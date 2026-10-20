#!/usr/bin/env python3
"""Build current rolling 12-month outmigration forecast for Lulea.

Locked monthly research specification:
- target: all_outmigrations
- horizon: next 12 months
- baseline: same future calendar months one year earlier
- feature: age 25-29 employment-rate YoY pp
- lag: 1 month
- backward window: 12 months
- Ridge alpha: 30
- minimum completed training origins: 24

This forecast is separate from the annual 25/75 outmigration model.
"""
import csv,json,math
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

F=Path("docs/data/short_term_monthly_candidate_family_2.csv")
T=Path("docs/data/short_term_monthly_target_lulea.csv")
OUT=Path("docs/data/outmigration_monthly_12m_current_forecast.json")

H=12
LAG=1
ALPHA=30.0
MIN_TRAIN=24
FEATURE="bas2_age25_29_sysselsattningsgrad_yoy_pp"

def read(p):
    with p.open(encoding="utf-8") as f:return list(csv.DictReader(f))
def num(x):
    try:
        if x in (None,""):return None
        v=float(x);return v if math.isfinite(v) else None
    except:return None
def mi(s):return int(s[:4])*12+int(s[-2:])
def ms(k):
    y=(k-1)//12; m=k-y*12
    return f"{y:04d}M{m:02d}"

fr={r["month"]:r for r in read(F)}
tr={r["month"]:r for r in read(T)}
months=sorted(tr,key=mi)

def actual_sum_after(origin):
    labs=[ms(mi(origin)+i) for i in range(1,H+1)]
    vals=[]
    for lab in labs:
        r=tr.get(lab)
        v=num(r.get("all_outmigrations")) if r else None
        if v is None:return None,labs[-1]
        vals.append(v)
    return sum(vals),labs[-1]

def seasonal_after(origin):
    future=[ms(mi(origin)+i) for i in range(1,H+1)]
    src=[ms(mi(x)-12) for x in future]
    vals=[]
    for lab in src:
        r=tr.get(lab)
        v=num(r.get("all_outmigrations")) if r else None
        if v is None:return None,future,src
        vals.append(v)
    return sum(vals),future,src

def x_for(origin):
    fm=ms(mi(origin)-LAG)
    r=fr.get(fm)
    return (num(r.get(FEATURE)) if r else None),fm

hist=[]
for origin in months:
    actual,end=actual_sum_after(origin)
    seasonal,_,_=seasonal_after(origin)
    x,fm=x_for(origin)
    if actual is None or seasonal is None or x is None:continue
    hist.append({"origin":origin,"target_end":end,"actual":actual,
                 "seasonal":seasonal,"residual":actual-seasonal,"x":x,"feature_month":fm})

# Latest origin with a lagged feature and a complete seasonal baseline.
eligible=[]
for origin in months:
    seasonal,future,src=seasonal_after(origin)
    x,fm=x_for(origin)
    if seasonal is not None and x is not None:
        eligible.append((origin,seasonal,future,src,x,fm))
if not eligible:
    raise SystemExit("No current origin with feature and seasonal baseline")
origin,seasonal,future,src,xcur,fm=max(eligible,key=lambda z:mi(z[0]))

train=[r for r in hist if mi(r["target_end"])<=mi(origin)]
if len(train)<MIN_TRAIN:
    raise SystemExit(f"Insufficient completed training origins: {len(train)}")

X=np.asarray([[r["x"]] for r in train],float)
y=np.asarray([r["residual"] for r in train],float)
model=make_pipeline(StandardScaler(),Ridge(alpha=ALPHA))
model.fit(X,y)
correction=float(model.predict(np.asarray([[xcur]],float))[0])
forecast=seasonal+correction

res={
 "status":"outmigration_monthly_12m_current_forecast",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "annual_outmigration_blend_changed":False,
 "annual_monthly_direct_integration":False,
 "origin":origin,
 "target_start":future[0],
 "target_end":future[-1],
 "seasonal_source_start":src[0],
 "seasonal_source_end":src[-1],
 "feature_month":fm,
 "feature":FEATURE,
 "feature_value_yoy_pp":xcur,
 "lag_months":LAG,
 "backward_window_months":12,
 "alpha":ALPHA,
 "n_completed_training_origins":len(train),
 "seasonal_baseline_count":seasonal,
 "monthly_module_correction_count":correction,
 "forecast_count_next_12_months":forecast,
 "difference_pct_vs_seasonal":100*correction/seasonal if seasonal else None,
 "interpretation":"Rolling next-12-month Lulea outmigration forecast; not a calendar-year annual-model replacement."
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(res,ensure_ascii=False,indent=2))
