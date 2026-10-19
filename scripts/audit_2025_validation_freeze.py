#!/usr/bin/env python3
"""Audit the complete pre-outcome 2025 validation freeze.

Checks:
- manifests and SHA256 hashes
- 290 municipalities in core4/trend and naive benchmark
- municipality sets identical
- Lulea 2580 present
- predictor matrix has no 2025 outcome values
- training matrix contains only 2019-2024
- scorer exists
Writes validation_ready audit JSON.
"""
import hashlib, json
from pathlib import Path
import pandas as pd

D=Path("docs/data")
F=D/"preoutcome_2025_core4_temporal"
OUT=D/"three_year_forecast_2025_validation_readiness_audit.json"

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

m=json.loads((F/"manifest.json").read_text(encoding="utf-8"))
n=json.loads((F/"naive_persistence_manifest.json").read_text(encoding="utf-8"))

checks={}
checks["core_manifest_status"]=m.get("status")=="preoutcome_2025_core4_temporal_predictions_frozen"
checks["naive_manifest_status"]=n.get("status")=="preoutcome_2025_naive_persistence_frozen"
checks["forecast_year_2025"]=m.get("forecast_year")==2025 and n.get("forecast_year")==2025
checks["production_unchanged"]=m.get("production_changed") is False and n.get("production_changed") is False

files={
 "training_matrix_2019_2024.csv":F/"training_matrix_2019_2024.csv",
 "predictor_matrix_2025.csv":F/"predictor_matrix_2025.csv",
 "predictions_2025.csv":F/"predictions_2025.csv",
}
hashes={}
for name,p in files.items():
    hashes[name]=sha(p)
    checks[f"hash_{name}"]=hashes[name]==m["files_sha256"][name]

naive_file=F/"naive_persistence_2025.csv"
hashes["naive_persistence_2025.csv"]=sha(naive_file)
checks["hash_naive_persistence_2025.csv"]=hashes["naive_persistence_2025.csv"]==n["prediction_sha256"]

train=pd.read_csv(files["training_matrix_2019_2024.csv"],dtype={"kommun_kod":str})
predmat=pd.read_csv(files["predictor_matrix_2025.csv"],dtype={"kommun_kod":str})
pred=pd.read_csv(files["predictions_2025.csv"],dtype={"kommun_kod":str})
naive=pd.read_csv(naive_file,dtype={"kommun_kod":str})

for df in (train,predmat,pred,naive):
    df["kommun_kod"]=df["kommun_kod"].astype(str).str.zfill(4)

checks["train_years_exact_2019_2024"]=set(pd.to_numeric(train["year"],errors="coerce").dropna().astype(int))==set(range(2019,2025))
checks["train_rows_1740"]=len(train)==1740
checks["predictor_rows_290"]=len(predmat)==290 and predmat["kommun_kod"].nunique()==290
checks["prediction_rows_290"]=len(pred)==290 and pred["kommun_kod"].nunique()==290
checks["naive_rows_290"]=len(naive)==290 and naive["kommun_kod"].nunique()==290

sets={
 "predictor":set(predmat["kommun_kod"]),
 "prediction":set(pred["kommun_kod"]),
 "naive":set(naive["kommun_kod"])
}
checks["municipality_sets_identical"]=len({frozenset(v) for v in sets.values()})==1
checks["lulea_present_all"]=all("2580" in v for v in sets.values())

# Guard against accidental outcome leakage into the frozen 2025 predictor matrix.
checks["predictor_year_exact_2025"]=set(pd.to_numeric(predmat["year"],errors="coerce").dropna().astype(int))=={2025}
if "inflyttning_per_1000" in predmat.columns:
    checks["no_2025_outcome_in_predictor_matrix"]=predmat["inflyttning_per_1000"].isna().all()
else:
    checks["no_2025_outcome_in_predictor_matrix"]=True

scorer=Path("scripts/score_2025_core4_temporal_untouched.py")
checks["untouched_scorer_exists"]=scorer.exists()

validation_ready=all(checks.values())
result={
 "status":"2025_validation_readiness_audit",
 "validation_ready":validation_ready,
 "forecast_year":2025,
 "checks":checks,
 "hashes_observed":hashes,
 "municipality_count":len(sets["prediction"]),
 "lulea_present":"2580" in sets["prediction"],
 "guardrail":"No 2025 outcome values may be written into the frozen predictor or prediction files before scoring."
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))
if not validation_ready:
    raise SystemExit("2025 validation freeze audit failed")
