#!/usr/bin/env python3
"""Freeze a naive persistence benchmark for the already frozen 2025 gate.

Definition:
  prediction_2025 = observed inflow_per_1000 in 2024
                 = lag1_inflyttning_per_1000 in the frozen 2025 predictor matrix.

This benchmark is diagnostic only and does not alter core-4 or the temporal challenger.
"""
import hashlib, json
from pathlib import Path
import pandas as pd

D=Path("docs/data")
FREEZE=D/"preoutcome_2025_core4_temporal"
PREDICTORS=FREEZE/"predictor_matrix_2025.csv"
OUT=FREEZE/"naive_persistence_2025.csv"
MANIFEST=FREEZE/"naive_persistence_manifest.json"

def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

base_manifest=json.loads((FREEZE/"manifest.json").read_text(encoding="utf-8"))
expected=base_manifest["files_sha256"]["predictor_matrix_2025.csv"]
actual=sha256(PREDICTORS)
if actual!=expected:
    raise SystemExit(f"Frozen predictor matrix hash mismatch: expected={expected}, actual={actual}")

df=pd.read_csv(PREDICTORS,dtype={"kommun_kod":str})
df["kommun_kod"]=df["kommun_kod"].astype(str).str.zfill(4)
if len(df)!=290 or df["kommun_kod"].nunique()!=290:
    raise SystemExit(f"Expected 290 unique municipalities, got rows={len(df)}, unique={df['kommun_kod'].nunique()}")
if df["lag1_inflyttning_per_1000"].isna().any():
    raise SystemExit("Naive persistence cannot be frozen: missing lag1 inflow values")

out=df[["kommun_kod","year","lag1_inflyttning_per_1000"]].copy()
out=out.rename(columns={"lag1_inflyttning_per_1000":"naive_persistence_prediction_per_1000"})
out.to_csv(OUT,index=False)

m={
  "status":"preoutcome_2025_naive_persistence_frozen",
  "forecast_year":2025,
  "municipalities":290,
  "definition":"prediction_2025 = observed inflow_per_1000 in 2024",
  "source":"docs/data/preoutcome_2025_core4_temporal/predictor_matrix_2025.csv",
  "source_sha256":actual,
  "prediction_file":"docs/data/preoutcome_2025_core4_temporal/naive_persistence_2025.csv",
  "prediction_sha256":sha256(OUT),
  "production_changed":False,
  "model_selection_changed":False
}
MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

print(json.dumps({
  "status":m["status"],
  "n":len(out),
  "mean_prediction":float(out["naive_persistence_prediction_per_1000"].mean()),
  "lulea":out.loc[out.kommun_kod=="2580"].to_dict("records"),
  "prediction_sha256":m["prediction_sha256"]
},ensure_ascii=False,indent=2))
