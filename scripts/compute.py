#!/usr/bin/env python3
"""
compute.py — Parses the raw CSV pulls from the "Production and Operations
Dashboard" Google Sheet (already saved to disk by Claude via web_fetch) and
produces a single compact data.json with every number the dashboard template
needs. All arithmetic happens here (deterministic, no LLM tokens spent on
sums/percentages) so the model only has to write the narrative/insight copy.

Usage:
    python3 compute.py <raw_dir> <out_json> [--date YYYY-MM-DD]

Expected files in <raw_dir> (exact names, all CSV text as returned by the
Google Sheets gviz endpoint):
    photo_queue.csv
    film_queue.csv
    video_queue.csv
    ops.csv
    ops_staffing_detail.csv
    output_station.csv
    staffing.csv
    turn_estimate.csv
    yesterday_scores.csv
    week_data.csv
"""
import csv
import io
import json
import sys
import argparse
from datetime import datetime, timedelta

WEEKDAY_COL = {
    0: "Scheduled Monday",
    1: "Scheduled Tuesday",
    2: "Scheduled Wednesday",
    3: "Scheduled Thursday",
    4: "Scheduled Friday",
    # Sat/Sun: no scheduled column in the sheet — treated as no shift column,
    # staffing section will just show 0 unless overridden.
}


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def to_num(s, default=0.0):
    if s is None:
        return default
    s = str(s).strip().replace(",", "").replace("$", "").replace("%", "")
    if s in ("", "-", "--"):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def pct(part, whole):
    if not whole:
        return 0.0
    return round(100.0 * part / whole, 1)


# ---------------------------------------------------------------- Photo/Film Queue

def parse_bucket_queue(rows, category_names):
    """
    Generic parser for the Photo Queue / Film Queue style tabs:
    header row, then one row per category with
    00_Late,07_Day_Due,14_Day_Due,21_Day_Due,28_Day_Due (5 buckets -- the
    25-day working window split into Late + 4 weekly tiers).
    category_names: fixed ordered list matching row order (row 2..N of the sheet)
    """
    out = []
    # find header row index (contains 'Late' or '00_Late')
    start = 1
    for i, r in enumerate(rows):
        joined = ",".join(r).lower()
        if "late" in joined and "day_due" in joined:
            start = i + 1
            break
    for idx, name in enumerate(category_names):
        if start + idx >= len(rows):
            break
        r = rows[start + idx]
        # first cell may be blank or the category name itself
        vals = r[1:6] if len(r) >= 6 else r
        late, d7, d14, d21, d28 = (to_num(v) for v in (vals + ["0", "0", "0", "0", "0"])[:5])
        total = late + d7 + d14 + d21 + d28
        out.append({
            "name": name,
            "late": late, "due_7d": d7, "due_14d": d14, "due_21d": d21, "due_28d": d28,
            "total": total,
            "pct_late": pct(late, total), "pct_7d": pct(d7, total),
            "pct_14d": pct(d14, total), "pct_21d": pct(d21, total), "pct_28d": pct(d28, total),
        })
    return out


def parse_photo_queue(rows):
    return parse_bucket_queue(rows, ["Negative", "Paper", "Slide", "Special"])


def parse_film_queue(rows):
    # Row order follows the physical pipeline: Splice -> Capture -> Edit.
    # Same-date queue volumes are often identical across all three stages --
    # that's expected (nothing's been worked yet for that date cohort), not
    # a data bug.
    return parse_bucket_queue(rows, ["Film Splice", "Film Capture", "Film Edit"])


def parse_video_queue(rows):
    """
    Parses the simplified "Queue Breakdown" table: one row per bucket
    (00_Late..28_Day_Due) with columns Hi8,VHS,VHS-C,MiniDV,Audio,Other,Total,
    followed by a "Total Tapes in Queue" row (same column layout) and a
    "% of Queue" row. Players Used sits in the 00_Late row's 10th column.
    A secondary "Coming Due Daily Counts - Next 5 Days" table gives a short
    day-level forecast (kept for the capacity forecast tab).
    """
    types = ["Hi8", "VHS", "VHS-C", "MiniDV", "Audio", "Other"]
    label_field = {
        "00_late": "late", "07_day_due": "due_7d", "14_day_due": "due_14d",
        "21_day_due": "due_21d", "28_day_due": "due_28d",
    }
    idx = None
    for i, r in enumerate(rows):
        if r and r[0].strip().lower() == "queue breakdown":
            idx = i
            break
    by_type = {t: {"name": t, "late": 0, "due_7d": 0, "due_14d": 0, "due_21d": 0, "due_28d": 0, "total": 0} for t in types}
    result = {
        "types": [], "late": 0, "due_7d": 0, "due_14d": 0, "due_21d": 0, "due_28d": 0,
        "total_tapes": 0, "players_used": None, "daily_due": [],
    }
    if idx is not None:
        for j in range(1, 6):
            if idx + j >= len(rows):
                break
            r = rows[idx + j]
            label = (r[0] or "").strip().lower()
            field = label_field.get(label)
            if not field:
                continue
            for t_i, tname in enumerate(types):
                v = to_num(r[t_i + 1]) if len(r) > t_i + 1 else 0
                by_type[tname][field] = v
            total_v = to_num(r[7]) if len(r) > 7 else 0
            result[field] = total_v
            if field == "late" and len(r) > 9:
                result["players_used"] = to_num(r[9], None)
        for r in rows[idx:idx + 8]:
            if r and r[0].strip().lower() == "total tapes in queue":
                result["total_tapes"] = to_num(r[7]) if len(r) > 7 else 0
                for t_i, tname in enumerate(types):
                    by_type[tname]["total"] = to_num(r[t_i + 1]) if len(r) > t_i + 1 else 0
                break
    for t in by_type.values():
        tot = t["total"]
        t["pct_late"] = pct(t["late"], tot)
        t["pct_7d"] = pct(t["due_7d"], tot)
        t["pct_14d"] = pct(t["due_14d"], tot)
        t["pct_21d"] = pct(t["due_21d"], tot)
        t["pct_28d"] = pct(t["due_28d"], tot)
    result["types"] = [by_type[t] for t in types]
    # Backward-compat aliases used elsewhere in this file / render_dashboard.py
    result["current_lates"] = result["late"]
    result["due_7d_total"] = result["due_7d"]
    result["due_14d_total"] = result["due_14d"]

    for i, r in enumerate(rows):
        if r and r[0].strip().lower().startswith("coming due daily counts"):
            header_idx = i + 1  # "Date,Total,Hi8,VHS,VHS-C,MiniDV,Audio,Other"
            for r2 in rows[header_idx + 1: header_idx + 6]:
                if not r2 or not r2[0].strip():
                    continue
                result["daily_due"].append({
                    "date": r2[0].strip(),
                    "total": to_num(r2[1]) if len(r2) > 1 else 0,
                    "hi8": to_num(r2[2]) if len(r2) > 2 else 0,
                    "vhs": to_num(r2[3]) if len(r2) > 3 else 0,
                    "vhs_c": to_num(r2[4]) if len(r2) > 4 else 0,
                    "minidv": to_num(r2[5]) if len(r2) > 5 else 0,
                    "audio": to_num(r2[6]) if len(r2) > 6 else 0,
                    "other": to_num(r2[7]) if len(r2) > 7 else 0,
                })
            break
    return result


# ---------------------------------------------------------------- Ops

def parse_ops(rows, detail_rows):
    tasks = []
    section = None
    for r in rows:
        label = (r[1] if len(r) > 1 else "").strip()
        if not label:
            continue
        low = label.lower()
        if low == "task":
            continue  # column header row, not a section
        if low in ("order reception", "order review", "order fulfillment", "investigations + kits", "totals"):
            section = label
            continue
        if low in ("staffing", "trent", "kian", "anita", "other"):
            continue
        oldest = r[2].strip() if len(r) > 2 else ""
        count = to_num(r[3]) if len(r) > 3 else 0
        hrs = to_num(r[4]) if len(r) > 4 else 0.0
        if hrs or count or oldest:
            tasks.append({"section": section, "task": label, "oldest_date": oldest, "order_count": count, "hrs_reqd": hrs})

    totals = {"hrs_reqd_tasks": round(sum(t["hrs_reqd"] for t in tasks), 2)}
    # detail block: rows are [hrs_worked, label, value]
    for r in detail_rows:
        if len(r) < 3:
            continue
        label = r[1].strip().lower()
        val = to_num(r[2])
        if label == "total":
            totals["sheet_total_hrs_reqd"] = val
        elif label == "expected new":
            totals["expected_new_hrs"] = val
        elif label == "hours reqd":
            totals["hours_reqd_incl_new"] = val
        elif label == "hrs scheduled":
            totals["hrs_scheduled"] = val
        elif label == "difference":
            totals["gap_hrs"] = val
    return {"tasks": tasks, "totals": totals}


# ---------------------------------------------------------------- Staffing

def parse_staffing(rows, weekday_idx):
    header = rows[0]
    col = {name: i for i, name in enumerate(header)}
    day_col_name = WEEKDAY_COL.get(weekday_idx)
    trained_cols = [name for name in header if name.strip().lower().startswith("trained on")]
    people = []
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        def g(colname, default=""):
            i = col.get(colname)
            return r[i] if i is not None and i < len(r) else default
        scheduled_today = False
        if day_col_name and day_col_name in col:
            scheduled_today = g(day_col_name).strip().upper() == "TRUE"
        trained_on = [tc.replace("Trained on ", "").strip() for tc in trained_cols if g(tc).strip().upper() == "TRUE"]
        person = {
            "name": g("Staff Name"),
            "station": g("Station"),
            "department": g("Department"),
            "hours": to_num(g("Hours"), None),
            "weekly_hours": to_num(g("Weekly Hours"), None),
            "absent": g("Absent Y/N").strip().upper() == "TRUE",
            "scheduled_today": scheduled_today,
            "hrly_throughput": to_num(g("Hrly ThruPut"), None),
            "expected_output": to_num(g("Expected Output"), None),
            "trained_on": trained_on,
        }
        people.append(person)

    depts = {}
    for p in people:
        d = p["department"] or "Other"
        depts.setdefault(d, {"roster": [], "scheduled": [], "present": [], "absent": []})
        depts[d]["roster"].append(p)
        if p["scheduled_today"]:
            depts[d]["scheduled"].append(p)
            if p["absent"]:
                depts[d]["absent"].append(p)
            else:
                depts[d]["present"].append(p)

    dept_summary = {}
    for d, info in depts.items():
        sched_n = len(info["scheduled"])
        present_n = len(info["present"])
        dept_summary[d] = {
            "scheduled_count": sched_n,
            "present_count": present_n,
            "absent_count": len(info["absent"]),
            "pct_present": pct(present_n, sched_n) if sched_n else None,
            "present": [{"name": p["name"], "station": p["station"], "hours": p["hours"]} for p in info["present"]],
            "absent": [{"name": p["name"], "station": p["station"]} for p in info["absent"]],
            "scheduled_hours_total": round(sum((p["hours"] or 0) for p in info["present"]), 2),
        }
    return {"people": people, "by_department": dept_summary}


# ---------------------------------------------------------------- Output by Station

def parse_output_station(rows):
    stations = []
    for r in rows[1:]:
        if len(r) < 5 or not r[0].strip() or not r[1].strip():
            continue
        stations.append({
            "department": r[0].strip(), "media_type": r[1].strip(),
            "target_rate_hr": to_num(r[2]), "daily_output": to_num(r[3]),
            "weekly_output": to_num(r[4]),
        })
    return {"stations": stations}


# ---------------------------------------------------------------- Turn Estimate

def parse_turn_estimate(rows, avg10_rows=None):
    """
    avg10_rows: optional narrow supplemental fetch of just G2:H2 (Avg 10 Day
    Inbound / Avg 10 Day Output for the current row). Required because
    Google's gviz CSV export applies column type-inference across the WHOLE
    fetched range, and since the history rows below don't share column H's
    numeric type consistently, it silently blanks H2 when the tab is fetched
    without an explicit narrow range — even though the cell has a real
    value. Same class of bug as the Ops tab's dropped side-table cells.
    """
    header = rows[0]
    entries = []
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        entries.append({
            "date": r[0].strip(),
            "est_daily_output": to_num(r[1]),
            "checked_in": to_num(r[2]),
            "pending_wsa": to_num(r[3]),
            "total_backlog": to_num(r[4]),
            "est_daily_inbound": to_num(r[5]),
            "avg_10d_inbound": to_num(r[6]),
            "avg_10d_output": to_num(r[7], None) if len(r) > 7 else None,
        })
    current = entries[0] if entries else None
    history = entries[1:] if len(entries) > 1 else []

    if current and avg10_rows:
        for r in avg10_rows:
            if len(r) >= 2 and (r[0].strip() or r[1].strip()):
                current["avg_10d_inbound"] = to_num(r[0], current.get("avg_10d_inbound"))
                current["avg_10d_output"] = to_num(r[1], current.get("avg_10d_output"))
                break

    return {"current": current, "history": history}


# ---------------------------------------------------------------- Yesterday Scores

def parse_yesterday_scores(rows):
    # master roster columns A-E: Date, Name, Scheduled, Actual, Pct
    master = []
    for r in rows[4:]:  # data starts after header rows (0-3)
        if len(r) < 5:
            continue
        date, name, sched, act, p = r[0], r[1], r[2], r[3], r[4]
        if not name.strip():
            continue
        master.append({
            "date": date.strip(), "name": name.strip(),
            "scheduled": to_num(sched, None), "actual": to_num(act, None),
            "pct": to_num(p, None),
        })

    def lookup_name(sched, act, p):
        for m in master:
            if abs((m["scheduled"] or -999) - sched) < 0.02 and abs((m["actual"] or -999) - act) < 0.02:
                return m["name"]
        return None

    dept_blocks = {"Photo": 6, "Film": 12, "Video": 18, "Operations": 24}
    depts = {}
    header_row = rows[0]
    for dept, base_col in dept_blocks.items():
        attendance = score = output = None
        for r in rows[:4]:
            if len(r) > base_col and r[base_col].strip().lower() == "attendance":
                attendance = r[base_col + 1] if len(r) > base_col + 1 else None
            if len(r) > base_col and r[base_col].strip().lower() == "score":
                score = r[base_col + 1] if len(r) > base_col + 1 else None
            if len(r) > base_col and r[base_col].strip().lower() == "output":
                output = r[base_col + 1] if len(r) > base_col + 1 else None
        # tier-1 people rows run until a "Name" marker (start of a rollup/detail
        # sub-table further down the same columns, e.g. in the Operations block)
        boundary = len(rows)
        for i, r in enumerate(rows[5:], start=5):
            if len(r) > base_col and r[base_col].strip().lower() == "name":
                boundary = i
                break
        people = []
        for r in rows[5:boundary]:
            if len(r) <= base_col + 4:
                continue
            date_c, name_c, sched_c, act_c, pct_c = (r[base_col:base_col + 5] + ["", "", "", "", ""])[:5]
            sched_v, act_v, pct_v = to_num(sched_c, None), to_num(act_c, None), to_num(pct_c, None)
            if sched_v is None and act_v is None:
                continue
            nm = name_c.strip() or (lookup_name(sched_v, act_v, pct_v) if sched_v is not None and act_v is not None else None)
            if not nm:
                continue
            people.append({"name": nm, "scheduled": sched_v, "actual": act_v, "pct": pct_v})
        depts[dept] = {
            "attendance": attendance, "score": score, "output": to_num(output, None) if output else None,
            "people": people,
        }

    # Operations also has a per-station detail table further down the same
    # columns (Name | Position | Scheduled | Actual | Pct), e.g. Anita's
    # Final Check vs Ops General split. Find it and attach as "detail".
    ops_col = 24
    ops_detail = []
    in_detail = False
    for r in rows[5:]:
        if len(r) <= ops_col + 1:
            continue
        c0, c1 = r[ops_col].strip(), r[ops_col + 1].strip()
        if c0.lower() == "name" and c1.lower() == "position":
            in_detail = True
            continue
        if not in_detail or not c0:
            continue
        hrs_s = to_num(r[ops_col + 2], None) if len(r) > ops_col + 2 else None
        hrs_a = to_num(r[ops_col + 3], None) if len(r) > ops_col + 3 else None
        p = to_num(r[ops_col + 4], None) if len(r) > ops_col + 4 else None
        ops_detail.append({"name": c0, "position": c1.replace("Position: ", ""), "scheduled": hrs_s, "actual": hrs_a, "pct": p})
    if "Operations" in depts:
        depts["Operations"]["detail_by_station"] = ops_detail
    return depts


# ---------------------------------------------------------------- Week Data

def parse_week_data(rows):
    def col(rowidx, c):
        r = rows[rowidx] if rowidx < len(rows) else []
        return r[c] if c < len(r) else ""

    inbound = {}
    for r in rows[1:7]:
        name, total = r[0].strip(), r[1].strip() if len(r) > 1 else ""
        if name:
            inbound[name] = to_num(total)
    orders = to_num(col(1, 3))
    gross = to_num(col(1, 4))

    # "Last Week Pieces Made Online" is actually TWO stacked tables in the
    # sheet (col G/H): a Photo media-type breakdown ending in its own
    # "Total", then (after a "Combined" header row) a department-level
    # Photo/Film/Video table ending in the true grand "Total". Keep them
    # distinct rather than flattening into one dict — the sheet's own
    # first "Total" is a Photo subtotal, not the grand total.
    media_breakdown = {}
    media_breakdown_total = None
    combined = {}
    combined_total = None
    phase = "media"
    for r in rows[1:]:
        name = r[6].strip() if len(r) > 6 else ""
        val = r[7].strip() if len(r) > 7 else ""
        if not name:
            continue
        if name.lower() == "combined":
            phase = "combined"
            continue
        if name.lower() == "total":
            if phase == "media" and media_breakdown_total is None:
                media_breakdown_total = to_num(val)
            elif phase == "combined":
                combined_total = to_num(val)
                break  # grand total row ends this block
            continue
        if phase == "media":
            media_breakdown[name] = to_num(val)
        else:
            combined[name] = to_num(val)
    output_lw = {
        "media_breakdown": media_breakdown, "media_breakdown_total": media_breakdown_total,
        "combined": combined, "combined_total": combined_total,
    }

    payroll = []
    for r in rows[1:]:
        name = r[9].strip() if len(r) > 9 else ""
        hrs = r[10].strip() if len(r) > 10 else ""
        pay = r[11].strip() if len(r) > 11 else ""
        if name and name.lower() != "total":
            payroll.append({"name": name, "hours": to_num(hrs), "pay": to_num(pay)})
        elif name.lower() == "total":
            payroll_total = {"hours": to_num(hrs), "pay": to_num(pay)}

    revenue = {}
    for r in rows[1:6]:
        name = r[13].strip() if len(r) > 13 else ""
        val = r[14].strip() if len(r) > 14 else ""
        if name:
            revenue[name] = to_num(val)

    dept_hours = {}
    for r in rows[1:6]:
        name = r[16].strip() if len(r) > 16 else ""
        val = r[17].strip() if len(r) > 17 else ""
        if name:
            dept_hours[name] = to_num(val)

    late_rates = {}
    prefix_orders = {}
    in_prefix = False
    for r in rows[1:]:
        name = r[19].strip() if len(r) > 19 else ""
        val = r[20].strip() if len(r) > 20 else ""
        if not name:
            continue
        if name.lower() == "prefix":
            in_prefix = True
            continue
        if in_prefix:
            prefix_orders[name] = to_num(val, val)
        else:
            late_rates[name] = val
    on_time = to_num(late_rates.get("Quantity On-Time"), None)
    late = to_num(late_rates.get("Quantity Late"), None)
    if on_time is not None and late is not None and (on_time + late) > 0:
        late_rates["pct_on_time_computed"] = pct(on_time, on_time + late)
        late_rates["pct_late_computed"] = pct(late, on_time + late)

    return {
        "this_week_inbound": inbound, "this_week_orders": orders, "this_week_gross": gross,
        "last_week_output": output_lw, "last_week_payroll": payroll,
        "last_week_payroll_total": payroll_total if "payroll_total" in dir() else None,
        "last_week_revenue": revenue, "last_week_dept_hours": dept_hours,
        "late_rates": late_rates, "late_rates_prefix": prefix_orders,
    }


# ---------------------------------------------------------------- Photo Late Orders

def _sort_key_date(entry):
    d = entry.get("due_date", "")
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(d, fmt)
        except ValueError:
            continue
    return datetime.max  # unparseable dates sort last


def parse_photo_late_orders(rows):
    # 4 side-by-side blocks: Slides Lates | Negatives Lates | Special Lates | Paper Lates
    # each block: <Category>, Order ID, Due Date, Quantity, Storage Location, <blank>
    blocks = [
        ("slides", 0), ("negatives", 6), ("special", 12), ("paper", 18),
    ]
    result = {}
    for key, start in blocks:
        entries = []
        total_qty = None
        for r in rows[1:]:
            if len(r) <= start + 4:
                continue
            cat, order_id, due_date, qty, storage = (r[start:start + 5] + ["", "", "", "", ""])[:5]
            cat = cat.strip()
            order_id = order_id.strip()
            due_date = due_date.strip()
            if cat.lower() == "total":
                total_qty = to_num(qty, None)
                continue
            if not order_id or not due_date:
                continue
            entries.append({
                "order_id": order_id, "due_date": due_date,
                "quantity": to_num(qty, None), "storage_location": storage.strip(),
            })
        entries.sort(key=_sort_key_date)
        result[key] = {
            "entries": entries,
            "count": len(entries),
            "total_quantity": total_qty if total_qty is not None else round(sum((e["quantity"] or 0) for e in entries), 0),
        }
    return result


# ---------------------------------------------------------------- Station Capacity (Staffing tab)

# Photo queue tab uses singular category names; Staffing tab / Output tab use these labels.
PHOTO_QUEUE_TO_STATION = {"Negative": "Negatives", "Paper": "Paper", "Slide": "Slides", "Special": "Special"}

OPS_GROUPS = [
    {"label": "Shipping (priority)", "tasks": ["Shipping", "Upcoming Shipping (Loading + Matching)"], "trained": ["Shipping"]},
    {"label": "Final Check + Video Review", "tasks": ["Final Check", "Video Review (Assigning)", "Video Review (Verification)"], "trained": ["Final Check", "Video Review"]},
    {"label": "Check-In + Matching + Tickets", "tasks": ["Reception", "Late Check-In", "Non-Rush Check-In Video", "Non-Rush Check-In Photo", "Matching", "Tickets"], "trained": ["Check-In", "Matching", "Tickets"]},
]


def build_station_capacity(data):
    people = data["staffing"]["people"]
    out_by_station = {s["media_type"]: s for s in data["output_station"]["stations"]}
    photo_by_cat = {c["name"]: c for c in data["queues"]["photo"]}
    film_by_cat = {c["name"]: c for c in data["queues"]["film"]}
    video = data["queues"]["video"]

    def build_row(station_name, dept_label, queue_info, trained_flag_name):
        assigned = [p for p in people if p["station"] == station_name and p["scheduled_today"] and not p["absent"]]
        assigned_names = {p["name"] for p in assigned}
        backup = sorted({p["name"] for p in people if trained_flag_name in (p.get("trained_on") or []) and p["name"] not in assigned_names})
        out = out_by_station.get(station_name, {})
        late = (queue_info or {}).get("late", 0) or 0
        due7 = (queue_info or {}).get("due_7d", 0) or 0
        total = (queue_info or {}).get("total", 0) or 0
        output_day = out.get("daily_output")
        if late > 0:
            flag = "critical" if total and pct(late, total) >= 15 else "watch"
        elif output_day and due7 > output_day * 2:
            flag = "watch"
        else:
            flag = "stable"
        return {
            "station": station_name, "department": dept_label,
            "assigned": [{"name": p["name"], "hours": p["hours"]} for p in assigned],
            "cross_trained_backup": backup,
            "output_day": output_day,
            "queue_total": total, "queue_late": late, "queue_due_7d": due7,
            "flag": flag,
        }

    rows = {"photo": [], "film": [], "video": [], "operations": []}

    for station_name in ["Negatives", "Slides", "Paper", "Special"]:
        cat_name = next((k for k, v in PHOTO_QUEUE_TO_STATION.items() if v == station_name), None)
        rows["photo"].append(build_row(station_name, "Photo", photo_by_cat.get(cat_name), station_name))

    for station_name in ["Film Edit", "Film Splice", "Film Capture"]:
        rows["film"].append(build_row(station_name, "Film", film_by_cat.get(station_name), station_name))

    video_assigned = [p for p in people if p["station"] == "Video" and p["scheduled_today"] and not p["absent"]]
    video_names = {p["name"] for p in video_assigned}
    video_backup = sorted({p["name"] for p in people if "Video" in (p.get("trained_on") or []) and p["name"] not in video_names})
    video_out = out_by_station.get("Video", {})
    v_late = video.get("current_lates", 0) or 0
    v_due7 = video.get("due_7d_total", 0) or 0
    rows["video"].append({
        "station": "Video (all formats)", "department": "Video",
        "assigned": [{"name": p["name"], "hours": p["hours"]} for p in video_assigned],
        "cross_trained_backup": video_backup,
        "output_day": video_out.get("daily_output"),
        "queue_total": video.get("total_tapes", 0), "queue_late": v_late, "queue_due_7d": v_due7,
        "flag": "critical" if v_late > 0 else ("watch" if v_due7 and v_due7 > 20 else "stable"),
    })

    ops_tasks_by_name = {t["task"]: t for t in data["ops"]["tasks"]}
    for group in OPS_GROUPS:
        hrs = round(sum(ops_tasks_by_name.get(t, {}).get("hrs_reqd", 0) for t in group["tasks"]), 2)
        orders = round(sum(ops_tasks_by_name.get(t, {}).get("order_count", 0) for t in group["tasks"]), 0)
        eligible = [p for p in people if p["department"] == "Operations" and p["scheduled_today"] and not p["absent"]
                    and any(tf in (p.get("trained_on") or []) for tf in group["trained"])]
        eligible_names = {p["name"] for p in eligible}
        backup = sorted({p["name"] for p in people if p["department"] == "Operations"
                          and any(tf in (p.get("trained_on") or []) for tf in group["trained"])
                          and p["name"] not in eligible_names})
        rows["operations"].append({
            "station": group["label"], "department": "Operations",
            "assigned": [{"name": p["name"], "hours": p["hours"]} for p in eligible],
            "cross_trained_backup": backup,
            "output_day": None,
            "queue_total": orders, "queue_late": None, "queue_due_7d": None,
            "hrs_reqd": hrs,
            "flag": "critical" if hrs > sum((p["hours"] or 0) for p in eligible) else "watch" if eligible else "critical",
        })

    return rows


# ---------------------------------------------------------------- Equipment / Station Capacity (Station Capacity tab)
# NOTE: this is distinct from build_station_capacity() below, which is the
# STAFFING-based "who's assigned today" table (Staffing tab). This section
# parses the separate "Station Capacity" tab -- physical machine counts and
# throughput -- which Mark added specifically to support equipment-vs-staffing
# capacity forecasting.

def parse_equipment_capacity(rows):
    out = []
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        media_type = r[0].strip()
        station = r[1].strip() if len(r) > 1 else ""
        n_stations = to_num(r[2]) if len(r) > 2 else 0
        throughput_hr = to_num(r[3]) if len(r) > 3 else 0
        max_operators = to_num(r[4], 1) if len(r) > 4 else 1
        hours_avail = to_num(r[5]) if len(r) > 5 else 0
        n_down = to_num(r[6], 0) if len(r) > 6 else 0
        n_available = max(n_stations - n_down, 0)
        effective_daily_capacity = round(n_available * throughput_hr * max_operators * hours_avail, 1)
        max_daily_capacity = round(n_stations * throughput_hr * max_operators * hours_avail, 1)
        out.append({
            "media_type": media_type, "station": station,
            "stations_total": n_stations, "stations_down": n_down, "stations_available": n_available,
            "throughput_per_hr": throughput_hr, "max_operators": max_operators,
            "hours_available": hours_avail,
            "effective_daily_capacity": effective_daily_capacity,
            "max_daily_capacity": max_daily_capacity,
        })
    return out


# ---------------------------------------------------------------- Capacity & Forecast (weekly jeopardy projection)

# Working days per week used for all cumulative projections below. Mark's
# shop runs a Mon-Fri schedule (the Staffing tab only has weekday columns),
# so equipment ceilings are also projected on a 5-day week even though the
# Station Capacity tab's "Operating Hours per Day Available" allows for a
# fuller multi-shift day.
WORKING_DAYS_PER_WEEK = 5

# Maps a forecast group -> (photo/film queue category name, media_type used
# for output_station lookup). Video is handled separately as one aggregate
# line since it isn't a current pain point and the 6 tape types would add a
# lot of noise for little decision value.
GROUP_TO_QUEUE = {
    "Negatives": ("photo", "Negative"),
    "Slides": ("photo", "Slide"),
    "Paper": ("photo", "Paper"),
    "Special": ("photo", "Special"),
    "Film Splice": ("film", "Film Splice"),
    "Film Capture": ("film", "Film Capture"),
    "Film Edit": ("film", "Film Edit"),
}
GROUP_TO_OUTPUT_STATION = {
    "Negatives": "Negatives", "Slides": "Slides", "Paper": "Paper", "Special": "Special",
    "Film Splice": "Film Splice", "Film Capture": "Film Capture", "Film Edit": "Film Edit",
    "Video": "Video",
}


# Maps a forecast group -> (station_capacity dept key, station name) so we
# can pull today's assigned staff for that station and cross-check
# expected-vs-actual output (a "performance" root-cause signal).
GROUP_TO_STATION_CAPACITY = {
    "Negatives": ("photo", "Negatives"), "Slides": ("photo", "Slides"),
    "Paper": ("photo", "Paper"), "Special": ("photo", "Special"),
    "Film Splice": ("film", "Film Splice"), "Film Capture": ("film", "Film Capture"),
    "Film Edit": ("film", "Film Edit"), "Video": ("video", "Video (all formats)"),
}


def _root_cause_signals(name, data):
    dept, station_name = GROUP_TO_STATION_CAPACITY.get(name, (None, None))
    cap_rows = data.get("station_capacity", {}).get(dept, []) if dept else []
    row = next((r for r in cap_rows if r["station"] == station_name), None)
    assigned = row["assigned"] if row else []
    # Match by (name, station) pair, not name alone -- several people (e.g.
    # Rob Hall on both Film Capture and Film Splice) have separate sheet
    # rows with different per-station Expected Output values, and matching
    # on name alone would double/mis-count their output across stations.
    if station_name == "Video (all formats)":
        station_match = "Video"
    else:
        station_match = station_name
    expected_total = 0.0
    any_expected = False
    for p in data["staffing"]["people"]:
        if p["station"] != station_match or not p["scheduled_today"] or p["absent"]:
            continue
        if p.get("expected_output") is not None:
            expected_total += p["expected_output"]
            any_expected = True
    return {
        "assigned_headcount": len(assigned),
        "expected_output_today": round(expected_total, 1) if any_expected else None,
    }


def _classify_causes(assigned_headcount, expected_output, actual_output, any_at_risk_late):
    """
    Mechanical (no judgment) cause tags, most-specific first. narrative.json
    picks which to foreground and writes the actual explanation -- this just
    flags what's checkable from the numbers:
      - no_staff_assigned: nobody logged against this station today
      - underperformed_vs_expected: staff were assigned, but actual output
        came in well under what their Expected Output figures add up to
        (a performance signal, not a staffing or volume one)
      - volume_exceeds_staffed_capacity: due-date volume in the at-risk
        window exceeds what today's staffed rate can clear, and neither of
        the above applies -- i.e. the backlog itself is the constraint, not
        who showed up or how they performed
    """
    causes = []
    if assigned_headcount == 0:
        causes.append("no_staff_assigned")
    elif expected_output and expected_output > 0 and actual_output is not None:
        ratio = actual_output / expected_output
        if ratio < 0.85:
            causes.append("underperformed_vs_expected")
    if any_at_risk_late and not causes:
        causes.append("volume_exceeds_staffed_capacity")
    return causes


def _equipment_group_key(row):
    mt = row["media_type"]
    if mt == "Film":
        s = row["station"].lower()
        if "splice" in s:
            return "Film Splice"
        if "capture" in s:
            return "Film Capture"
        if "edit" in s:
            return "Film Edit"
        return "Film Other"
    if mt == "Video":
        return "Video"
    return mt  # Negatives / Slides / Paper / Special


def build_capacity_forecast(data):
    equipment_rows = data.get("equipment_capacity", [])
    equip_by_group = {}
    for row in equipment_rows:
        key = _equipment_group_key(row)
        g = equip_by_group.setdefault(key, {
            "effective_daily_capacity": 0.0, "max_daily_capacity": 0.0,
            "stations_total": 0, "stations_down": 0,
        })
        g["effective_daily_capacity"] += row["effective_daily_capacity"]
        g["max_daily_capacity"] += row["max_daily_capacity"]
        g["stations_total"] += row["stations_total"]
        g["stations_down"] += row["stations_down"]

    out_by_media = {s["media_type"]: s for s in data["output_station"]["stations"]}
    photo_by_cat = {c["name"]: c for c in data["queues"]["photo"]}
    film_by_cat = {c["name"]: c for c in data["queues"]["film"]}
    video = data["queues"]["video"]

    groups = []

    def make_entry(name, queue_bucket, equip):
        equip = equip or {"effective_daily_capacity": 0.0, "max_daily_capacity": 0.0, "stations_total": 0, "stations_down": 0}
        late = (queue_bucket or {}).get("late", 0) or 0
        d7 = (queue_bucket or {}).get("due_7d", 0) or 0
        d14 = (queue_bucket or {}).get("due_14d", 0) or 0
        d21 = (queue_bucket or {}).get("due_21d", 0) or 0
        d28 = (queue_bucket or {}).get("due_28d", 0) or 0
        total_queue = late + d7 + d14 + d21 + d28

        week1_due = late + d7
        week2_due = week1_due + d14
        week3_due = week2_due + d21
        week4_due = week3_due + d28

        out_station = out_by_media.get(GROUP_TO_OUTPUT_STATION.get(name, name), {})
        staffed_daily = out_station.get("daily_output")
        equip_ceiling_daily = equip["effective_daily_capacity"]

        weeks = []
        constrained_by_overall = None
        for wk, due_cum in enumerate([week1_due, week2_due, week3_due, week4_due], start=1):
            staffed_cum = round((staffed_daily or 0) * WORKING_DAYS_PER_WEEK * wk, 1)
            equip_cum = round(equip_ceiling_daily * WORKING_DAYS_PER_WEEK * wk, 1)
            if staffed_daily is None:
                status = "unknown"
            elif staffed_cum < due_cum:
                status = "at_risk_late"
            elif staffed_cum > total_queue and total_queue > 0 and staffed_cum - total_queue > staffed_daily * WORKING_DAYS_PER_WEEK:
                # capacity would clear the ENTIRE current queue with more than
                # a week of headroom to spare by this point -- running-low signal
                status = "at_risk_running_low"
            else:
                status = "on_track"
            weeks.append({
                "week": wk, "due_cumulative": round(due_cum, 1),
                "staffed_capacity_cumulative": staffed_cum,
                "equipment_capacity_cumulative": equip_cum,
                "status": status,
            })

        utilization_vs_equipment = None
        constrained_by = None
        if equip_ceiling_daily and staffed_daily is not None:
            utilization_vs_equipment = round(pct(staffed_daily, equip_ceiling_daily), 1)
            any_late_risk = any(w["status"] == "at_risk_late" for w in weeks)
            if any_late_risk:
                if utilization_vs_equipment >= 90:
                    constrained_by = "equipment"
                elif utilization_vs_equipment < 60:
                    constrained_by = "staffing"
                else:
                    constrained_by = "mixed"

        root = _root_cause_signals(name, data)
        any_at_risk_late = any(w["status"] == "at_risk_late" for w in weeks)
        causes = _classify_causes(root["assigned_headcount"], root["expected_output_today"], staffed_daily, any_at_risk_late)

        groups.append({
            "name": name,
            "total_queue": round(total_queue, 1),
            "late": late,
            "staffed_daily_capacity": staffed_daily,
            "equipment_daily_capacity": equip_ceiling_daily,
            "equipment_stations_total": equip["stations_total"],
            "equipment_stations_down": equip["stations_down"],
            "utilization_vs_equipment_pct": utilization_vs_equipment,
            "constrained_by": constrained_by,
            "weeks": weeks,
            "assigned_headcount_today": root["assigned_headcount"],
            "expected_output_today": root["expected_output_today"],
            "causes": causes,
            "late_trend": None,       # filled in by _merge_capacity_trend() if a prior log entry exists
            "week1_status_trend": None,
            "trend_prior_date": None,
        })

    for name, (dept, cat) in GROUP_TO_QUEUE.items():
        bucket = (photo_by_cat if dept == "photo" else film_by_cat).get(cat)
        make_entry(name, bucket, equip_by_group.get(name))

    # Video: one aggregate line across all 6 tape types.
    video_bucket = {
        "late": video.get("late", 0), "due_7d": video.get("due_7d", 0),
        "due_14d": video.get("due_14d", 0), "due_21d": video.get("due_21d", 0),
        "due_28d": video.get("due_28d", 0),
    }
    video_equip = equip_by_group.get("Video")
    make_entry("Video", video_bucket, video_equip)

    return groups


def merge_capacity_trend(groups, prior_log, report_date=None):
    """
    prior_log: parsed capacity_log.json (list of {date, groups:[...]}) as
    logged by the Deliver step on past runs. Finds the most recent entry
    STRICTLY BEFORE report_date and fills in late_trend / week1_status_trend
    for each group so narrative.json can distinguish "carrying over" from
    "newly emerged" lates, and flag the first day a station's output looks
    off vs yesterday. Pure comparison -- no judgment. Safe to call with an
    empty/missing log, or a log that only contains today's own entry
    (e.g. a re-run) -- everything just stays "first_day_tracking".
    """
    candidates = [e for e in (prior_log or []) if report_date is None or e.get("date", "") < report_date]
    if not candidates:
        for g in groups:
            g["late_trend"] = "first_day_tracking"
            g["week1_status_trend"] = "first_day_tracking"
        return groups
    prior_entry = sorted(candidates, key=lambda e: e.get("date", ""))[-1]
    prior_by_name = {pg["name"]: pg for pg in prior_entry.get("groups", [])}
    for g in groups:
        pg = prior_by_name.get(g["name"])
        if not pg:
            g["late_trend"] = "first_day_tracking"
            g["week1_status_trend"] = "first_day_tracking"
            continue
        g["trend_prior_date"] = prior_entry.get("date")
        prior_late = pg.get("late") or 0
        today_late = g.get("late") or 0
        if today_late > prior_late:
            g["late_trend"] = "up"
        elif today_late < prior_late:
            g["late_trend"] = "down"
        else:
            g["late_trend"] = "flat"
        prior_week1 = (pg.get("week_statuses") or [None])[0]
        today_week1 = g["weeks"][0]["status"] if g["weeks"] else None
        if prior_week1 == today_week1:
            g["week1_status_trend"] = "unchanged_at_risk" if today_week1 == "at_risk_late" else "unchanged_on_track"
        elif today_week1 == "at_risk_late" and prior_week1 != "at_risk_late":
            g["week1_status_trend"] = "newly_emerged"
        elif today_week1 != "at_risk_late" and prior_week1 == "at_risk_late":
            g["week1_status_trend"] = "resolved"
        else:
            g["week1_status_trend"] = "changed"
    return groups


# ---------------------------------------------------------------- Daily Notes

def parse_daily_notes(rows):
    notes = []
    for r in rows:
        if not r:
            continue
        text = (r[0] or "").strip()
        if text:
            notes.append(text)
    return notes


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_dir")
    ap.add_argument("out_json")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD, defaults to system today")
    args = ap.parse_args()

    if args.date:
        today = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        today = datetime.now()
    weekday_idx = today.weekday()  # 0=Mon

    rd = args.raw_dir.rstrip("/")

    photo_rows = read_csv(f"{rd}/photo_queue.csv")
    film_rows = read_csv(f"{rd}/film_queue.csv")
    video_rows = read_csv(f"{rd}/video_queue.csv")
    ops_rows = read_csv(f"{rd}/ops.csv")
    ops_detail_rows = read_csv(f"{rd}/ops_staffing_detail.csv")
    out_station_rows = read_csv(f"{rd}/output_station.csv")
    staffing_rows = read_csv(f"{rd}/staffing.csv")
    turn_rows = read_csv(f"{rd}/turn_estimate.csv")
    scores_rows = read_csv(f"{rd}/yesterday_scores.csv")
    week_rows = read_csv(f"{rd}/week_data.csv")
    late_orders_rows = read_csv(f"{rd}/photo_late_orders.csv")
    try:
        daily_notes_rows = read_csv(f"{rd}/daily_notes.csv")
    except FileNotFoundError:
        daily_notes_rows = []
    try:
        turn_avg10_rows = read_csv(f"{rd}/turn_estimate_avg10.csv")
    except FileNotFoundError:
        turn_avg10_rows = []
    try:
        equipment_rows = read_csv(f"{rd}/station_capacity_equipment.csv")
    except FileNotFoundError:
        equipment_rows = []
    try:
        with open(f"{rd}/capacity_log_prior.json", "r", encoding="utf-8") as f:
            capacity_log_prior = json.load(f)
    except FileNotFoundError:
        capacity_log_prior = []

    data = {
        "meta": {
            "date": today.strftime("%Y-%m-%d"),
            "date_display": today.strftime("%B %-d, %Y") if hasattr(today, "strftime") else today.strftime("%B %d, %Y"),
            "weekday": today.strftime("%A"),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "queues": {
            "photo": parse_photo_queue(photo_rows),
            "film": parse_film_queue(film_rows),
            "video": parse_video_queue(video_rows),
        },
        "ops": parse_ops(ops_rows, ops_detail_rows),
        "staffing": parse_staffing(staffing_rows, weekday_idx),
        "output_station": parse_output_station(out_station_rows),
        "turn_estimate": parse_turn_estimate(turn_rows, turn_avg10_rows),
        "scores": parse_yesterday_scores(scores_rows),
        "week": parse_week_data(week_rows),
        "photo_late_orders": parse_photo_late_orders(late_orders_rows),
        "daily_notes": parse_daily_notes(daily_notes_rows),
        "equipment_capacity": parse_equipment_capacity(equipment_rows),
    }

    data["station_capacity"] = build_station_capacity(data)
    data["capacity_forecast"] = merge_capacity_trend(build_capacity_forecast(data), capacity_log_prior, report_date=data["meta"]["date"])

    # ---- derived top-line KPIs (all mechanical, no judgment) ----
    te_cur = data["turn_estimate"]["current"] or {}
    te_hist = data["turn_estimate"]["history"]
    prev = te_hist[0] if te_hist else None
    # Per Mark: use the sheet's own "Avg 10 Day Output" figure directly for
    # the surplus calc (more accurate than an estimated fallback average).
    # If the sheet hasn't got a value for it yet, show missing rather than
    # guessing.
    avg_output = te_cur.get("avg_10d_output")
    surplus = None
    if avg_output is not None and te_cur.get("avg_10d_inbound") is not None:
        surplus = round(avg_output - te_cur["avg_10d_inbound"], 0)
    photo_total_late = sum(c["late"] for c in data["queues"]["photo"])
    photo_total_units = sum(c["total"] for c in data["queues"]["photo"])
    film_total_late = sum(c["late"] for c in data["queues"]["film"])
    ops_gap = data["ops"]["totals"].get("gap_hrs")
    ops_present_hours = data["staffing"]["by_department"].get("Operations", {}).get("scheduled_hours_total")
    data["kpi_summary"] = {
        "backlog_total": te_cur.get("total_backlog"),
        "checked_in": te_cur.get("checked_in"),
        "pending_wsa": te_cur.get("pending_wsa"),
        "backlog_prev_entry": (prev or {}).get("total_backlog"),
        "backlog_prev_entry_date": (prev or {}).get("date"),
        "est_daily_output": te_cur.get("est_daily_output"),
        "est_daily_inbound": te_cur.get("est_daily_inbound"),
        "avg_10d_inbound": te_cur.get("avg_10d_inbound"),
        "avg_10d_output": avg_output,
        "output_surplus_per_day": surplus,
        "photo_total_late_units": photo_total_late,
        "photo_total_queue_units": photo_total_units,
        "photo_pct_late": pct(photo_total_late, photo_total_units),
        "film_total_late_units": film_total_late,
        "video_current_lates": data["queues"]["video"].get("current_lates"),
        "ops_gap_hrs_sheet": ops_gap,
        "ops_present_scheduled_hours": ops_present_hours,
        "note": "ops_gap_hrs_sheet uses the sheet's own Hrs Scheduled figure, which "
                "may NOT reflect same-day call-outs (Absent Y/N). Prefer "
                "ops_present_scheduled_hours (sum of hours for staff actually present "
                "today) when writing the staffing-gap narrative.",
    }

    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {args.out_json}")


if __name__ == "__main__":
    main()
