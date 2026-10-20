#!/usr/bin/env python3
"""Calendar-year diagnostic for annual vs monthly outmigration forecasts.

This is deliberately NON-PROMOTIONAL.
Reason: with the current monthly feature history and MIN_TRAIN=24, only one
calendar-year-aligned monthly origin is available (2024M12 -> Jan-Dec 2025).

The diagnostic records:
- annual frozen 2025 blend rate forecast for Lulea;
- monthly 12m model forecast for origin 2024M12, if available;
- monthly observed Jan-Dec 2025 outmigration total from the stitched target,
  if all months are available.

No annual/monthly blending or production promotion is allowed.
"""
import csv,json
from pathlib import Path

D=Path("docs/data")
ANNUAL=D/"preoutcome_2025_outmigration/manifest.json"
MONTHLY=D/"outmigration_monthly_12m_backward_window_predictions.csv"
TARGET=D/"short_term_monthly_target_lulea.csv"
OUT=D/"outmigration_calendar_year_integration_diagnostic.json"

manifest=json.loads(ANNUAL.read_text(encoding="utf-8"))
lulea=manifest["lulea_prediction"][0]

with MONTHLY.open(encoding="utf-8") as f:
    mrows=list(csv.DictReader(f))
aligned=[r for r in mrows if r["origin"]=="2024M12" and r["target_end"]=="2025M12"]

with TARGET.open(encoding="utf-8") as f:
    trows=list(csv.DictReader(f))
months=[r for r in trows if r["month"].startswith("2025M")]
months=sorted(months,key=lambda r:r["month"])
vals=[]
for r in months:
    v=r.get("all_outmigrations")
    if v not in (None,""):
        vals.append(float(v))
actual_2025=sum(vals) if len(vals)==12 else None

monthly=None
if aligned:
    r=aligned[0]
    monthly={
      "origin":"2024M12",
      "target_start":"2025M01",
      "target_end":"2025M12",
      "forecast_count_w12":float(r["w12"]),
      "actual_count_from_monthly_scb":float(r["actual"]),
      "error_count":float(r["w12_error"]),
      "seasonal_count":float(r["seasonal"]),
      "seasonal_error":float(r["seasonal_error"])
    }

res={
 "status":"outmigration_calendar_year_integration_diagnostic",
 "production_changed":False,
 "annual_outmigration_blend_changed":False,
 "monthly_module_promoted":False,
 "promotion_allowed":False,
 "reason":"Only one calendar-year-aligned monthly origin is available after the 24-month minimum training requirement.",
 "aligned_origin_count":len(aligned),
 "annual_2025":{
   "specification":manifest["specification"],
   "forecast_rate_per_1000":lulea["forecast_blend_25_75_per_1000"],
   "outcome_2025_read_in_annual_freeze":manifest["outcome_2025_read"],
   "outcome_2025_queried_in_annual_freeze":manifest["outcome_2025_queried"]
 },
 "monthly_2025":monthly,
 "monthly_target_check":{
   "months_available_2025":len(vals),
   "sum_all_outmigrations_2025":actual_2025
 },
 "decision":"keep annual model and monthly rolling-12m module separate until more calendar-year-aligned origins exist",
 "usage":{
   "annual_model":"calendar-year forecast",
   "monthly_module":"rolling next-12-month short-term signal/nowcast",
   "do_not_add_directly":True
 }
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(res,ensure_ascii=False,indent=2))
