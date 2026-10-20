#!/usr/bin/env python3
"""Gate the 25/75 blend against the locked 3y core and 10y sensitivity reference.

Candidate:
  25% 3-year lag1-only forecast + 75% 10-year lag1-only forecast.

Promotion requires:
- lower national pooled RMSE than both references;
- bootstrap probability > 90% of beating both references;
- Lulea RMSE not worse than the better reference by more than 0.5%;
- no change to inflow model.
"""
import json
from pathlib import Path

D=Path("docs/data")
j=json.loads((D/"outmigration_3y_10y_blend_test.json").read_text(encoding="utf-8"))

cand="blend_25_75"
nat=j["national"]; lul=j["lulea"]; boot=j["bootstrap"][cand]

best_lulea=min(lul["3y"]["rmse"],lul["10y"]["rmse"])
lulea_delta_best=100*(lul[cand]["rmse"]/best_lulea-1)

checks={
 "national_rmse_better_than_3y": nat[cand]["rmse"] < nat["3y"]["rmse"],
 "national_rmse_better_than_10y": nat[cand]["rmse"] < nat["10y"]["rmse"],
 "bootstrap_prob_better_than_3y_gt_90pct": boot["vs3"]["probability_blend_better"] > 0.90,
 "bootstrap_prob_better_than_10y_gt_90pct": boot["vs10"]["probability_blend_better"] > 0.90,
 "lulea_within_0_5pct_of_best_reference": lulea_delta_best <= 0.5
}
passes=all(checks.values())

out={
 "status":"outmigration_blend_promotion_gate",
 "production_changed":False,
 "inflow_model_changed":False,
 "candidate":cand,
 "candidate_formula":"0.25 * forecast_3y + 0.75 * forecast_10y",
 "checks":checks,
 "passes":passes,
 "national":{
   "candidate_rmse":nat[cand]["rmse"],
   "core3_rmse":nat["3y"]["rmse"],
   "ref10_rmse":nat["10y"]["rmse"]
 },
 "lulea":{
   "candidate_rmse":lul[cand]["rmse"],
   "core3_rmse":lul["3y"]["rmse"],
   "ref10_rmse":lul["10y"]["rmse"],
   "delta_vs_best_reference_pct":lulea_delta_best
 },
 "bootstrap":boot,
 "decision":"Promote blend only if all checks pass; otherwise keep 3y core locked and 10y sensitivity reference."
}

(D/"outmigration_blend_promotion_gate.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
