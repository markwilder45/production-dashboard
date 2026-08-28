# Production Dashboard

A daily operations dashboard for a photo/film/video scanning production floor — built to turn a Google Sheet of raw queue, staffing, and equipment data into a decision-ready HTML report every morning.

**Live dashboard:** https://markwilder45.github.io/production-dashboard/

## What it does

- Pulls ~14 tabs from a Google Sheet (queue backlogs, staffing/attendance, output by station, equipment capacity, turn-time tracking) each morning.
- Computes queue aging (Late / Week 1 / Week 2 / Week 3 / Week 4 buckets), staffing gaps, and a 4-week-forward capacity forecast per station — comparing what's coming due against both staffed output and physical equipment ceilings.
- Classifies *why* a station is falling behind (understaffed, output below expectation, or backlog volume exceeding capacity) and tracks day-over-day whether an issue is new or carrying over.
- Renders a self-contained, six-tab HTML report: Today / Week / Staffing / Late Orders / Capacity & Forecast / Overview & AI Insights.

## How it's built

- **`scripts/compute.py`** — parses the raw sheet exports and does all the arithmetic (bucket splits, staffing rollups, capacity/utilization math, root-cause classification). Deterministic, no external dependencies beyond the Python standard library.
- **`scripts/render_dashboard.py`** — pure templating layer that turns the computed JSON plus a short block of written commentary into the final HTML/CSS. No business logic lives here.
- The written commentary (status summary, floor notes, suggested actions) is generated separately each day and merged in at render time — the scripts above never see or need write access to that step.

## Structure

```
index.html            live dashboard (always the latest run)
archive/              dated snapshots, one per day, for tracking progress over time
scripts/              the two Python modules described above
capacity_log.json     daily capacity-forecast snapshots (aggregate numbers only), used to
                       compute day-over-day trend (e.g. "carrying over" vs "newly emerged")
```

## Notes

This repo intentionally does not include the intermediate per-run data files (raw sheet exports, computed JSON, or written commentary) — only the source code and the rendered output. Individual compensation figures are never included in the published report; the payroll section shows hours per person with an aggregate dollar total only.
