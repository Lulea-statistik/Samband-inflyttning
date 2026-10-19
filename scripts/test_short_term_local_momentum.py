#!/usr/bin/env python3
import csv, json, math
from pathlib import Path
from datetime import datetime, timezone

TARGET=Path("docs/data/short_term_monthly_target_lulea.csv")
OUT=Path("docs/data/short_term_monthly_local_momentum_benchmark.json")
PRED=Path("docs/data/short_term_monthly_local_momentum_predictions.csv")
HORIZONS=[3,6,9,12]

def read_csv(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))

def fnum(x):
    try:
        if x is None or x=="": return None
        v=float(x); return v if math.isfinite(v) else None
    except: return None

def mi(s): return int(s[:4])*12+int(s[-2:])
def rmse(e): return math.sqrt(sum(x*x for x in e)/len(e)) if e else None
def mae(e): return sum(abs(x) for x in e)/len(e) if e else None
def bias(e): return sum(e)/len(e) if e else None
def pct(a,b): return 100*(a/b-1) if a is not None and b not in (None,0) else None

rows={r["month"]:r for r in read_csv(TARGET)}
months=sorted(rows,key=mi)
idx={mi(m):m for m in months}

def val(k):
    m=idx.get(k)
    return fnum(rows[m]["all_inmigrations"]) if m else None

def sum_range(start_k,end_k):
    vals=[val(k) for k in range(start_k,end_k+1)]
    return None if any(v is None for v in vals) else sum(vals)

preds=[]
summaries={}
for h in HORIZONS:
    hp=[]
    for origin in months:
        k=mi(origin)
        actual=sum_range(k+1,k+h)
        seasonal=sum_range(k-11,k-12+h)
        if actual is None or seasonal is None: continue

        # Recent local level adjustment:
        # compare last 3 or 6 observed months with same months one year earlier,
        # then scale the seasonal forecast by that ratio.
        arms={"seasonal_naive":seasonal}
        for w in [3,6]:
            recent=sum_range(k-w+1,k)
            recent_prev=sum_range(k-w+1-12,k-12)
            if recent is not None and recent_prev not in (None,0):
                ratio=recent/recent_prev
                arms[f"seasonal_x_recent_{w}m_ratio"]=seasonal*ratio

        # additive YoY change variant avoids multiplicative explosion.
        for w in [3,6]:
            recent=sum_range(k-w+1,k)
            recent_prev=sum_range(k-w+1-12,k-12)
            if recent is not None and recent_prev is not None:
                monthly_shift=(recent-recent_prev)/w
                arms[f"seasonal_plus_recent_{w}m_shift"]=seasonal+h*monthly_shift

        if len(arms)<5: continue
        rec={
          "horizon_months":h,"origin":origin,
          "target_end":idx.get(k+h),
          "actual":actual,
          "source_break_2025":1 if origin>="2025M01" else 0
        }
        for name,p in arms.items():
            rec[name]=p
            rec[name+"_error"]=p-actual
        hp.append(rec); preds.append(rec)

    arm_names=["seasonal_naive","seasonal_x_recent_3m_ratio","seasonal_x_recent_6m_ratio",
               "seasonal_plus_recent_3m_shift","seasonal_plus_recent_6m_shift"]
    sm={}
    for arm in arm_names:
        errs=[r[arm+"_error"] for r in hp]
        pre=[r[arm+"_error"] for r in hp if r["target_end"] and r["target_end"]<"2025M01"]
        post=[r[arm+"_error"] for r in hp if r["origin"]>="2025M01"]
        sm[arm]={
          "rmse":rmse(errs),"mae":mae(errs),"bias":bias(errs),
          "pre_2025_rmse":rmse(pre),"post_2025_rmse":rmse(post)
        }
    base=sm["seasonal_naive"]
    for arm in arm_names[1:]:
        sm[arm]["delta_rmse_pct_vs_seasonal"]=pct(sm[arm]["rmse"],base["rmse"])
        sm[arm]["delta_mae_pct_vs_seasonal"]=pct(sm[arm]["mae"],base["mae"])
    best=min(arm_names,key=lambda a: sm[a]["rmse"])
    summaries[str(h)]={
      "n_origins":len(hp),
      "first_origin":hp[0]["origin"] if hp else None,
      "last_origin":hp[-1]["origin"] if hp else None,
      "best_by_rmse":best,
      "arms":sm
    }

result={
 "status":"short_term_monthly_local_momentum_benchmark",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "purpose":"Test whether apparent recent gains can be explained by local migration level/momentum before crediting external indicators.",
 "target":"sum of all_inmigrations over t+1..t+h",
 "horizons_months":HORIZONS,
 "arms":[
   "seasonal_naive",
   "seasonal_x_recent_3m_ratio",
   "seasonal_x_recent_6m_ratio",
   "seasonal_plus_recent_3m_shift",
   "seasonal_plus_recent_6m_shift"
 ],
 "selection":"No tuning. All four local momentum formulas fixed before evaluation.",
 "summaries":summaries
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

cols=sorted({k for r in preds for k in r})
with PRED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(preds)
print(json.dumps(result,ensure_ascii=False,indent=2))
