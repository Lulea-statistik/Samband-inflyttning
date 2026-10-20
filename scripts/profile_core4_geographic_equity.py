#!/usr/bin/env python3
import csv, json, math
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

P=Path("docs/data/three_year_forecast_core4_historical_reconstructed_predictions.csv")
OUT=Path("docs/data/core4_geographic_equity_profile.json")
DETAIL=Path("docs/data/core4_geographic_equity_by_municipality.csv")
COMMON_YEARS=list(range(2017,2025))
WINDOWS=[3,4,5,6]

def read():
    with P.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))
def f(x): return float(x)
def q(vals,p):
    a=sorted(vals)
    if not a:return None
    x=(len(a)-1)*p
    lo=int(math.floor(x)); hi=int(math.ceil(x))
    if lo==hi:return a[lo]
    w=x-lo
    return a[lo]*(1-w)+a[hi]*w
def mean(x): return sum(x)/len(x) if x else None
def sd(x):
    if len(x)<2:return 0.0
    m=mean(x)
    return math.sqrt(sum((v-m)**2 for v in x)/(len(x)-1))
def rmse(x): return math.sqrt(mean([v*v for v in x])) if x else None
def mae(x): return mean([abs(v) for v in x]) if x else None

rows=read()
profiles={}
detail=[]

for w in WINDOWS:
    rr=[r for r in rows if int(r["window_years"])==w and int(r["forecast_year"]) in COMMON_YEARS]
    years=sorted({int(r["forecast_year"]) for r in rr})
    munis=sorted({r["kommun_kod"].zfill(4) for r in rr})
    if years!=COMMON_YEARS or len(munis)!=290:
        raise SystemExit(f"Window {w} lacks common balanced panel: years={years}, municipalities={len(munis)}")
    by=defaultdict(list)
    all_err=[]
    for r in rr:
        e=f(r["prediction"])-f(r["actual"])
        by[r["kommun_kod"].zfill(4)].append(e)
        all_err.append(e)
    muni_stats=[]
    for code in munis:
        es=by[code]
        if len(es)!=len(COMMON_YEARS):
            raise SystemExit(f"Window {w} municipality {code} has {len(es)} years")
        rec={
          "window_years":w,
          "kommun_kod":code,
          "n_years":len(es),
          "municipality_rmse":rmse(es),
          "municipality_mae":mae(es),
          "municipality_bias":mean(es),
          "abs_bias":abs(mean(es))
        }
        detail.append(rec);muni_stats.append(rec)
    rms=[x["municipality_rmse"] for x in muni_stats]
    mas=[x["municipality_mae"] for x in muni_stats]
    absbias=[x["abs_bias"] for x in muni_stats]
    p90=q(rms,.90); med=q(rms,.50)
    worst=sorted(rms,reverse=True)[:29]
    profiles[str(w)]={
      "n_municipalities":290,
      "evaluation_years":COMMON_YEARS,
      "pooled_rmse":rmse(all_err),
      "pooled_mae":mae(all_err),
      "mean_municipality_rmse":mean(rms),
      "median_municipality_rmse":med,
      "sd_municipality_rmse":sd(rms),
      "iqr_municipality_rmse":q(rms,.75)-q(rms,.25),
      "p90_municipality_rmse":p90,
      "p95_municipality_rmse":q(rms,.95),
      "worst_decile_mean_rmse":mean(worst),
      "max_municipality_rmse":max(rms),
      "p90_minus_median_rmse":p90-med,
      "p90_to_median_ratio":p90/med if med else None,
      "mean_municipality_mae":mean(mas),
      "p90_municipality_mae":q(mas,.90),
      "mean_abs_municipality_bias":mean(absbias),
      "p90_abs_municipality_bias":q(absbias,.90),
      "share_municipalities_rmse_gt_10":sum(v>10 for v in rms)/len(rms)
    }

base=profiles["6"]
for w in WINDOWS:
    p=profiles[str(w)]
    p["delta_vs_locked_6y"]={
      "pooled_rmse_pct":100*(p["pooled_rmse"]/base["pooled_rmse"]-1),
      "p90_municipality_rmse_pct":100*(p["p90_municipality_rmse"]/base["p90_municipality_rmse"]-1),
      "worst_decile_mean_rmse_pct":100*(p["worst_decile_mean_rmse"]/base["worst_decile_mean_rmse"]-1),
      "sd_municipality_rmse_pct":100*(p["sd_municipality_rmse"]/base["sd_municipality_rmse"]-1),
      "mean_abs_municipality_bias_pct":100*(p["mean_abs_municipality_bias"]/base["mean_abs_municipality_bias"]-1)
    }

# Pareto: lower pooled RMSE and lower p90 municipality RMSE.
pareto=[]
for w in WINDOWS:
    a=profiles[str(w)]
    dominated=False
    for v in WINDOWS:
        if v==w: continue
        b=profiles[str(v)]
        if (b["pooled_rmse"]<=a["pooled_rmse"] and b["p90_municipality_rmse"]<=a["p90_municipality_rmse"]
            and (b["pooled_rmse"]<a["pooled_rmse"] or b["p90_municipality_rmse"]<a["p90_municipality_rmse"])):
            dominated=True;break
    if not dominated: pareto.append(w)

res={
 "status":"core4_geographic_equity_profile",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "locked_reference_window_years":6,
 "common_evaluation_years":COMMON_YEARS,
 "n_municipalities":290,
 "interpretation":{
   "pooled_rmse":"overall accuracy across all municipality-year predictions",
   "p90_municipality_rmse":"error level below which 90% of municipalities fall; primary geographic-equity tail metric",
   "worst_decile_mean_rmse":"mean municipality RMSE among the hardest 10% of municipalities",
   "sd_municipality_rmse":"dispersion of municipality-specific RMSE",
   "pareto_rule":"a window is retained if no other window has both lower pooled RMSE and lower p90 municipality RMSE"
 },
 "profiles":profiles,
 "pareto_windows":pareto,
 "next_step":"Use the locked 6-year model as reference and test dispersion-aware training objectives only if an existing window does not dominate on both accuracy and geographic equity."
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
with DETAIL.open("w",newline="",encoding="utf-8") as fobj:
    cols=list(detail[0].keys())
    w=csv.DictWriter(fobj,fieldnames=cols);w.writeheader();w.writerows(detail)
print(json.dumps(res,ensure_ascii=False,indent=2))
