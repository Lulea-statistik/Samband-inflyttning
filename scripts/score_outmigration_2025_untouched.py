#!/usr/bin/env python3
"""Strict untouched scorer for frozen 2025 outmigration blend.

This script:
- verifies the frozen 2025 prediction hash from its manifest;
- accepts only a supplied 2025 outcome CSV;
- never refits, retunes, rebuilds predictors, or reads model-building code;
- scores 3y, 10y, and promoted 25/75 blend on identical municipalities.

Required outcome columns:
  kommun_kod, utflyttning_per_1000
Optional:
  year (must equal 2025 if present)
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
FREEZE=D/"preoutcome_2025_outmigration"
MANIFEST=FREEZE/"manifest.json"
PRED=FREEZE/"predictions_2025.csv"
DEFAULT_OUT=D/"outmigration_2025_untouched_score.json"

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def metrics(y,p):
    e=np.asarray(p,float)-np.asarray(y,float)
    ae=np.abs(e)
    return {
      "n":int(len(e)),
      "rmse":float(np.sqrt(np.mean(e*e))),
      "mae":float(np.mean(ae)),
      "bias_prediction_minus_actual":float(np.mean(e)),
      "median_absolute_error":float(np.median(ae))
    },e

ap=argparse.ArgumentParser()
ap.add_argument("--outcome-csv",required=True)
ap.add_argument("--output-json",default=str(DEFAULT_OUT))
args=ap.parse_args()

manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
if manifest.get("status")!="outmigration_2025_predictions_frozen_pre_outcome":
    raise SystemExit("Frozen manifest status invalid")
if manifest.get("forecast_year")!=2025:
    raise SystemExit("Frozen forecast year is not 2025")
if manifest.get("outcome_2025_read") is not False or manifest.get("outcome_2025_queried") is not False:
    raise SystemExit("Freeze manifest indicates outcome contamination")

expected=manifest["files_sha256"][str(PRED)]
actual=sha256(PRED)
if actual!=expected:
    raise SystemExit(f"Frozen prediction hash mismatch: expected={expected}, actual={actual}")

pred=pd.read_csv(PRED,dtype={"kommun_kod":str})
pred["kommun_kod"]=pred["kommun_kod"].astype(str).str.zfill(4)
if len(pred)!=290 or pred.kommun_kod.nunique()!=290:
    raise SystemExit("Frozen predictions must contain exactly 290 municipalities")

outcome=pd.read_csv(args.outcome_csv,dtype={"kommun_kod":str})
need={"kommun_kod","utflyttning_per_1000"}
missing=need-set(outcome.columns)
if missing:
    raise SystemExit(f"Outcome CSV missing columns: {sorted(missing)}")
outcome["kommun_kod"]=outcome["kommun_kod"].astype(str).str.zfill(4)
if "year" in outcome.columns:
    yrs=set(pd.to_numeric(outcome["year"],errors="coerce").dropna().astype(int))
    if yrs!={2025}:
        raise SystemExit(f"Outcome year must be 2025, got {sorted(yrs)}")
outcome["utflyttning_per_1000"]=pd.to_numeric(outcome["utflyttning_per_1000"],errors="coerce")
outcome=outcome.dropna(subset=["utflyttning_per_1000"]).copy()
if outcome.kommun_kod.duplicated().any():
    raise SystemExit("Duplicate municipality codes in outcome")

m=pred.merge(outcome[["kommun_kod","utflyttning_per_1000"]],on="kommun_kod",how="inner",validate="one_to_one")
if len(m)!=290:
    raise SystemExit(f"Untouched scoring requires all 290 municipalities; matched={len(m)}")

models={
 "component_3y":"forecast_3y_per_1000",
 "component_10y":"forecast_10y_per_1000",
 "blend_25_75":"forecast_blend_25_75_per_1000"
}
result_metrics={}
residuals=m[["kommun_kod","utflyttning_per_1000"]].copy()
for name,col in models.items():
    met,e=metrics(m["utflyttning_per_1000"],m[col])
    result_metrics[name]=met
    residuals[name+"_prediction_per_1000"]=m[col]
    residuals[name+"_residual_prediction_minus_actual"]=e
    residuals[name+"_absolute_error"]=np.abs(e)

lulea=residuals[residuals.kommun_kod.eq("2580")].iloc[0]
b=result_metrics["blend_25_75"]["rmse"]
r3=result_metrics["component_3y"]["rmse"]
r10=result_metrics["component_10y"]["rmse"]

result={
 "status":"untouched_2025_outmigration_score_recorded",
 "forecast_year":2025,
 "frozen_prediction_sha256":actual,
 "source_freeze_manifest":str(MANIFEST),
 "n_municipalities":290,
 "primary_metric":"RMSE",
 "metrics":result_metrics,
 "comparison":{
   "blend_rmse_change_vs_3y_pct":float(100*(b/r3-1)) if r3 else None,
   "blend_rmse_change_vs_10y_pct":float(100*(b/r10-1)) if r10 else None,
   "blend_beats_3y":bool(b<r3),
   "blend_beats_10y":bool(b<r10)
 },
 "lulea":{
   "kommun_kod":"2580",
   "actual_per_1000":float(lulea["utflyttning_per_1000"]),
   "forecast_3y_per_1000":float(lulea["component_3y_prediction_per_1000"]),
   "forecast_10y_per_1000":float(lulea["component_10y_prediction_per_1000"]),
   "forecast_blend_25_75_per_1000":float(lulea["blend_25_75_prediction_per_1000"]),
   "blend_absolute_error":float(lulea["blend_25_75_absolute_error"])
 },
 "guardrails":{
   "refit_performed":False,
   "retuning_performed":False,
   "reselection_performed":False,
   "predictors_rebuilt":False,
   "frozen_predictions_only":True,
   "automatic_production_promotion":False
 }
}
Path(args.output_json).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
residual_path=Path(args.output_json).with_name("outmigration_2025_untouched_residuals.csv")
residuals.sort_values("kommun_kod").to_csv(residual_path,index=False)
print(json.dumps(result,ensure_ascii=False,indent=2))
