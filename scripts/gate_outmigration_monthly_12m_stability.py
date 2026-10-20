#!/usr/bin/env python3
"""Temporal stability gate for 12-month outmigration monthly challengers."""
import csv,json,math
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone

PRED=Path("docs/data/outmigration_monthly_neutral_common_origin_predictions.csv")
OUT=Path("docs/data/outmigration_monthly_12m_stability_gate.json")

CANDIDATES=[
 ("rates_25_29_lag1",30.0),
 ("rates_25_29_lag1",10.0),
 ("family1_bas_yoy_lag2",30.0),
 ("family1_bas_yoy_lag2",10.0),
]
H=12

def read():
    with PRED.open(encoding="utf-8") as f:return list(csv.DictReader(f))
def f(x):return float(x)
def rmse(v):return math.sqrt(sum(x*x for x in v)/len(v)) if v else None
def mae(v):return sum(abs(x) for x in v)/len(v) if v else None
def pct(a,b):return 100*(a/b-1) if b else None

rows=read()
summary={}
for arm,alpha in CANDIDATES:
    rr=[r for r in rows if int(r["horizon_months"])==H and float(r["alpha"])==alpha]
    me=[f(r[arm+"_error"]) for r in rr]
    se=[f(r["seasonal_error"]) for r in rr]
    byy=defaultdict(list)
    for r in rr: byy[r["origin"][:4]].append(r)
    ys={}
    wins=0
    for y,yy in sorted(byy.items()):
        mer=[f(r[arm+"_error"]) for r in yy]
        ser=[f(r["seasonal_error"]) for r in yy]
        d=pct(rmse(mer),rmse(ser))
        win=d<0
        wins+=int(win)
        ys[y]={
          "n_origins":len(yy),
          "delta_rmse_pct_vs_seasonal":d,
          "delta_mae_pct_vs_seasonal":pct(mae(mer),mae(ser)),
          "rmse_win":win
        }
    loo=[]
    for i,r in enumerate(rr):
        xx=[x for j,x in enumerate(rr) if j!=i]
        d=pct(rmse([f(x[arm+"_error"]) for x in xx]),
              rmse([f(x["seasonal_error"]) for x in xx]))
        loo.append(d)
    overall={
      "n_origins":len(rr),
      "first_origin":rr[0]["origin"] if rr else None,
      "last_origin":rr[-1]["origin"] if rr else None,
      "rmse":rmse(me),
      "seasonal_rmse":rmse(se),
      "delta_rmse_pct_vs_seasonal":pct(rmse(me),rmse(se)),
      "mae":mae(me),
      "seasonal_mae":mae(se),
      "delta_mae_pct_vs_seasonal":pct(mae(me),mae(se)),
      "year_rmse_wins":wins,
      "year_count":len(ys),
      "loo_worst_delta_rmse_pct":max(loo) if loo else None,
      "loo_all_still_better":all(x<0 for x in loo) if loo else False
    }
    passes=(
      overall["delta_rmse_pct_vs_seasonal"]<=-5
      and overall["delta_mae_pct_vs_seasonal"]<=-5
      and wins>=max(1,len(ys)-1)
      and overall["loo_all_still_better"]
    )
    summary[f"{arm}_alpha{int(alpha)}"]={
      "arm":arm,"alpha":alpha,"overall":overall,"by_origin_year":ys,"passes_gate":passes
    }

passing=[k for k,v in summary.items() if v["passes_gate"]]
res={
 "status":"outmigration_monthly_12m_stability_gate",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "annual_outmigration_blend_changed":False,
 "horizon_months":12,
 "gate":{
   "rmse_improvement_pct_at_least":5,
   "mae_improvement_pct_at_least":5,
   "year_rmse_wins":"all but at most one origin-year",
   "leave_one_origin_out":"must remain better than seasonal for every omitted origin"
 },
 "candidates":summary,
 "passing_candidates":passing,
 "promotion_status":"eligible_for_next_gate" if passing else "no_monthly_candidate_promoted"
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(res,ensure_ascii=False,indent=2))
