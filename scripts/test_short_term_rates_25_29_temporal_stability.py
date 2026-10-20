#!/usr/bin/env python3
import csv, json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PRED=Path("docs/data/short_term_monthly_common_origin_candidate_comparison_predictions.csv")
OUT=Path("docs/data/short_term_rates_25_29_temporal_stability.json")
DETAIL=Path("docs/data/short_term_rates_25_29_temporal_stability.csv")

ARMS=["rates_25_29_lag1","rates_25_29_lag2"]
HORIZONS=[3,6,9,12]
ALPHAS=[3.0,10.0,30.0]

def read():
    with PRED.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))
def f(x):
    return float(x)
def rmse(vals):
    return math.sqrt(sum(x*x for x in vals)/len(vals)) if vals else None
def mae(vals):
    return sum(abs(x) for x in vals)/len(vals) if vals else None
def bias(vals):
    return sum(vals)/len(vals) if vals else None
def med(vals):
    if not vals:return None
    a=sorted(vals); n=len(a)
    return a[n//2] if n%2 else (a[n//2-1]+a[n//2])/2
def pct(a,b):
    return 100*(a/b-1) if a is not None and b not in (None,0) else None

rows=read()
detail=[]
summary={}

for h in HORIZONS:
    hs={}
    for alpha in ALPHAS:
        subset=[r for r in rows if int(r["horizon_months"])==h and float(r["alpha"])==alpha]
        if not subset:
            continue
        aset={}
        for arm in ARMS:
            all_model=[f(r[arm+"_error"]) for r in subset]
            all_seas=[f(r["seasonal_error"]) for r in subset]
            abs_wins=sum(abs(f(r[arm+"_error"])) < abs(f(r["seasonal_error"])) for r in subset)
            ties=sum(abs(f(r[arm+"_error"])) == abs(f(r["seasonal_error"])) for r in subset)
            years=defaultdict(list)
            for r in subset:
                years[r["origin"][:4]].append(r)
            year_stats={}
            year_wins=0
            for y, rr in sorted(years.items()):
                me=[f(r[arm+"_error"]) for r in rr]
                se=[f(r["seasonal_error"]) for r in rr]
                mrm, srm = rmse(me), rmse(se)
                mma, sma = mae(me), mae(se)
                won = mrm < srm
                year_wins += int(won)
                year_stats[y]={
                    "n_origins":len(rr),
                    "model_rmse":mrm,
                    "seasonal_rmse":srm,
                    "delta_rmse_pct_vs_seasonal":pct(mrm,srm),
                    "model_mae":mma,
                    "seasonal_mae":sma,
                    "delta_mae_pct_vs_seasonal":pct(mma,sma),
                    "model_bias":bias(me),
                    "seasonal_bias":bias(se),
                    "rmse_win":won
                }
            # Leave-one-origin-out influence on overall RMSE delta.
            loo=[]
            for i,r in enumerate(subset):
                rr=[x for j,x in enumerate(subset) if j!=i]
                me=[f(x[arm+"_error"]) for x in rr]
                se=[f(x["seasonal_error"]) for x in rr]
                loo.append({
                    "origin":r["origin"],
                    "delta_rmse_pct_vs_seasonal_without_origin":pct(rmse(me),rmse(se))
                })
            loo_sorted=sorted(loo,key=lambda x:x["delta_rmse_pct_vs_seasonal_without_origin"])
            overall={
                "n_origins":len(subset),
                "first_origin":subset[0]["origin"],
                "last_origin":subset[-1]["origin"],
                "rmse":rmse(all_model),
                "seasonal_rmse":rmse(all_seas),
                "delta_rmse_pct_vs_seasonal":pct(rmse(all_model),rmse(all_seas)),
                "mae":mae(all_model),
                "seasonal_mae":mae(all_seas),
                "delta_mae_pct_vs_seasonal":pct(mae(all_model),mae(all_seas)),
                "bias":bias(all_model),
                "seasonal_bias":bias(all_seas),
                "median_abs_error":med([abs(x) for x in all_model]),
                "seasonal_median_abs_error":med([abs(x) for x in all_seas]),
                "origin_abs_error_win_rate":abs_wins/len(subset),
                "origin_abs_error_wins":abs_wins,
                "origin_abs_error_ties":ties,
                "year_rmse_wins":year_wins,
                "year_count":len(year_stats),
                "loo_best_delta_rmse_pct":loo_sorted[0] if loo_sorted else None,
                "loo_worst_delta_rmse_pct":loo_sorted[-1] if loo_sorted else None,
                "loo_all_still_better_than_seasonal":all(x["delta_rmse_pct_vs_seasonal_without_origin"] < 0 for x in loo)
            }
            aset[arm]={"overall":overall,"by_origin_year":year_stats}
            for r in subset:
                detail.append({
                    "horizon_months":h,
                    "alpha":alpha,
                    "arm":arm,
                    "origin":r["origin"],
                    "origin_year":r["origin"][:4],
                    "model_error":f(r[arm+"_error"]),
                    "seasonal_error":f(r["seasonal_error"]),
                    "model_abs_error":abs(f(r[arm+"_error"])),
                    "seasonal_abs_error":abs(f(r["seasonal_error"])),
                    "model_abs_error_win":abs(f(r[arm+"_error"])) < abs(f(r["seasonal_error"]))
                })
        hs[str(alpha)]=aset
    summary[str(h)]=hs

result={
    "status":"short_term_rates_25_29_temporal_stability",
    "generated_at_utc":datetime.now(timezone.utc).isoformat(),
    "production_changed":False,
    "structural_core4_changed":False,
    "backward_window_months":12,
    "feature_family":"rates_25_29",
    "purpose":"Check whether aggregate gains are stable over forecast-origin years and not driven by one influential origin.",
    "summary":summary
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
with DETAIL.open("w",newline="",encoding="utf-8") as fobj:
    cols=list(detail[0].keys()) if detail else []
    w=csv.DictWriter(fobj,fieldnames=cols);w.writeheader();w.writerows(detail)
print(json.dumps(result,ensure_ascii=False,indent=2))
