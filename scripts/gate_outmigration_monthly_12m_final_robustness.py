#!/usr/bin/env python3
"""Final robustness gate for 12-month outmigration monthly candidate.

Primary candidate:
- employment rate age 25-29 YoY pp, lag1, Ridge alpha=30

Reference:
- both age25-29 rates, lag1, Ridge alpha=30

Gate is based on identical forecast origins and tests pooled metrics, origin wins,
year stability, and leave-one-origin-out robustness.
"""
import csv,json,math
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone

PRED=Path("docs/data/outmigration_monthly_12m_feature_count_predictions.csv")
OUT=Path("docs/data/outmigration_monthly_12m_final_robustness_gate.json")

CAND="employment_only_lag1"
REF="both_rates_lag1"
ALPHA=30.0
H=12

def read():
    with PRED.open(encoding="utf-8") as f:return list(csv.DictReader(f))
def f(x):return float(x)
def rmse(v):return math.sqrt(sum(x*x for x in v)/len(v)) if v else None
def mae(v):return sum(abs(x) for x in v)/len(v) if v else None
def pct(a,b):return 100*(a/b-1) if b else None

rr=[r for r in read() if int(r["horizon_months"])==H and float(r["alpha"])==ALPHA]
ce=[f(r[CAND+"_error"]) for r in rr]
re=[f(r[REF+"_error"]) for r in rr]
se=[f(r["seasonal_error"]) for r in rr]

origin_wins=sum(abs(f(r[CAND+"_error"])) < abs(f(r[REF+"_error"])) for r in rr)
origin_ties=sum(abs(f(r[CAND+"_error"])) == abs(f(r[REF+"_error"])) for r in rr)

byy=defaultdict(list)
for r in rr: byy[r["origin"][:4]].append(r)
years={}
for y,yy in sorted(byy.items()):
    c=[f(r[CAND+"_error"]) for r in yy]
    ref=[f(r[REF+"_error"]) for r in yy]
    seas=[f(r["seasonal_error"]) for r in yy]
    years[y]={
      "n_origins":len(yy),
      "candidate_delta_rmse_pct_vs_seasonal":pct(rmse(c),rmse(seas)),
      "reference_delta_rmse_pct_vs_seasonal":pct(rmse(ref),rmse(seas)),
      "candidate_delta_rmse_pct_vs_reference":pct(rmse(c),rmse(ref)),
      "candidate_beats_seasonal_rmse":rmse(c)<rmse(seas)
    }

loo=[]
for i in range(len(rr)):
    xx=[r for j,r in enumerate(rr) if j!=i]
    c=[f(r[CAND+"_error"]) for r in xx]
    ref=[f(r[REF+"_error"]) for r in xx]
    seas=[f(r["seasonal_error"]) for r in xx]
    loo.append({
      "omitted_origin":rr[i]["origin"],
      "candidate_delta_rmse_pct_vs_seasonal":pct(rmse(c),rmse(seas)),
      "candidate_delta_rmse_pct_vs_reference":pct(rmse(c),rmse(ref))
    })

candidate={
 "rmse":rmse(ce),"mae":mae(ce),
 "delta_rmse_pct_vs_seasonal":pct(rmse(ce),rmse(se)),
 "delta_mae_pct_vs_seasonal":pct(mae(ce),mae(se)),
 "delta_rmse_pct_vs_reference":pct(rmse(ce),rmse(re)),
 "delta_mae_pct_vs_reference":pct(mae(ce),mae(re))
}
reference={
 "rmse":rmse(re),"mae":mae(re),
 "delta_rmse_pct_vs_seasonal":pct(rmse(re),rmse(se)),
 "delta_mae_pct_vs_seasonal":pct(mae(re),mae(se))
}

passes=(
 candidate["delta_rmse_pct_vs_seasonal"] < 0
 and candidate["delta_mae_pct_vs_seasonal"] < 0
 and all(v["candidate_beats_seasonal_rmse"] for v in years.values())
 and all(v["candidate_delta_rmse_pct_vs_seasonal"] < 0 for v in loo)
)

res={
 "status":"outmigration_monthly_12m_final_robustness_gate",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "annual_outmigration_blend_changed":False,
 "horizon_months":12,
 "candidate":{
   "name":"employment_only_lag1_alpha30",
   "feature":"bas2_age25_29_sysselsattningsgrad_yoy_pp",
   "lag_months":1,
   "alpha":30.0,
   **candidate
 },
 "two_feature_reference":{
   "name":"both_rates_lag1_alpha30",
   "features":["bas2_age25_29_sysselsattningsgrad_yoy_pp","bas2_age25_29_arbetskraftsdeltagande_yoy_pp"],
   "lag_months":1,
   "alpha":30.0,
   **reference
 },
 "origin_absolute_error_wins_vs_two_feature":origin_wins,
 "origin_absolute_error_ties_vs_two_feature":origin_ties,
 "n_origins":len(rr),
 "by_origin_year":years,
 "leave_one_origin_out":loo,
 "passes_gate":passes,
 "decision":"promote_simple_12m_candidate_to_final_integration_test" if passes else "do_not_promote"
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(res,ensure_ascii=False,indent=2))
