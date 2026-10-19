#!/usr/bin/env python3
"""Score frozen 2025 core-4 temporal predictions against a provided outcome file.

Strict scoring only:
- verifies frozen prediction file hash against manifest
- never refits models
- never reconstructs predictors
- never reselects or redefines variables
- compares core4 vs core4_plus_trend3y on identical municipalities

Outcome CSV requirements:
  kommun_kod, inflyttning_per_1000
Optional:
  year (must equal 2025 if present)
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
FREEZE=D/"preoutcome_2025_core4_temporal"
MANIFEST=FREEZE/"manifest.json"
PRED=FREEZE/"predictions_2025.csv"
NAIVE=FREEZE/"naive_persistence_2025.csv"
NAIVE_MANIFEST=FREEZE/"naive_persistence_manifest.json"
OUT=D/"three_year_forecast_2025_untouched_temporal_score.json"

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def metrics(y,p):
    e=np.asarray(p,dtype=float)-np.asarray(y,dtype=float)
    ae=np.abs(e)
    return {
      "n":int(len(e)),
      "rmse":float(np.sqrt(np.mean(e**2))),
      "mae":float(np.mean(ae)),
      "bias_prediction_minus_actual":float(np.mean(e)),
      "median_absolute_error":float(np.median(ae))
    },e

ap=argparse.ArgumentParser()
ap.add_argument("--outcome-csv",required=True)
ap.add_argument("--output-json",default=str(OUT))
args=ap.parse_args()

manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
if manifest.get("status")!="preoutcome_2025_core4_temporal_predictions_frozen":
    raise SystemExit("Frozen manifest status invalid")
if manifest.get("forecast_year")!=2025:
    raise SystemExit("Frozen manifest forecast year is not 2025")
if manifest.get("production_changed") is not False:
    raise SystemExit("Unexpected production_changed state")

expected=manifest["files_sha256"]["predictions_2025.csv"]
actual=sha256(PRED)
if actual!=expected:
    raise SystemExit(f"Frozen prediction hash mismatch: expected={expected}, actual={actual}")

naive_manifest=json.loads(NAIVE_MANIFEST.read_text(encoding="utf-8"))
if naive_manifest.get("status")!="preoutcome_2025_naive_persistence_frozen":
    raise SystemExit("Naive persistence manifest status invalid")
naive_expected=naive_manifest["prediction_sha256"]
naive_actual=sha256(NAIVE)
if naive_actual!=naive_expected:
    raise SystemExit(f"Frozen naive prediction hash mismatch: expected={naive_expected}, actual={naive_actual}")

pred=pd.read_csv(PRED,dtype={"kommun_kod":str})
pred["kommun_kod"]=pred["kommun_kod"].astype(str).str.zfill(4)
if len(pred)!=290 or pred["kommun_kod"].nunique()!=290:
    raise SystemExit(f"Frozen prediction row mismatch: rows={len(pred)}, unique={pred['kommun_kod'].nunique()}")

naive=pd.read_csv(NAIVE,dtype={"kommun_kod":str})
naive["kommun_kod"]=naive["kommun_kod"].astype(str).str.zfill(4)
if len(naive)!=290 or naive["kommun_kod"].nunique()!=290:
    raise SystemExit(f"Frozen naive row mismatch: rows={len(naive)}, unique={naive['kommun_kod'].nunique()}")
pred=pred.merge(naive[["kommun_kod","naive_persistence_prediction_per_1000"]],
                on="kommun_kod",how="inner")
if len(pred)!=290:
    raise SystemExit("Frozen model and naive benchmark municipality sets differ")

outcome=pd.read_csv(args.outcome_csv,dtype={"kommun_kod":str})
required={"kommun_kod","inflyttning_per_1000"}
missing=required-set(outcome.columns)
if missing:
    raise SystemExit(f"Outcome CSV missing columns: {sorted(missing)}")
outcome["kommun_kod"]=outcome["kommun_kod"].astype(str).str.zfill(4)
if "year" in outcome.columns:
    yrs=set(pd.to_numeric(outcome["year"],errors="coerce").dropna().astype(int))
    if yrs!={2025}:
        raise SystemExit(f"Outcome year must be exactly 2025, got {sorted(yrs)}")

outcome["inflyttning_per_1000"]=pd.to_numeric(outcome["inflyttning_per_1000"],errors="coerce")
outcome=outcome.dropna(subset=["inflyttning_per_1000"]).copy()
if outcome["kommun_kod"].duplicated().any():
    dups=outcome.loc[outcome["kommun_kod"].duplicated(),"kommun_kod"].tolist()[:10]
    raise SystemExit(f"Duplicate municipality codes in outcome: {dups}")

m=pred.merge(outcome[["kommun_kod","inflyttning_per_1000"]],on="kommun_kod",how="inner")
if len(m)!=290:
    missing_pred=sorted(set(pred.kommun_kod)-set(m.kommun_kod))
    missing_out=sorted(set(outcome.kommun_kod)-set(m.kommun_kod))
    raise SystemExit(
      f"Untouched score requires all 290 municipalities; matched={len(m)}, "
      f"missing_outcome_for_frozen={missing_pred[:20]}, outcome_only={missing_out[:20]}"
    )

models={
 "naive_persistence":"naive_persistence_prediction_per_1000",
 "core4":"core4_prediction_per_1000",
 "core4_plus_trend3y":"core4_plus_trend3y_prediction_per_1000"
}
res={}
residual_table=m[["kommun_kod","inflyttning_per_1000"]].copy()

for name,col in models.items():
    met,e=metrics(m["inflyttning_per_1000"],m[col])
    res[name]=met
    residual_table[name+"_prediction_per_1000"]=m[col]
    residual_table[name+"_residual_prediction_minus_actual"]=e
    residual_table[name+"_absolute_error"]=np.abs(e)

naive_rmse=res["naive_persistence"]["rmse"]
base=res["core4"]["rmse"]
chal=res["core4_plus_trend3y"]["rmse"]
delta=chal-base
delta_pct=100*(chal/base-1) if base else None
core4_vs_naive=100*(base/naive_rmse-1) if naive_rmse else None
trend_vs_naive=100*(chal/naive_rmse-1) if naive_rmse else None

lulea=residual_table[residual_table.kommun_kod=="2580"]
if len(lulea)!=1:
    raise SystemExit("Luleå 2580 missing from untouched score")
lr=lulea.iloc[0]

comparison={
 "rmse_challenger_minus_core4":float(delta),
 "rmse_change_vs_core4_pct":float(delta_pct),
 "challenger_beats_core4_rmse":bool(chal<base),
 "core4_rmse_change_vs_naive_pct":float(core4_vs_naive),
 "trend3y_rmse_change_vs_naive_pct":float(trend_vs_naive),
 "core4_beats_naive_rmse":bool(base<naive_rmse),
 "trend3y_beats_naive_rmse":bool(chal<naive_rmse),
 "within_1pct":bool(chal<=base*1.01),
 "within_2pct":bool(chal<=base*1.02),
 "within_5pct":bool(chal<=base*1.05)
}

result={
 "status":"untouched_2025_temporal_score_recorded",
 "forecast_year":2025,
 "frozen_prediction_sha256":actual,
 "frozen_naive_prediction_sha256":naive_actual,
 "source_freeze_manifest":"docs/data/preoutcome_2025_core4_temporal/manifest.json",
 "n_municipalities":290,
 "primary_metric":"RMSE",
 "metrics":res,
 "comparison":comparison,
 "lulea":{
   "kommun_kod":"2580",
   "actual_per_1000":float(lr["inflyttning_per_1000"]),
   "naive_persistence_prediction_per_1000":float(lr["naive_persistence_prediction_per_1000"]),
   "naive_persistence_absolute_error":float(lr["naive_persistence_absolute_error"]),
   "core4_prediction_per_1000":float(lr["core4_prediction_per_1000"]),
   "core4_absolute_error":float(lr["core4_absolute_error"]),
   "core4_plus_trend3y_prediction_per_1000":float(lr["core4_plus_trend3y_prediction_per_1000"]),
   "core4_plus_trend3y_absolute_error":float(lr["core4_plus_trend3y_absolute_error"])
 },
 "guardrails":{
   "refit_performed":False,
   "reselection_performed":False,
   "temporal_redefinition_performed":False,
   "frozen_predictions_only":True,
   "automatic_production_promotion":False
 }
}

Path(args.output_json).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
residual_csv=Path(args.output_json).with_name("three_year_forecast_2025_untouched_temporal_residuals.csv")
residual_table.sort_values("kommun_kod").to_csv(residual_csv,index=False)

print(json.dumps(result,ensure_ascii=False,indent=2))
