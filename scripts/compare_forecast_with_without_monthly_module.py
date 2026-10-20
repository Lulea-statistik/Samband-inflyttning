#!/usr/bin/env python3
import csv, json, math
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

F2=Path("docs/data/short_term_monthly_candidate_family_2.csv")
TARGET=Path("docs/data/short_term_monthly_target_lulea.csv")
BACKTEST=Path("docs/data/short_term_rates_25_29_feature_count_comparison.json")
OUT=Path("docs/data/short_term_forecast_with_without_monthly_module.json")
PRED=Path("docs/data/short_term_forecast_with_without_monthly_module.csv")

FEATURES=[
 "bas2_age25_29_sysselsattningsgrad_yoy_pp",
 "bas2_age25_29_arbetskraftsdeltagande_yoy_pp"
]
HORIZONS=[3,6,9,12]
ALPHAS=[3.0,10.0]
LAGS=[1,2]
MIN_TRAIN=24

def read(p):
    with p.open(encoding="utf-8") as f:return list(csv.DictReader(f))
def num(x):
    try:
        if x in (None,""):return None
        v=float(x); return v if math.isfinite(v) else None
    except:return None
def mi(s): return int(s[:4])*12+int(s[-2:])
def ms(k):
    y=(k-1)//12
    m=k-y*12
    return f"{y:04d}M{m:02d}"
def rmse(e):return math.sqrt(sum(x*x for x in e)/len(e)) if e else None
def mae(e):return sum(abs(x) for x in e)/len(e) if e else None
def bias(e):return sum(e)/len(e) if e else None
def pct(a,b):return 100*(a/b-1) if a is not None and b not in (None,0) else None

f2={r["month"]:r for r in read(F2)}
tr={r["month"]:r for r in read(TARGET)}
actual_months=sorted(tr,key=mi)
latest_actual=max(actual_months,key=mi)

def target_sum_after(origin,h):
    k=mi(origin)
    labs=[ms(k+i) for i in range(1,h+1)]
    vals=[]
    for lab in labs:
        r=tr.get(lab)
        v=num(r.get("all_inmigrations")) if r else None
        if v is None:return None,None
        vals.append(v)
    return sum(vals),labs[-1]

def seasonal_sum_after(origin,h):
    k=mi(origin)
    labs=[ms(k+i) for i in range(1,h+1)]
    vals=[]
    src=[]
    for lab in labs:
        prev=ms(mi(lab)-12)
        r=tr.get(prev)
        v=num(r.get("all_inmigrations")) if r else None
        if v is None:return None,None,None
        vals.append(v);src.append(prev)
    return sum(vals),labs,src

def x_for(origin,lag):
    fm=ms(mi(origin)-lag)
    r=f2.get(fm)
    if not r:return None,None
    x=[num(r.get(c)) for c in FEATURES]
    if any(v is None for v in x):return None,None
    return x,fm

# Latest common current origin for lag 1 and lag 2, not after latest observed target month.
common_origins=[]
for lab in actual_months:
    ok=True
    for lag in LAGS:
        x,_=x_for(lab,lag)
        if x is None:ok=False;break
    if ok:common_origins.append(lab)
CURRENT_ORIGIN=max(common_origins,key=mi)

rows=[]
current=[]
summary={}
for h in HORIZONS:
    hist=[]
    for origin in actual_months:
        actual,end=target_sum_after(origin,h)
        seasonal,_,_=seasonal_sum_after(origin,h)
        if actual is None or seasonal is None:continue
        xs={};valid=True
        for lag in LAGS:
            x,fm=x_for(origin,lag)
            if x is None:
                valid=False;break
            xs[lag]=(x,fm)
        if not valid:continue
        hist.append({
            "origin":origin,"target_end":end,"actual":actual,
            "seasonal":seasonal,"residual":actual-seasonal,"xs":xs
        })

    seasonal_current,target_months,seasonal_source=seasonal_sum_after(CURRENT_ORIGIN,h)
    hs={}
    for alpha in ALPHAS:
        for lag in LAGS:
            key=f"alpha{int(alpha)}_lag{lag}"
            xcur,fm=x_for(CURRENT_ORIGIN,lag)
            train=[r for r in hist if mi(r["target_end"])<=mi(CURRENT_ORIGIN)]
            if len(train)<MIN_TRAIN or seasonal_current is None or xcur is None:
                hs[key]={"available":False,"n_train":len(train)}
                continue
            X=np.asarray([r["xs"][lag][0] for r in train],dtype=float)
            y=np.asarray([r["residual"] for r in train],dtype=float)
            model=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
            model.fit(X,y)
            correction=float(model.predict(np.asarray([xcur],dtype=float))[0])
            with_module=seasonal_current+correction
            rec={
              "origin":CURRENT_ORIGIN,
              "horizon_months":h,
              "alpha":alpha,
              "lag_months":lag,
              "feature_month":fm,
              "target_start":target_months[0],
              "target_end":target_months[-1],
              "seasonal_source_start":seasonal_source[0],
              "seasonal_source_end":seasonal_source[-1],
              "without_monthly_module":seasonal_current,
              "monthly_module_correction":correction,
              "with_monthly_module":with_module,
              "difference_count":correction,
              "difference_pct_vs_without":100*correction/seasonal_current if seasonal_current else None,
              "n_train":len(train)
            }
            rows.append(rec);current.append(rec)
            hs[key]=rec
    summary[str(h)]=hs

# Historical marginal value from the already locked common-origin two-feature backtest.
bt=json.loads(BACKTEST.read_text(encoding="utf-8"))
historical={}
for h in HORIZONS:
    hh={}
    for alpha in ALPHAS:
        s=bt["summaries"][str(h)][str(alpha)]
        aa={}
        for lag in LAGS:
            arm=f"both_rates_lag{lag}"
            st=s["stats"][arm]
            aa[f"lag{lag}"]={
              "n_origins":s["n_origins"],
              "without_monthly_module":{
                "rmse":s["stats"]["seasonal"]["rmse"],
                "mae":s["stats"]["seasonal"]["mae"],
                "bias":s["stats"]["seasonal"]["bias"]
              },
              "with_monthly_module":{
                "rmse":st["rmse"],"mae":st["mae"],"bias":st["bias"]
              },
              "delta_rmse_pct":st["delta_rmse_pct_vs_seasonal"],
              "delta_mae_pct":st["delta_mae_pct_vs_seasonal"]
            }
        hh[str(alpha)]=aa
    historical[str(h)]=hh

result={
 "status":"short_term_forecast_with_without_monthly_module",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "current_origin":CURRENT_ORIGIN,
 "latest_observed_target_month":latest_actual,
 "without_monthly_module_definition":"seasonal naive: same future calendar months one year earlier",
 "with_monthly_module_definition":"same seasonal-naive baseline plus rates_25_29 residual correction",
 "monthly_module":{
   "backward_window_months":12,
   "features":FEATURES,
   "alphas":ALPHAS,
   "lags_months":LAGS
 },
 "core4_note":"Frozen long-term core-4 is unchanged. The previously tested direct annual-core4-times-seasonal-share monthly bridge was rejected, so it is not reused here.",
 "current_forecasts":summary,
 "historical_common_origin_performance":historical
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
with PRED.open("w",newline="",encoding="utf-8") as f:
    cols=list(rows[0].keys()) if rows else []
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
print(json.dumps(result,ensure_ascii=False,indent=2))
