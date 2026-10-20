#!/usr/bin/env python3
"""Full Lulea demographic component backtest with forecasted migration.

Components:
- Birth: 3y national lag1-only Ridge + rolling 3-origin Lulea bias correction.
- Death: 3y Ridge on lag1 death rate + lag1 pensioner share.
- Inflow: frozen Core4 OLS historical reconstructed rolling-origin predictions,
          primary 6-year window.
- Outflow: promoted 25% lag1-only 3y + 75% lag1-only 10y Ridge blend.
- Balance residual: rolling mean of previous 3 observed accounting residuals.

No observed migration count enters the forecasted population change.
Rate-to-count conversion uses population at Y-1 as the known exposure, avoiding
use of year-Y population in this first full one-step backtest.
No production model is changed.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")
ALPHAS=[0.0,0.1,1.0,10.0]
BIRTH_ALPHAS=[0.0,0.3,3.0,30.0]

p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
t=pd.read_csv(D/"demographic_birth_death_targets.csv",dtype={"kommun_kod":str})
t["kommun_kod"]=t["kommun_kod"].astype(str).str.zfill(4)
t=t.sort_values(["kommun_kod","year"])
t["lag1_fodelsetal_per_100"]=t.groupby("kommun_kod")["fodelsetal_per_100"].shift(1)
t["lag1_dodstal_per_1000"]=t.groupby("kommun_kod")["dodstal_per_1000"].shift(1)

q=p.merge(t,on=["kommun_kod","year"],how="inner",validate="one_to_one").sort_values(["kommun_kod","year"])
q["pop_prev"]=q.groupby("kommun_kod")["folkmangd"].shift(1)
q["delta_population"]=q["folkmangd"]-q["pop_prev"]
q["births_obs"]=q["fodelsetal_per_100"]*q["mean_population"]/100.0
q["deaths_obs"]=q["dodstal_per_1000"]*q["mean_population"]/1000.0
q["component_change_obs"]=q["births_obs"]-q["deaths_obs"]+q["inflyttade"]-q["utflyttade"]
q["residual_obs"]=q["delta_population"]-q["component_change_obs"]

# Frozen/reconstructed inflow Core4 predictions: primary 6-year window.
inf=pd.read_csv(D/"three_year_forecast_core4_historical_reconstructed_predictions.csv",
                dtype={"kommun_kod":str})
inf["kommun_kod"]=inf["kommun_kod"].astype(str).str.zfill(4)
inf=inf[(inf.window_years==6)&(inf.kommun_kod=="2580")][
    ["forecast_year","prediction","actual"]
].rename(columns={"forecast_year":"year","prediction":"inflow_pred_per_1000",
                  "actual":"inflow_actual_per_1000"})

BIRTH_FEATURE=["lag1_fodelsetal_per_100"]
DEATH_FEATURE=["lag1_dodstal_per_1000","lag1_bas_pensionarer_andel_pct"]
OUT_FEATURE=["lag1_utflyttning_per_1000"]

def model(alpha):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),
                         Ridge(alpha=1e-10 if alpha==0 else alpha))

def choose_group_alpha(tr,target,features,alphas):
    X=tr[features];y=tr[target].to_numpy(float);g=tr.kommun_kod.to_numpy()
    cv=GroupKFold(n_splits=5); scores=[]
    for a in alphas:
        ee=[]
        for ti,vi in cv.split(X,y,g):
            m=model(a);m.fit(X.iloc[ti],y[ti]);ee.extend((y[vi]-m.predict(X.iloc[vi])).tolist())
        scores.append((float(np.sqrt(np.mean(np.square(ee)))),a))
    return min(scores,key=lambda x:(x[0],x[1]))[1]

def choose_out_alpha(tr):
    yrs=sorted(int(x) for x in tr.year.unique())
    vy=yrs[-1]
    fit=tr[tr.year<vy];val=tr[tr.year.eq(vy)]
    scores=[]
    for a in ALPHAS:
        m=model(a);m.fit(fit[OUT_FEATURE],fit["utflyttning_per_1000"])
        pr=m.predict(val[OUT_FEATURE]);e=pr-val["utflyttning_per_1000"].to_numpy(float)
        scores.append((float(np.sqrt(np.mean(e*e))),a))
    return min(scores,key=lambda x:(x[0],-x[1]))[1]

def outflow_forecast(year):
    # Use the full panel history for the promoted outflow model.
    # Do not truncate its 10y training window to the shorter birth/death target history.
    lu=p[p.year.eq(year)&p.kommun_kod.eq("2580")]
    if len(lu)!=1:return None
    preds=[]
    for w in [3,10]:
        tr=p[p.year.isin(range(year-w,year))].dropna(subset=OUT_FEATURE+["utflyttning_per_1000"]).copy()
        if len(tr)!=290*w:return None
        a=choose_out_alpha(tr)
        m=model(a);m.fit(tr[OUT_FEATURE],tr["utflyttning_per_1000"])
        preds.append((float(m.predict(lu[OUT_FEATURE])[0]),a))
    return 0.25*preds[0][0]+0.75*preds[1][0],preds

rows=[]
birth_raw_errors=[]
for year in sorted(set(inf.year).intersection(set(range(2017,2025)))):
    train=q[q.year.isin(range(year-3,year))].copy()
    te=q[q.year.eq(year)&q.kommun_kod.eq("2580")].copy()
    if len(train)!=870 or len(te)!=1:continue
    r=te.iloc[0]

    # Birth.
    ba=choose_group_alpha(train,"fodelsetal_per_100",BIRTH_FEATURE,BIRTH_ALPHAS)
    bm=model(ba);bm.fit(train[BIRTH_FEATURE],train["fodelsetal_per_100"])
    birth_raw=float(bm.predict(te[BIRTH_FEATURE])[0])
    birth_corr=float(np.mean(birth_raw_errors[-3:])) if len(birth_raw_errors)>=3 else 0.0
    birth_rate=birth_raw+birth_corr
    birth_raw_errors.append(float(r.fodelsetal_per_100)-birth_raw)

    # Death.
    da=choose_group_alpha(train,"dodstal_per_1000",DEATH_FEATURE,BIRTH_ALPHAS)
    dm=model(da);dm.fit(train[DEATH_FEATURE],train["dodstal_per_1000"])
    death_rate=float(dm.predict(te[DEATH_FEATURE])[0])

    # Migration.
    ir=inf[inf.year.eq(year)]
    if len(ir)!=1:continue
    inflow_rate=float(ir.inflow_pred_per_1000.iloc[0])
    of=outflow_forecast(year)
    if of is None:continue
    outflow_rate,oparts=of

    exposure=float(r.pop_prev)
    births=birth_rate*exposure/100.0
    deaths=death_rate*exposure/1000.0
    inflow=inflow_rate*exposure/1000.0
    outflow=outflow_rate*exposure/1000.0

    rh=q[(q.kommun_kod=="2580")&(q.year<year)].tail(3).residual_obs.dropna()
    residual_pred=float(rh.mean()) if len(rh)==3 else 0.0

    pred_change=births-deaths+inflow-outflow+residual_pred
    actual_change=float(r.delta_population)
    rows.append({
      "year":int(year),"population_prev":exposure,
      "birth_rate_pred":birth_rate,"death_rate_pred":death_rate,
      "inflow_rate_pred":inflow_rate,"outflow_rate_pred":outflow_rate,
      "births_pred":births,"deaths_pred":deaths,
      "inflow_pred":inflow,"outflow_pred":outflow,
      "residual_pred":residual_pred,
      "pred_change":pred_change,"actual_change":actual_change,
      "error_actual_minus_prediction":actual_change-pred_change,
      "birth_alpha":ba,"death_alpha":da,
      "outflow_alpha_3y":oparts[0][1],"outflow_alpha_10y":oparts[1][1]
    })

r=pd.DataFrame(rows)
e=r.error_actual_minus_prediction.to_numpy(float)
out={
 "status":"lulea_full_component_historical_backtest",
 "production_changed":False,
 "forecast_components":{
   "birth":"3y lag1-only Ridge + rolling 3-origin Lulea raw-error correction",
   "death":"3y lag1 death rate + lag1 pensioner share Ridge",
   "inflow":"frozen Core4 OLS reconstructed rolling-origin, 6y window",
   "outflow":"0.25 * lag1-only 3y + 0.75 * lag1-only 10y",
   "balance_residual":"rolling mean previous 3 observed accounting residuals"
 },
 "rate_to_count_exposure":"population at Y-1",
 "outflow_training_source":"full panel.csv history; not truncated by demographic target join",
 "observed_migration_used_in_forecast":False,
 "first_year":int(r.year.min()),"last_year":int(r.year.max()),"n_years":int(len(r)),
 "rmse_persons":float(np.sqrt(np.mean(e*e))),
 "mae_persons":float(np.mean(np.abs(e))),
 "bias_actual_minus_prediction":float(np.mean(e)),
 "years":rows
}
(D/"lulea_full_component_historical_backtest.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
