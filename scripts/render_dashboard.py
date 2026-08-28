#!/usr/bin/env python3
"""
render_dashboard.py — merges data.json (computed, from compute.py) with
narrative.json (prose written by Claude) into the final 3-tab HTML dashboard.
Pure templating: no arithmetic, no judgment calls happen here.

Usage:
    python3 render_dashboard.py <data.json> <narrative.json> <out.html>
"""
import json
import sys
import html as html_lib


def esc(s):
    if s is None:
        return ""
    return html_lib.escape(str(s))


def fnum(v, decimals=0):
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return esc(v)
    if decimals == 0:
        return f"{v:,.0f}"
    return f"{v:,.{decimals}f}"


def signed(v, decimals=0):
    if v is None:
        return "—"
    v = float(v)
    s = fnum(abs(v), decimals)
    return f"{'+' if v >= 0 else '-'}{s}"


CSS = """
:root{
  --bg:#12161D;--panel:#1B2129;--panel-raised:#212834;--line:#2C3340;
  --ink:#ECEEF1;--muted:#8B93A1;--muted-dim:#5E6573;
  --good:#4FB286;--good-dim:#2A4A3D;
  --warn:#E0A23A;--warn-dim:#4A3B22;
  --bad:#D9594C;--bad-dim:#4A2B27;
  --accent:#5B9BD5;--accent-dim:#22344A;
  --photo:#7B68EE;--photo-dim:#2A2550;
  --film:#E07B3A;--film-dim:#4A2E1A;
  --video:#3ABDE0;--video-dim:#1A3A4A;
  --ops:#9DE03A;--ops-dim:#2C4A1A;
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{background:var(--bg);color:var(--ink);font-family:'Inter',system-ui,sans-serif;font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased;}
body{padding:24px 28px 60px;max-width:1400px;margin:0 auto;}
h1,h2,h3,.oswald,.kpi-value,.kpi-label,.dept-badge,.gap-pill,th,.station-name,.eyebrow,.trend-section-label{font-family:'Oswald',sans-serif;letter-spacing:.02em;}
table{font-variant-numeric:tabular-nums;}
header{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid var(--line);padding-bottom:16px;margin-bottom:16px;flex-wrap:wrap;gap:12px;}
.eyebrow{font-size:11px;color:var(--accent);font-weight:600;text-transform:uppercase;letter-spacing:.12em;margin-bottom:5px;}
h1{font-size:28px;font-weight:600;text-transform:uppercase;}
.meta-block{text-align:right;color:var(--muted);font-size:13px;}
.big-date{color:var(--ink);font-size:15px;font-weight:600;font-family:'Oswald',sans-serif;}
.status-pill{display:inline-flex;align-items:center;gap:8px;padding:5px 13px;border-radius:3px;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;margin-top:7px;font-family:'Oswald',sans-serif;}
.status-pill.bad{background:var(--bad-dim);color:var(--bad);border:1px solid #6b2929;}
.status-pill.warn{background:var(--warn-dim);color:var(--warn);border:1px solid #6b5429;}
.status-pill.good{background:var(--good-dim);color:var(--good);border:1px solid #2f6b4a;}
.dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}
.dot.bad{background:var(--bad);}.dot.warn{background:var(--warn);}.dot.good{background:var(--good);}

.tabbar{display:flex;gap:4px;margin-bottom:22px;border-bottom:1px solid var(--line);}
.tabbtn{font-family:'Oswald',sans-serif;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);background:none;border:none;padding:11px 18px;cursor:pointer;border-bottom:3px solid transparent;}
.tabbtn:hover{color:var(--ink);}
.tabbtn.active{color:var(--ink);border-bottom-color:var(--accent);}
.tabpanel{display:none;}
.tabpanel.active{display:block;}

.kpi-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:22px;}
.kpi{background:var(--panel);border:1px solid var(--line);border-top:3px solid var(--accent);border-radius:4px;padding:14px 16px;}
.kpi.flag-warn{border-top-color:var(--warn);}
.kpi.flag-bad{border-top-color:var(--bad);}
.kpi.flag-good{border-top-color:var(--good);}
.kpi-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-weight:500;margin-bottom:6px;}
.kpi-value{font-size:28px;font-weight:600;line-height:1;margin-bottom:3px;}
.kpi-value .unit{font-size:13px;color:var(--muted);font-weight:400;margin-left:3px;}
.kpi-sub{font-size:11.5px;color:var(--muted-dim);}
.kpi-sub.warn{color:var(--warn);}.kpi-sub.bad{color:var(--bad);}.kpi-sub.good{color:var(--good);}

.section{margin-bottom:26px;}
.section-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:12px;border-bottom:1px solid var(--line);padding-bottom:7px;flex-wrap:wrap;gap:6px;}
.section-head h2{font-size:15px;text-transform:uppercase;font-weight:600;}
.section-sub{font-size:11.5px;color:var(--muted-dim);}

.four-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;}
.dept-card{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:16px 18px;}
.dept-card-head{display:flex;align-items:center;gap:8px;margin-bottom:14px;}
.dept-color-bar{width:4px;height:20px;border-radius:2px;flex-shrink:0;}
.dept-card-head h3{font-size:13px;text-transform:uppercase;font-weight:600;font-family:'Oswald',sans-serif;}
.pct-bar-track{height:9px;background:#0F1318;border-radius:3px;overflow:hidden;}
.pct-bar-fill{height:100%;border-radius:3px;}
.pct-row{display:flex;justify-content:space-between;align-items:baseline;margin-top:5px;margin-bottom:12px;}
.big-pct{font-family:'Oswald',sans-serif;font-size:24px;font-weight:700;line-height:1;}
.pct-detail{font-size:11px;color:var(--muted-dim);}
.absent-block{border-top:1px solid var(--line);padding-top:10px;}
.absent-title{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:500;margin-bottom:6px;}
.absent-person{display:flex;align-items:center;gap:7px;font-size:12px;padding:3px 0;}
.absent-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;background:var(--bad);}
.a-station{font-size:11px;color:var(--muted-dim);margin-left:auto;}
.no-absent{font-size:12px;color:var(--good);display:flex;align-items:center;gap:5px;}
.no-absent::before{content:'\\2713';font-weight:700;}
.sched-note{font-size:11px;color:var(--muted-dim);margin-top:6px;}

.score-card{background:var(--panel);border:1px solid var(--line);border-radius:4px;overflow:hidden;}
.score-card-head{padding:10px 14px 8px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;}
.sc-dept{font-size:12px;text-transform:uppercase;font-family:'Oswald',sans-serif;font-weight:600;}
.dept-score-big{font-family:'Oswald',sans-serif;font-size:22px;font-weight:700;line-height:1;}
.score-meta{font-size:11.5px;color:var(--muted);padding:5px 14px 7px;border-bottom:1px solid var(--line);display:flex;gap:16px;flex-wrap:wrap;}
.score-meta b{color:var(--ink);font-weight:600;}
.score-row{display:flex;justify-content:space-between;align-items:center;padding:6px 14px;border-bottom:1px solid var(--line);font-size:12px;}
.score-row:last-child{border-bottom:none;}
.score-name{color:var(--ink);}
.score-detail{color:var(--muted-dim);font-size:10.5px;}
.score-pct{font-family:'Oswald',sans-serif;font-size:14px;font-weight:600;white-space:nowrap;margin-left:8px;}
.score-footer{padding:8px 14px;background:#0F1318;font-size:11px;color:var(--muted-dim);}

.panel{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:16px;}
.panel-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;}
.panel-header h3{font-size:13px;text-transform:uppercase;font-weight:600;}
.dept-badge{font-size:10px;font-weight:700;text-transform:uppercase;padding:2px 7px;border-radius:2px;font-family:'Oswald',sans-serif;letter-spacing:.06em;}
.badge-photo{background:var(--photo-dim);color:var(--photo);}
.badge-film{background:var(--film-dim);color:var(--film);}
.badge-video{background:var(--video-dim);color:var(--video);}
.badge-ops{background:var(--ops-dim);color:var(--ops);}
.panel-total{font-size:12px;color:var(--muted);margin-bottom:12px;}
.panel-total b{color:var(--ink);font-size:16px;font-family:'Oswald',sans-serif;}
.bucket-row{margin-bottom:10px;}
.bucket-top{display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;}
.bucket-top .bname{color:var(--muted);}
.bucket-top .bval{font-weight:600;color:var(--ink);}
.bar-track{height:7px;background:#0F1318;border-radius:2px;overflow:hidden;display:flex;}
.bar-fill{height:100%;}
.b-late{background:var(--bad);}.b-7{background:var(--warn);}.b-14{background:var(--accent);}.b-21{background:#6B7A99;}.b-28{background:var(--muted-dim);}
.legend-row{display:flex;gap:12px;margin-top:12px;padding-top:10px;border-top:1px solid var(--line);font-size:11px;color:var(--muted);flex-wrap:wrap;}
.legend-item{display:flex;align-items:center;gap:4px;}
.legend-dot{width:7px;height:7px;border-radius:50%;}
.alert-inline{font-size:11.5px;padding:5px 10px;border-radius:3px;display:block;margin-top:8px;}
.alert-inline.bad{background:var(--bad-dim);color:var(--bad);}
.alert-inline.warn{background:var(--warn-dim);color:var(--warn);}
.alert-inline.good{background:var(--good-dim);color:var(--good);}
.ops-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--line);font-size:12px;}
.ops-row:last-child{border-bottom:none;}
.ops-flag{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:5px;flex-shrink:0;}
.ops-flag.bad{background:var(--bad);}.ops-flag.warn{background:var(--warn);}.ops-flag.ok{background:var(--good);}
.o-meta{color:var(--muted-dim);font-size:10.5px;}
.o-hrs{font-family:'Oswald',sans-serif;font-size:13px;font-weight:600;white-space:nowrap;margin-left:8px;}

.week-data-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;}
.week-card{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:16px 18px;}
.week-card-title{font-size:11px;text-transform:uppercase;font-family:'Oswald',sans-serif;letter-spacing:.08em;color:var(--muted);margin-bottom:12px;font-weight:500;}
.week-stat{display:flex;justify-content:space-between;align-items:baseline;padding:5px 0;border-bottom:1px solid var(--line);font-size:12.5px;}
.week-stat:last-child{border-bottom:none;}
.week-stat .ws-label{color:var(--muted);}
.week-stat .ws-val{font-family:'Oswald',sans-serif;font-weight:600;font-size:14px;color:var(--ink);}
.week-total{display:flex;justify-content:space-between;align-items:baseline;padding:8px 0 0;margin-top:4px;font-size:13px;font-weight:600;}
.week-total .wt-label{color:var(--muted);font-family:'Oswald',sans-serif;font-size:12px;text-transform:uppercase;}
.week-total .wt-val{font-family:'Oswald',sans-serif;font-size:20px;color:var(--ink);}
.payroll-row{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid var(--line);font-size:11.5px;}
.payroll-row:last-child{border-bottom:none;}
.payroll-name{color:var(--ink);}
.payroll-hrs{color:var(--muted-dim);font-size:10.5px;}
.payroll-pay{font-family:'Oswald',sans-serif;font-weight:600;font-size:13px;color:var(--good);}

.action-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
.action-panel{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:16px;}
.action-panel.critical{border-top:2px solid var(--bad);}
.action-panel.watch{border-top:2px solid var(--warn);}
.action-panel.info{border-top:2px solid var(--accent);}
.action-head{display:flex;align-items:center;gap:9px;margin-bottom:11px;}
.a-icon{font-size:13px;font-family:'Oswald',sans-serif;font-weight:700;width:22px;height:22px;border-radius:3px;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.a-icon.bad{background:var(--bad-dim);color:var(--bad);}
.a-icon.warn{background:var(--warn-dim);color:var(--warn);}
.a-icon.info{background:var(--accent-dim);color:var(--accent);}
.action-head h3{font-size:13px;text-transform:uppercase;font-weight:600;line-height:1.2;}
.action-body{font-size:12.5px;color:var(--muted);line-height:1.6;}
.action-body b{color:var(--ink);}
.move-names{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px;}
.move-chip{font-size:11px;padding:2px 7px;border-radius:2px;background:var(--accent-dim);color:var(--accent);font-family:'Oswald',sans-serif;font-weight:500;}
.action-why{font-size:11px;color:var(--muted-dim);margin-top:8px;border-top:1px solid var(--line);padding-top:7px;font-style:italic;}

.trend-wrap{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start;}
.trend-panel{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:18px 20px;}
.trend-section-label{font-size:11px;color:var(--muted);margin-bottom:12px;text-transform:uppercase;letter-spacing:.06em;}
.tstat{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--line);padding-bottom:9px;margin-bottom:9px;}
.tstat:last-child{border-bottom:none;padding-bottom:0;margin-bottom:0;}
.tstat .tl{font-size:12px;color:var(--muted);}
.tstat .tv{font-family:'Oswald',sans-serif;font-size:17px;font-weight:600;}
.tstat .tv.warn{color:var(--warn);}.tstat .tv.bad{color:var(--bad);}.tstat .tv.good{color:var(--good);}
.trend-note{font-size:11.5px;color:var(--muted-dim);margin-top:10px;font-style:italic;line-height:1.5;}
.station-name{font-weight:500;}
table.cap{width:100%;border-collapse:collapse;}
table.cap th{position:sticky;top:0;text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:500;padding:8px 10px;border-bottom:1px solid var(--line);background:var(--panel-raised);}
table.cap td{padding:6px 10px;border-bottom:1px solid var(--line);font-size:12px;vertical-align:top;}
table.cap tr:last-child td{border-bottom:none;}
table.cap td.nr{text-align:right;font-family:'Oswald',sans-serif;font-weight:500;white-space:nowrap;}
footer{margin-top:32px;padding-top:14px;border-top:1px solid var(--line);font-size:11px;color:var(--muted-dim);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;}
@media(max-width:1100px){
  .kpi-strip,.four-grid,.week-data-grid{grid-template-columns:repeat(2,1fr);}
  .action-grid{grid-template-columns:1fr 1fr;}
  .trend-wrap{grid-template-columns:1fr;}
}
.capacity-wrap{background:var(--panel);border:1px solid var(--line);border-radius:4px;overflow:hidden;}
table.cap tr.dept-row td{background:#0F1318;padding:5px 10px;}
.dept-label{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;font-family:'Oswald',sans-serif;}
.gap-pill{display:inline-block;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:700;font-family:'Oswald',sans-serif;}
.gap-pill.bad{background:var(--bad-dim);color:var(--bad);}
.gap-pill.warn{background:var(--warn-dim);color:var(--warn);}
.gap-pill.good{background:var(--good-dim);color:var(--good);}
.train-chips{display:flex;flex-wrap:wrap;gap:3px;}
.chip{font-size:10px;padding:1px 6px;border-radius:2px;background:#28303C;color:var(--muted);font-family:'Oswald',sans-serif;letter-spacing:.03em;white-space:nowrap;}
.chip.assigned{background:var(--accent-dim);color:var(--accent);}
.chip.none{background:transparent;color:var(--muted-dim);font-style:italic;padding-left:0;}

.forecast-wrap{display:flex;flex-direction:column;gap:14px;}
.forecast-card{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:16px 18px;}
.forecast-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;}
.forecast-head h3{font-size:14px;text-transform:uppercase;font-weight:600;font-family:'Oswald',sans-serif;}
.forecast-meta{font-size:11px;color:var(--muted-dim);display:flex;gap:14px;flex-wrap:wrap;}
.forecast-meta b{color:var(--ink);}
.week-track{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;}
.week-cell{border-radius:3px;padding:8px 10px;border:1px solid var(--line);}
.week-cell .wk-label{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:4px;}
.week-cell .wk-nums{font-size:11px;color:var(--muted-dim);}
.week-cell .wk-nums b{color:var(--ink);font-family:'Oswald',sans-serif;}
.week-cell.status-on_track{border-left:3px solid var(--good);}
.week-cell.status-at_risk_late{border-left:3px solid var(--bad);background:rgba(217,89,76,0.06);}
.week-cell.status-at_risk_running_low{border-left:3px solid var(--warn);background:rgba(224,162,58,0.06);}
.week-cell.status-unknown{border-left:3px solid var(--muted-dim);}
.wk-status{font-size:10px;text-transform:uppercase;letter-spacing:.04em;font-weight:600;margin-top:4px;}
.wk-status.status-on_track{color:var(--good);}
.wk-status.status-at_risk_late{color:var(--bad);}
.wk-status.status-at_risk_running_low{color:var(--warn);}
.wk-status.status-unknown{color:var(--muted-dim);}
.constrain-pill{font-size:10px;font-weight:700;text-transform:uppercase;padding:2px 7px;border-radius:2px;font-family:'Oswald',sans-serif;letter-spacing:.05em;}
.constrain-pill.equipment{background:var(--film-dim);color:var(--film);}
.constrain-pill.staffing{background:var(--accent-dim);color:var(--accent);}
.constrain-pill.mixed{background:var(--warn-dim);color:var(--warn);}
.forecast-summary{font-size:11.5px;color:var(--muted-dim);margin-top:6px;border-top:1px solid var(--line);padding-top:8px;}

.why-wrap{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-bottom:24px;}
.why-card{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--muted-dim);border-radius:4px;padding:14px 16px;}
.why-card.cause-no_staff_assigned{border-left-color:var(--accent);}
.why-card.cause-underperformed_vs_expected{border-left-color:var(--warn);}
.why-card.cause-volume_exceeds_staffed_capacity{border-left-color:var(--bad);}
.why-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:6px;}
.why-head h4{font-size:13px;text-transform:uppercase;font-weight:600;font-family:'Oswald',sans-serif;}
.why-tags{display:flex;gap:5px;flex-wrap:wrap;}
.why-tag{font-size:10px;font-weight:700;text-transform:uppercase;padding:2px 7px;border-radius:2px;font-family:'Oswald',sans-serif;letter-spacing:.04em;background:#28303C;color:var(--muted);}
.why-tag.cause-no_staff_assigned{background:var(--accent-dim);color:var(--accent);}
.why-tag.cause-underperformed_vs_expected{background:var(--warn-dim);color:var(--warn);}
.why-tag.cause-volume_exceeds_staffed_capacity{background:var(--bad-dim);color:var(--bad);}
.why-tag.trend-up{background:var(--bad-dim);color:var(--bad);}
.why-tag.trend-down{background:var(--good-dim);color:var(--good);}
.why-tag.trend-newly_emerged{background:var(--bad-dim);color:var(--bad);}
.why-tag.trend-unchanged_at_risk{background:var(--warn-dim);color:var(--warn);}
.why-tag.trend-resolved{background:var(--good-dim);color:var(--good);}
.why-body{font-size:12px;color:var(--muted);line-height:1.6;}
"""

JS = """
function showTab(id, btn){
  document.querySelectorAll('.tabpanel').forEach(function(p){p.classList.remove('active');});
  document.querySelectorAll('.tabbtn').forEach(function(b){b.classList.remove('active');});
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}
"""

DEPT_COLOR = {"Photo": "photo", "Film": "film", "Video": "video", "Operations": "ops"}


def render_kpi_strip(d, n):
    k = d["kpi_summary"]
    backlog_delta = None
    if k.get("backlog_total") is not None and k.get("backlog_prev_entry") is not None:
        backlog_delta = k["backlog_total"] - k["backlog_prev_entry"]
    surplus = k.get("output_surplus_per_day")
    surplus_flag = "flag-bad" if (surplus is not None and surplus < 3000) else "flag-good" if surplus is not None else ""
    backlog_flag = "flag-bad" if (backlog_delta is not None and backlog_delta > 0) else "flag-good" if backlog_delta is not None else ""
    ops_gap = k.get("ops_present_scheduled_hours")
    ops_flag = "flag-bad" if (ops_gap is not None) else ""

    return f"""
<section class="kpi-strip">
  <div class="kpi {backlog_flag}">
    <div class="kpi-label">Total Backlog</div>
    <div class="kpi-value">{fnum(k.get('backlog_total'))}</div>
    <div class="kpi-sub">Checked in: {fnum(k.get('checked_in'))} &middot; Pending WSA: {fnum(k.get('pending_wsa'))}
      {f" &middot; {signed(backlog_delta)} vs {esc(k.get('backlog_prev_entry_date'))}" if backlog_delta is not None else ""}</div>
  </div>
  <div class="kpi {surplus_flag}">
    <div class="kpi-label">Output Surplus vs Inbound</div>
    <div class="kpi-value">{signed(surplus)}<span class="unit">/day</span></div>
    <div class="kpi-sub">Avg 10-day output {fnum(k.get('avg_10d_output'))} vs avg 10-day inbound {fnum(k.get('avg_10d_inbound'))}</div>
  </div>
  <div class="kpi {ops_flag}">
    <div class="kpi-label">Ops Staffing (Present Today)</div>
    <div class="kpi-value">{fnum(ops_gap, 1)}<span class="unit">hrs</span></div>
    <div class="kpi-sub">vs {fnum(d['ops']['totals'].get('hours_reqd_incl_new'), 2)}h required &middot; sheet gap {fnum(k.get('ops_gap_hrs_sheet'), 1)}h</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Slides / Photo Late</div>
    <div class="kpi-value">{fnum(k.get('photo_total_late_units'))}</div>
    <div class="kpi-sub">{fnum(k.get('photo_pct_late'), 1)}% of {fnum(k.get('photo_total_queue_units'))} checked-in units</div>
  </div>
</section>
"""


def render_staffing(d, n):
    cards = []
    for dept in ["Photo", "Film", "Video", "Operations"]:
        info = d["staffing"]["by_department"].get(dept)
        color = DEPT_COLOR.get(dept, "accent")
        if not info:
            continue
        pct_present = info.get("pct_present")
        pct_color = "var(--good)" if (pct_present or 0) >= 90 else "var(--warn)" if (pct_present or 0) >= 60 else "var(--bad)"
        absent_html = '<div class="no-absent">No absences — full shift</div>' if not info["absent"] else "".join(
            f'<div class="absent-person"><span class="absent-dot"></span><span>{esc(p["name"])}</span><span class="a-station">{esc(p.get("station") or "")}</span></div>'
            for p in info["absent"]
        )
        note = n.get("dept_schedule_notes", {}).get(dept, "")
        cards.append(f"""
    <div class="dept-card">
      <div class="dept-card-head"><div class="dept-color-bar" style="background:var(--{color})"></div><h3>{esc(dept)}</h3></div>
      <div class="pct-bar-track"><div class="pct-bar-fill" style="width:{pct_present or 0}%;background:{pct_color}"></div></div>
      <div class="pct-row"><div class="big-pct" style="color:{pct_color}">{fnum(pct_present, 0) if pct_present is not None else '—'}%</div><div class="pct-detail">{info['present_count']} of {info['scheduled_count']} scheduled present</div></div>
      <div class="absent-block">
        <div class="absent-title">Absent Today</div>
        {absent_html}
        {f'<div class="sched-note">{esc(note)}</div>' if note else ''}
      </div>
    </div>""")
    return f"""
<section class="section">
  <div class="section-head"><h2>Staffing Status by Department</h2><span class="section-sub">{esc(d['meta']['weekday'])} &middot; Staffing tab</span></div>
  <div class="four-grid">{''.join(cards)}</div>
</section>
"""


def render_scores(d, n):
    cards = []
    for dept in ["Photo", "Film", "Video", "Operations"]:
        info = d["scores"].get(dept)
        if not info:
            continue
        color = DEPT_COLOR.get(dept, "accent")
        score_val = info.get("score") or "—"
        score_num = 0
        try:
            score_num = float(str(score_val).replace("%", ""))
        except ValueError:
            pass
        score_color = "var(--good)" if score_num >= 100 else "var(--warn)" if score_num >= 85 else "var(--bad)"
        rows = ""
        for p in sorted(info.get("people", []), key=lambda x: -(x.get("pct") or 0)):
            pc = p.get("pct")
            pcolor = "var(--good)" if (pc or 0) >= 100 else "var(--warn)" if (pc or 0) >= 85 else "var(--bad)"
            rows += f"""<div class="score-row"><div class="score-left"><div class="score-name">{esc(p['name'])}</div>
              <div class="score-detail">{fnum(p.get('scheduled'),2)}h sched &middot; {fnum(p.get('actual'),2)}h actual</div></div>
              <div class="score-pct" style="color:{pcolor}">{fnum(pc,0) if pc is not None else '—'}%</div></div>"""
        footer = n.get("score_footers", {}).get(dept, "")
        cards.append(f"""
    <div class="score-card">
      <div class="score-card-head"><span class="sc-dept" style="color:var(--{color})">{esc(dept)}</span>
        <span class="dept-score-big" style="color:{score_color}">{esc(score_val)}</span></div>
      <div class="score-meta"><span>Attendance <b>{esc(info.get('attendance') or '—')}</b></span>{f"<span>Output <b>{fnum(info.get('output'))}</b></span>" if info.get('output') else ''}</div>
      {rows}
      {f'<div class="score-footer">{esc(footer)}</div>' if footer else ''}
    </div>""")
    return f"""
<section class="section">
  <div class="section-head"><h2>Yesterday's Performance Scores</h2><span class="section-sub">Yesterday Scores tab</span></div>
  <div class="four-grid">{''.join(cards)}</div>
</section>
"""


def render_queue_bucket_panel(title, badge_class, badge_label, categories, total_units, alerts):
    rows = ""
    for c in categories:
        segs = ""
        if c.get("late"):
            segs += f'<div class="bar-fill b-late" style="width:{c["pct_late"]}%"></div>'
        segs += f'<div class="bar-fill b-7" style="width:{c["pct_7d"]}%"></div>'
        segs += f'<div class="bar-fill b-14" style="width:{c["pct_14d"]}%"></div>'
        segs += f'<div class="bar-fill b-21" style="width:{c["pct_21d"]}%"></div>'
        segs += f'<div class="bar-fill b-28" style="width:{c["pct_28d"]}%"></div>'
        late_note = f' &middot; <b style="color:var(--bad)">{fnum(c["late"])} late</b>' if c.get("late") else " &middot; 0 late"
        rows += f"""<div class="bucket-row"><div class="bucket-top"><span class="bname">{esc(c['name'])}</span>
          <span class="bval">{fnum(c['total'])}{late_note}</span></div>
          <div class="bar-track">{segs}</div></div>"""
    alert_html = "".join(f'<div class="alert-inline {a["level"]}">{esc(a["text"])}</div>' for a in alerts)
    return f"""
    <div class="panel">
      <div class="panel-header"><h3>{esc(title)}</h3><span class="dept-badge {badge_class}">{esc(badge_label)}</span></div>
      <div class="panel-total"><b>{fnum(total_units)}</b> total units</div>
      {rows}
      <div class="legend-row">
        <div class="legend-item"><span class="legend-dot" style="background:var(--bad)"></span>Late</div>
        <div class="legend-item"><span class="legend-dot" style="background:var(--warn)"></span>Wk1 (0-6d)</div>
        <div class="legend-item"><span class="legend-dot" style="background:var(--accent)"></span>Wk2 (7-13d)</div>
        <div class="legend-item"><span class="legend-dot" style="background:#6B7A99"></span>Wk3 (14-20d)</div>
        <div class="legend-item"><span class="legend-dot" style="background:var(--muted-dim)"></span>Wk4 (21-25d)</div>
      </div>
      {alert_html}
    </div>"""


def render_queues(d, n):
    photo = d["queues"]["photo"]
    film = d["queues"]["film"]
    video = d["queues"]["video"]
    ops = d["ops"]

    photo_alerts = n.get("queue_alerts", {}).get("photo", [])
    film_alerts = n.get("queue_alerts", {}).get("film", [])

    photo_panel = render_queue_bucket_panel("Photo Queue", "badge-photo", "Photo", photo,
                                             sum(c["total"] for c in photo), photo_alerts)
    film_panel = render_queue_bucket_panel("Film Queue", "badge-film", "Film", film,
                                            sum(c["total"] for c in film), film_alerts)

    video_alerts = [{"level": "good", "text": f"{fnum(video.get('due_7d_total'))} tapes due within 7 days (Wk1)."}]
    if (video.get("current_lates") or 0) > 0:
        video_alerts.insert(0, {"level": "bad", "text": f"{fnum(video.get('current_lates'))} tapes already late."})
    video_panel = render_queue_bucket_panel("Video Queue", "badge-video", "Video", video.get("types", []),
                                             video.get("total_tapes"), video_alerts)

    ops_rows = ""
    for t in sorted(ops["tasks"], key=lambda x: -x["hrs_reqd"])[:9]:
        flag = "bad" if t["hrs_reqd"] >= 10 else "warn" if t["hrs_reqd"] >= 2 else "ok"
        ops_rows += f"""<div class="ops-row"><div><span class="ops-flag {flag}"></span><b style="font-size:12.5px;">{esc(t['task'])}</b>
          <div class="o-meta">{fnum(t['order_count'])} orders{f" &middot; oldest {esc(t['oldest_date'])}" if t['oldest_date'] else ''}</div></div>
          <span class="o-hrs" style="color:var(--{flag if flag!='ok' else 'good'});">{fnum(t['hrs_reqd'],2)}h</span></div>"""
    tot = ops["totals"]
    ops_panel = f"""
    <div class="panel">
      <div class="panel-header"><h3>Operations Queue</h3><span class="dept-badge badge-ops">Ops</span></div>
      <div class="panel-total"><b style="color:var(--bad)">{fnum(tot.get('hours_reqd_incl_new'),2)}h required</b> &middot; {fnum(d['staffing']['by_department'].get('Operations',{}).get('scheduled_hours_total'),1)}h present</div>
      {ops_rows}
      <div style="margin-top:10px;padding-top:8px;border-top:1px solid var(--line);font-size:11.5px;color:var(--muted);">
        Gap (present staff): <b style="color:var(--bad);">{fnum(tot.get('gap_hrs'),1)}h (sheet)</b>
      </div>
    </div>"""

    return f"""
<section class="section">
  <div class="section-head"><h2>Queue Status — All Departments</h2><span class="section-sub">{esc(d['meta']['date_display'])}</span></div>
  <div class="four-grid">{photo_panel}{film_panel}{video_panel}{ops_panel}</div>
</section>
"""


def render_week_tab(d, n):
    w = d["week"]
    inbound_rows = "".join(f'<div class="week-stat"><span class="ws-label">{esc(k)}</span><span class="ws-val">{fnum(v)}</span></div>'
                            for k, v in w["this_week_inbound"].items())
    lwo = w["last_week_output"]
    out_media_rows = "".join(f'<div class="week-stat"><span class="ws-label">{esc(k)}</span><span class="ws-val">{fnum(v)}</span></div>'
                              for k, v in lwo.get("media_breakdown", {}).items())
    out_combined_rows = "".join(f'<div class="week-stat"><span class="ws-label">{esc(k)}</span><span class="ws-val">{fnum(v)}</span></div>'
                                 for k, v in lwo.get("combined", {}).items())
    rev_rows = "".join(f'<div class="week-stat"><span class="ws-label">{esc(k)}</span><span class="ws-val good">${fnum(v)}</span></div>'
                        for k, v in w["last_week_revenue"].items() if k != "Total")

    # Full payroll list (all employees, not truncated). Per-person dollar
    # pay is intentionally NOT shown here -- only hours per person, with the
    # combined hours + dollar total at the bottom. Individual compensation
    # stays out of the published dashboard; the aggregate total doesn't
    # attribute pay to any one person.
    payroll = sorted(w["last_week_payroll"], key=lambda p: -p["hours"])
    payroll_rows = "".join(f'<div class="payroll-row"><div class="payroll-name">{esc(p["name"])}</div><div class="payroll-pay">{fnum(p["hours"],2)}h</div></div>'
                            for p in payroll)
    pt = w.get("last_week_payroll_total") or {}

    # Department hours
    dept_hours_rows = "".join(f'<div class="week-stat"><span class="ws-label">{esc(k.title())}</span><span class="ws-val">{fnum(v,2)}h</span></div>'
                               for k, v in w.get("last_week_dept_hours", {}).items())

    # Late rate + order prefix breakdown
    lr = w.get("late_rates", {})
    prefix = w.get("late_rates_prefix", {})
    # Order counts (Quantity On-Time / Quantity Late / Total Orders)
    late_rows = ""
    for label, key in [("On-Time Orders", "Quantity On-Time"), ("Late Orders", "Quantity Late"),
                        ("Total Orders", "Total Orders")]:
        if lr.get(key) not in (None, ""):
            cls = "good" if key == "Quantity On-Time" else "warn" if key == "Quantity Late" else ""
            late_rows += f'<div class="week-stat"><span class="ws-label">{esc(label)}</span><span class="ws-val {cls}">{esc(lr.get(key))}</span></div>'

    # True rate percentages: Late Orders % = Late/Total, On-Time Orders % = On-Time/Total
    pct_divider = ""
    pct_rows = ""
    if lr.get("pct_late_computed") is not None or lr.get("pct_on_time_computed") is not None:
        pct_divider = '<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--line);font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted-dim);">Rate</div>'
        if lr.get("pct_on_time_computed") is not None:
            pct_rows += f'<div class="week-stat"><span class="ws-label">On-Time Orders %</span><span class="ws-val good">{fnum(lr.get("pct_on_time_computed"),1)}%</span></div>'
        if lr.get("pct_late_computed") is not None:
            pct_rows += f'<div class="week-stat"><span class="ws-label">Late Orders %</span><span class="ws-val warn">{fnum(lr.get("pct_late_computed"),1)}%</span></div>'

    # Day-count-vs-estimated-TAT figures — NOT percentages, kept as a separate
    # labeled group so they're not mistaken for the rate above.
    tat_divider = ""
    tat_rows = ""
    for label, key in [("Late Orders — Avg Days vs Est. TAT", "Late Orders"),
                        ("On-Time Orders — Avg Days vs Est. TAT", "On-Time Orders"),
                        ("Overall Average — Days vs Est. TAT", "Overall Average")]:
        if lr.get(key) not in (None, ""):
            tat_rows += f'<div class="week-stat"><span class="ws-label">{esc(label)}</span><span class="ws-val">{esc(lr.get(key))}</span></div>'
    if tat_rows:
        tat_divider = '<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--line);font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted-dim);">Day Count vs Estimated TAT</div>'

    prefix_rows = "".join(f'<div class="week-stat"><span class="ws-label">{esc(k)}</span><span class="ws-val">{fnum(v, 0)}</span></div>' for k, v in prefix.items())
    prefix_divider = '<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--line);font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted-dim);">By Order Prefix</div>' if prefix_rows else ""

    return f"""
<section class="section">
  <div class="section-head"><h2>Week at a Glance</h2><span class="section-sub">Week Data tab &middot; full breakdown</span></div>
  <div class="week-data-grid">
    <div class="week-card"><div class="week-card-title">This Week — Inbound Media (so far)</div>{inbound_rows}
      <div style="margin-top:8px;font-size:11px;color:var(--muted-dim);">{fnum(w.get('this_week_orders'))} orders &middot; ${fnum(w.get('this_week_gross'))} gross</div></div>
    <div class="week-card"><div class="week-card-title">Last Week — Pieces Made Online</div>{out_media_rows}
      <div class="week-total"><span class="wt-label">Photo Total</span><span class="wt-val">{fnum(lwo.get('media_breakdown_total'))}</span></div>
      <div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--line);font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted-dim);">By Department</div>
      {out_combined_rows}
      <div class="week-total"><span class="wt-label">Total Output</span><span class="wt-val">{fnum(lwo.get('combined_total'))}</span></div></div>
    <div class="week-card"><div class="week-card-title">Last Week — Revenue by Media</div>{rev_rows}
      <div class="week-total"><span class="wt-label">Total Revenue</span><span class="wt-val" style="color:var(--good)">${fnum(w['last_week_revenue'].get('Total'))}</span></div></div>
    <div class="week-card"><div class="week-card-title">Last Week — Department Hours</div>{dept_hours_rows}</div>
    <div class="week-card"><div class="week-card-title">Last Week — Order Late Rate</div>{late_rows}{pct_divider}{pct_rows}{tat_divider}{tat_rows}{prefix_divider}{prefix_rows}</div>
    <div class="week-card" style="grid-column:span 3;"><div class="week-card-title">Last Week — Payroll (hours by person; totals below)</div>
      <div style="max-height:340px;overflow-y:auto;padding-right:10px;">{payroll_rows}</div>
      <div class="week-total"><span class="wt-label">Total</span><span class="wt-val">{fnum(pt.get('hours'),1)}h &middot; ${fnum(pt.get('pay'))}</span></div></div>
  </div>
</section>
"""


def render_overview_tab(d, n):
    k = d["kpi_summary"]
    banner = n.get("status_banner", "")
    severity = n.get("status_severity", "warn")

    moves_html = ""
    for m in n.get("suggested_moves", []):
        sev = m.get("severity", "info")
        icon = "!" if sev == "critical" else ("▲" if sev == "watch" else "i")
        iconclass = "bad" if sev == "critical" else ("warn" if sev == "watch" else "info")
        panelclass = "critical" if sev == "critical" else ("watch" if sev == "watch" else "info")
        chips = "".join(f'<span class="move-chip">{esc(c)}</span>' for c in m.get("chips", []))
        moves_html += f"""
    <div class="action-panel {panelclass}">
      <div class="action-head"><div class="a-icon {iconclass}">{icon}</div><h3>{esc(m.get('title',''))}</h3></div>
      <div class="action-body">{m.get('body_html', esc(m.get('body','')))}</div>
      {f'<div class="move-names">{chips}</div>' if chips else ''}
      {f'<div class="action-why">{esc(m.get("why",""))}</div>' if m.get('why') else ''}
    </div>"""

    te = d["turn_estimate"]["history"]
    hist_rows = ""
    for e in te[:8]:
        hist_rows += f'<div class="tstat"><span class="tl">{esc(e["date"])}</span><span class="tv">{fnum(e["total_backlog"])}</span></div>'

    notes = n.get("notes_from_floor") or d.get("daily_notes") or []
    notes_html = ""
    if notes:
        notes_html = f"""
<section class="section">
  <div class="section-head"><h2>Notes From The Floor</h2><span class="section-sub">Daily Notes tab &middot; polished for clarity</span></div>
  <div class="panel">
    {''.join(f'<div style="padding:8px 0;border-bottom:1px solid var(--line);font-size:12.5px;color:var(--muted);line-height:1.6;">{esc(note)}</div>' for note in notes)}
  </div>
</section>"""

    return f"""
<section class="section">
  <div class="section-head"><h2>Status Overview</h2></div>
  <div class="status-pill {severity}"><span class="dot {severity}"></span>{esc(banner)}</div>
</section>
{notes_html}
<section class="section">
  <div class="section-head"><h2>Suggested Moves &amp; AI Insights</h2><span class="section-sub">Generated from today's computed metrics + Daily Notes</span></div>
  <div class="action-grid">{moves_html}</div>
</section>
<section class="section">
  <div class="trend-wrap">
    <div class="trend-panel">
      <div class="trend-section-label">Key Numbers — Today</div>
      <div class="tstat"><span class="tl">Backlog today</span><span class="tv bad">{fnum(k.get('backlog_total'))}</span></div>
      <div class="tstat"><span class="tl">Checked in</span><span class="tv">{fnum(k.get('checked_in'))}</span></div>
      <div class="tstat"><span class="tl">Pending WSA</span><span class="tv">{fnum(k.get('pending_wsa'))}</span></div>
      <div class="tstat"><span class="tl">Avg 10-day output</span><span class="tv">{fnum(k.get('avg_10d_output'))}</span></div>
      <div class="tstat"><span class="tl">Avg 10-day inbound</span><span class="tv">{fnum(k.get('avg_10d_inbound'))}</span></div>
      <div class="tstat"><span class="tl">Output surplus</span><span class="tv {'good' if (k.get('output_surplus_per_day') or 0) > 0 else 'bad'}">{signed(k.get('output_surplus_per_day'))}/day</span></div>
      <div class="trend-note">{esc(n.get('trend_note',''))}</div>
    </div>
    <div class="trend-panel">
      <div class="trend-section-label">Backlog — Recent History (Turn Estimate tab)</div>
      {hist_rows}
      <div class="trend-note">{esc(n.get('projection_note',''))}</div>
    </div>
  </div>
</section>
"""


FLAG_LABEL = {"critical": ("bad", "Critical"), "watch": ("warn", "Watch"), "stable": ("good", "Stable")}
CAP_DEPT_COLOR = {"photo": "photo", "film": "film", "video": "video", "operations": "ops"}
CAP_DEPT_LABEL = {"photo": "Photo", "film": "Film", "video": "Video", "operations": "Operations"}


def render_staffing_capacity_tab(d, n):
    cap = d.get("station_capacity", {})
    rows_html = ""
    for dept_key in ["photo", "film", "video", "operations"]:
        dept_rows = cap.get(dept_key, [])
        if not dept_rows:
            continue
        color = CAP_DEPT_COLOR[dept_key]
        rows_html += f'<tr class="dept-row"><td colspan="6"><span class="dept-label" style="color:var(--{color})">{esc(CAP_DEPT_LABEL[dept_key])}</span></td></tr>'
        for row in dept_rows:
            assigned = row["assigned"]
            assigned_chips = []
            for a in assigned:
                hrs_suffix = f" ({fnum(a.get('hours'), 2)}h)" if a.get("hours") else ""
                assigned_chips.append(f'<span class="chip assigned">{esc(a["name"])}{esc(hrs_suffix)}</span>')
            assigned_html = "".join(assigned_chips) or '<span class="chip none">Unassigned</span>'
            backup = row["cross_trained_backup"]
            backup_html = "".join(f'<span class="chip">{esc(b)}</span>' for b in backup) or '<span class="chip none">No backup identified</span>'
            out_day = row.get("output_day")
            out_cell = fnum(out_day) if out_day is not None else "—"
            if dept_key == "operations":
                status = f'{fnum(row.get("queue_total"))} orders &middot; {fnum(row.get("hrs_reqd"),2)}h required'
            else:
                late = row.get("queue_late") or 0
                status = f'{fnum(row.get("queue_total"))}'
                if late:
                    status += f' &middot; <b style="color:var(--bad)">{fnum(late)} late</b>'
                else:
                    status += ' &middot; 0 late &#x2713;'
                due7 = row.get("queue_due_7d")
                if due7:
                    status += f' &middot; {fnum(due7)} due &le;7d'
            flag_cls, flag_label = FLAG_LABEL.get(row["flag"], ("neutral", row["flag"].title()))
            rows_html += f"""<tr>
              <td></td><td class="station-name">{esc(row['station'])}</td>
              <td><div class="train-chips">{assigned_html}</div></td>
              <td><div class="train-chips">{backup_html}</div></td>
              <td class="nr">{out_cell}</td>
              <td class="nr">{status}</td>
              <td><span class="gap-pill {flag_cls}">{esc(flag_label)}</span></td>
            </tr>"""
    return f"""
<section class="section">
  <div class="section-head"><h2>Station Capacity &amp; Coverage Detail</h2><span class="section-sub">Staffed today &middot; cross-training &middot; output rate &middot; queue &amp; age status</span></div>
  <div class="capacity-wrap">
    <table class="cap">
      <thead><tr>
        <th style="width:4px;padding:8px 4px;"></th>
        <th>Station</th><th>Assigned Today</th><th>Cross-Trained Backup</th>
        <th class="nr">Output/Day</th><th class="nr">Queue &amp; Status</th><th>Flag</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</section>
"""


FORECAST_GROUP_DEPT = {
    "Negatives": "photo", "Slides": "photo", "Paper": "photo", "Special": "photo",
    "Film Splice": "film", "Film Capture": "film", "Film Edit": "film",
    "Video": "video",
}
FORECAST_DEPT_ORDER = ["photo", "film", "video"]
FORECAST_DEPT_LABEL = {"photo": "Photo", "film": "Film", "video": "Video"}
STATUS_LABEL = {
    "on_track": "On Track", "at_risk_late": "At Risk of Late",
    "at_risk_running_low": "At Risk of Running Low", "unknown": "No Output Data",
}
WEEK_LABEL = {1: "Week 1 (0-6d)", 2: "Week 2 (7-13d)", 3: "Week 3 (14-20d)", 4: "Week 4 (21-25d)"}


def _forecast_recommendation(g):
    weeks = g["weeks"]
    late_weeks = [w for w in weeks if w["status"] == "at_risk_late"]
    low_weeks = [w for w in weeks if w["status"] == "at_risk_running_low"]
    cb = g.get("constrained_by")
    if late_weeks:
        first = late_weeks[0]["week"]
        if cb == "equipment":
            return (f"At risk of falling behind starting Week {first} — running near equipment ceiling "
                     f"({fnum(g['utilization_vs_equipment_pct'],0)}% of max) with "
                     f"{fnum(g['equipment_stations_down'])} of {fnum(g['equipment_stations_total'])} stations down. "
                     f"Equipment is the likely constraint — repair/replace before adding staff here.")
        if cb == "staffing":
            return (f"At risk of falling behind starting Week {first} — only using "
                     f"{fnum(g['utilization_vs_equipment_pct'],0)}% of equipment capacity. "
                     f"Staffing is the likely constraint — more hours or headcount here would help before new equipment.")
        if cb == "mixed":
            return (f"At risk of falling behind starting Week {first}, using "
                     f"{fnum(g['utilization_vs_equipment_pct'],0)}% of equipment capacity — "
                     f"neither staffing nor equipment has clear headroom; worth a closer look at both.")
        return f"At risk of falling behind starting Week {first} — no output data to pin down staffing vs. equipment."
    if low_weeks:
        first = low_weeks[0]["week"]
        return (f"Capacity is outpacing this queue — could clear the entire current backlog well within the "
                 f"4-week window (crosses over around Week {first}). Consider redirecting staff elsewhere before "
                 f"backing off on hours here.")
    return "On track through the 4-week window at current staffing and equipment levels."


CAUSE_LABEL = {
    "no_staff_assigned": "No Staff Assigned",
    "underperformed_vs_expected": "Below Expected Output",
    "volume_exceeds_staffed_capacity": "Volume Exceeds Capacity",
}
LATE_TREND_LABEL = {"up": "Late Count Rising", "down": "Late Count Falling", "flat": "Late Count Flat"}
WEEK1_TREND_LABEL = {
    "newly_emerged": "Newly At Risk", "resolved": "Resolved Since Last Run",
    "unchanged_at_risk": "Still Carrying Over", "changed": "Status Changed",
}


def _why_fallback_body(g):
    """Mechanical fallback sentence if narrative.json didn't cover this
    group -- keeps the section honest/non-empty rather than silently
    dropping a flagged station."""
    parts = []
    if "no_staff_assigned" in g["causes"]:
        parts.append("No one was logged against this station today.")
    if "underperformed_vs_expected" in g["causes"]:
        eo = g.get("expected_output_today")
        ao = g.get("staffed_daily_capacity")
        parts.append(f"Actual output ({fnum(ao)}) came in well under the expected total for today's assigned staff ({fnum(eo)}).")
    if "volume_exceeds_staffed_capacity" in g["causes"]:
        parts.append("Staffing and output look normal -- the volume currently due simply exceeds what today's staffed rate can clear.")
    if g.get("week1_status_trend") == "unchanged_at_risk":
        parts.append("This has carried over from the last run, not a new issue.")
    elif g.get("week1_status_trend") == "newly_emerged":
        parts.append("This is newly at risk -- it was on track as of the last run.")
    return " ".join(parts) or "No specific cause identified from today's numbers."


def render_why_behind(d, n):
    groups = d.get("capacity_forecast", [])
    explanations = {e.get("group"): e for e in n.get("capacity_explanations", [])}
    flagged = [g for g in groups if g["causes"] or g.get("week1_status_trend") in ("newly_emerged", "unchanged_at_risk")]
    if not flagged:
        return ""
    cards = ""
    for g in flagged:
        primary_cause = g["causes"][0] if g["causes"] else None
        card_class = f"cause-{primary_cause}" if primary_cause else ""
        tags = "".join(f'<span class="why-tag cause-{c}">{esc(CAUSE_LABEL.get(c, c))}</span>' for c in g["causes"])
        lt = g.get("late_trend")
        if lt in LATE_TREND_LABEL:
            tags += f'<span class="why-tag trend-{lt}">{esc(LATE_TREND_LABEL[lt])}</span>'
        wt = g.get("week1_status_trend")
        if wt in WEEK1_TREND_LABEL:
            tags += f'<span class="why-tag trend-{wt}">{esc(WEEK1_TREND_LABEL[wt])}</span>'
        exp = explanations.get(g["name"])
        body = exp.get("body_html") if exp else None
        if not body:
            body = _why_fallback_body(g)
        headline = (exp.get("headline") if exp else None) or g["name"]
        cards += f"""
        <div class="why-card {card_class}">
          <div class="why-head"><h4>{esc(headline)}</h4><div class="why-tags">{tags}</div></div>
          <div class="why-body">{body if exp and exp.get('body_html') else esc(body)}</div>
        </div>"""
    return f"""
<section class="section">
  <div class="section-head"><h2>Why We're Behind (or Suddenly Not)</h2>
  <span class="section-sub">Performance vs. staffing vs. backlog volume, plus carry-over vs. newly-emerged status</span></div>
  <div class="why-wrap">{cards}</div>
</section>
"""


def render_capacity_forecast_tab(d, n):
    groups = d.get("capacity_forecast", [])
    by_name = {g["name"]: g for g in groups}
    why_html = render_why_behind(d, n)
    dept_html = ""
    for dept in FORECAST_DEPT_ORDER:
        names = [name for name, dp in FORECAST_GROUP_DEPT.items() if dp == dept]
        cards = ""
        for name in names:
            g = by_name.get(name)
            if not g:
                continue
            util = g.get("utilization_vs_equipment_pct")
            cb = g.get("constrained_by")
            cb_pill = f'<span class="constrain-pill {cb}">{esc(cb)}-bound</span>' if cb else ""
            week_cells = ""
            for w in g["weeks"]:
                status = w["status"]
                week_cells += f"""<div class="week-cell status-{status}">
                  <div class="wk-label">{esc(WEEK_LABEL[w['week']])}</div>
                  <div class="wk-nums">Due by then: <b>{fnum(w['due_cumulative'])}</b></div>
                  <div class="wk-nums">Staffed cap: <b>{fnum(w['staffed_capacity_cumulative'])}</b></div>
                  <div class="wk-status status-{status}">{esc(STATUS_LABEL.get(status, status))}</div>
                </div>"""
            equip_note = (f"{fnum(g['equipment_stations_total'])} stations "
                           f"({fnum(g['equipment_stations_down'])} down)" if g["equipment_stations_total"] else "no equipment data")
            cards += f"""
        <div class="forecast-card">
          <div class="forecast-head">
            <h3>{esc(name)}</h3>
            {cb_pill}
          </div>
          <div class="forecast-meta">
            <span>Total queue: <b>{fnum(g['total_queue'])}</b></span>
            <span>Late now: <b style="color:var(--bad)">{fnum(g['late'])}</b></span>
            <span>Staffed/day: <b>{fnum(g['staffed_daily_capacity']) if g['staffed_daily_capacity'] is not None else '—'}</b></span>
            <span>Equipment ceiling/day: <b>{fnum(g['equipment_daily_capacity'])}</b> &middot; {equip_note}</span>
            <span>Utilization vs. equipment: <b>{fnum(util,0) + '%' if util is not None else '—'}</b></span>
          </div>
          <div class="week-track">{week_cells}</div>
          <div class="forecast-summary">{esc(_forecast_recommendation(g))}</div>
        </div>"""
        if cards:
            dept_html += f"""
    <div class="section">
      <div class="section-head"><h2>{esc(FORECAST_DEPT_LABEL[dept])}</h2></div>
      <div class="forecast-wrap">{cards}</div>
    </div>"""
    return f"""
<section class="section">
  <div class="section-head"><h2>Capacity &amp; Forecast — Next 4 Weeks</h2>
  <span class="section-sub">Due-date buckets vs. today's staffed output and equipment ceiling &middot; Station Capacity tab</span></div>
  <div style="font-size:11.5px;color:var(--muted-dim);margin-bottom:16px;">
    Projections assume each station's current daily output stays constant and is fully dedicated to that station
    across a 5-day work week — a directional signal, not a literal schedule. "At Risk of Late" means projected
    output can't clear what's due by that week at today's pace. "At Risk of Running Low" means capacity would
    clear the entire current queue with room to spare, a signal this station could be overstaffed relative to
    its own backlog or ready to help elsewhere.
  </div>
  {why_html}
  {dept_html}
</section>
"""


LATE_ORDER_CATS = [
    ("slides", "Slides", "photo"), ("negatives", "Negatives", "photo"),
    ("special", "Special", "photo"), ("paper", "Paper", "photo"),
]


def render_late_orders_tab(d, n):
    plo = d.get("photo_late_orders", {})
    cards = []
    for key, label, color in LATE_ORDER_CATS:
        block = plo.get(key, {"entries": [], "count": 0, "total_quantity": 0})
        rows = "".join(
            f'<tr><td>{esc(e["order_id"])}</td><td>{esc(e["due_date"])}</td>'
            f'<td class="nr">{fnum(e.get("quantity"))}</td><td>{esc(e.get("storage_location") or "")}</td></tr>'
            for e in block["entries"]
        )
        cards.append(f"""
    <div class="panel">
      <div class="panel-header"><h3>{esc(label)}</h3><span class="dept-badge badge-{color}">{fnum(block['count'])} orders</span></div>
      <div class="panel-total"><b>{fnum(block.get('total_quantity'))}</b> units late</div>
      <div style="max-height:480px;overflow-y:auto;border:1px solid var(--line);border-radius:4px;">
        <table class="cap" style="width:100%;">
          <thead><tr><th>Order ID</th><th>Due Date</th><th class="nr">Qty</th><th>Storage</th></tr></thead>
          <tbody>{rows if rows else '<tr><td colspan="4" style="color:var(--good);padding:10px 14px;">No late orders &#x2713;</td></tr>'}</tbody>
        </table>
      </div>
    </div>""")
    return f"""
<section class="section">
  <div class="section-head"><h2>Late Orders — Photo</h2><span class="section-sub">Photo Late Orders tab &middot; oldest due date first</span></div>
  <div class="four-grid">{''.join(cards)}</div>
</section>
"""


def main():
    if len(sys.argv) != 4:
        print("Usage: render_dashboard.py <data.json> <narrative.json> <out.html>", file=sys.stderr)
        sys.exit(1)
    data_path, narrative_path, out_path = sys.argv[1:4]
    d = json.load(open(data_path, encoding="utf-8"))
    n = json.load(open(narrative_path, encoding="utf-8"))

    today_body = render_kpi_strip(d, n) + render_staffing(d, n) + render_queues(d, n) + render_scores(d, n)
    week_body = render_week_tab(d, n)
    staffing_capacity_body = render_staffing_capacity_tab(d, n)
    late_orders_body = render_late_orders_tab(d, n)
    forecast_body = render_capacity_forecast_tab(d, n)
    overview_body = render_overview_tab(d, n)

    banner_severity = n.get("status_severity", "warn")
    banner_text = n.get("status_banner", "")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Production Dashboard — {esc(d['meta']['date_display'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<header>
  <div>
    <div class="eyebrow">Production Operations &middot; Daily Dashboard</div>
    <h1>Floor Status — {esc(d['meta']['weekday'])}</h1>
  </div>
  <div class="meta-block">
    <div class="big-date">{esc(d['meta']['date_display'])} &middot; Morning Pull</div>
    <div>Source: Production and Operations Dashboard (Google Sheet)</div>
    <div class="status-pill {banner_severity}"><span class="dot {banner_severity}"></span>{esc(banner_text)}</div>
  </div>
</header>

<div class="tabbar">
  <button class="tabbtn active" onclick="showTab('tab-today', this)">Today</button>
  <button class="tabbtn" onclick="showTab('tab-week', this)">Week</button>
  <button class="tabbtn" onclick="showTab('tab-staffing', this)">Staffing</button>
  <button class="tabbtn" onclick="showTab('tab-late-orders', this)">Late Orders</button>
  <button class="tabbtn" onclick="showTab('tab-forecast', this)">Capacity &amp; Forecast</button>
  <button class="tabbtn" onclick="showTab('tab-overview', this)">Overview &amp; AI Insights</button>
</div>

<div id="tab-today" class="tabpanel active">{today_body}</div>
<div id="tab-week" class="tabpanel">{week_body}</div>
<div id="tab-staffing" class="tabpanel">{staffing_capacity_body}</div>
<div id="tab-late-orders" class="tabpanel">{late_orders_body}</div>
<div id="tab-forecast" class="tabpanel">{forecast_body}</div>
<div id="tab-overview" class="tabpanel">{overview_body}</div>

<footer>
  <div>Source: Production and Operations Dashboard &middot; Google Sheets (Photo Queue, Film Queue, Video Queue, Ops, Staffing, Yesterday Scores, Week Data, Turn Estimate, Output by Station, Photo Late Orders, Daily Notes)</div>
  <div>Generated {esc(d['meta']['generated_at'])}</div>
</footer>
<script>{JS}</script>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
