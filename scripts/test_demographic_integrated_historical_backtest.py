#!/usr/bin/env python3
"""Integrated historical backtest for demographic balance components.

Birth core:
  3-year Ridge on lag1_fodelsetal_per_100, with Lulea-specific rolling 3-origin bias correction
Death core:
  3-year Ridge on lag1_dodstal_per_1000 + lag1_bas_pensionarer_andel_pct
Residual correction:
  rolling mean of previous 3 observed accounting residuals for Lulea

Migration remains observed in this diagnostic backtest so that birth/death/residual
integration can be validated cleanly before substituting frozen migration forecasts.
No production model is changed.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold

D=Path("docs/data")
ALPHAS=[0.0,0.3,3.0,30.0]

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

SPECS={
 "birth":{"target":"fodelsetal_per_100","features":["lag1_fodelsetal_per_100"]},
 "death":{"target":"dodstal_per_1000","features":["lag1_dodstal_per_1000","lag1_bas_pensionarer_andel_pct"]}
}

def mdl(a):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=a))

def choose_alpha(tr,target,features):
    X=tr[features]; y=tr[target].to_numpy(float); g=tr.kommun_kod.to_numpy()
    cv=GroupKFold(n_splits=5); scores=[]
    for a in ALPHAS:
        ee=[]
        for ti,vi in cv.split(X,y,g):
            m=mdl(a);m.fit(X.iloc[ti],y[ti]);ee.extend((y[vi]-m.predict(X.iloc[vi])).tolist())
        scores.append((float(np.sqrt(np.mean(np.square(ee)))),a))
    return min(scores,key=lambda x:x[0])[1]

def forecast_rate(target,features,year):
    train_years=list(range(year-3,year))
    tr=q[q.year.isin(train_years)].copy()
    te=q[q.year.eq(year)].copy()
    if len(tr)!=870 or len(te)!=290:return None,None,None
    a=choose_alpha(tr,target,features)
    m=mdl(a);m.fit(tr[features],tr[target].to_numpy(float))
    pr=m.predict(te[features])
    return te.reset_index(drop=True),pr,a

rows=[]
lulea_birth_errors=[]
for y in range(2017,2025):
    bte,bpr,ba=forecast_rate(SPECS["birth"]["target"],SPECS["birth"]["features"],y)
    dte,dpr,da=forecast_rate(SPECS["death"]["target"],SPECS["death"]["features"],y)
    if bte is None or dte is None: continue
    # Same row ordering because both come from q year slice sorted by municipality.
    if not np.array_equal(bte.kommun_kod.to_numpy(),dte.kommun_kod.to_numpy()):
        raise RuntimeError("Birth/death prediction rows misaligned")
    for i,r in bte.iterrows():
        mean_pop=float(r.mean_population)
        birth_rate_pred=float(bpr[i])
        birth_bias_corr=0.0
        if r.kommun_kod=="2580" and len(lulea_birth_errors)>=3:
            birth_bias_corr=float(np.mean(lulea_birth_errors[-3:]))
        birth_rate_used=birth_rate_pred+birth_bias_corr
        births_pred=birth_rate_used*mean_pop/100.0
        deaths_pred=float(dpr[i])*mean_pop/1000.0
        residual_hist=q[(q.kommun_kod.eq(r.kommun_kod))&(q.year<y)].tail(3).residual_obs.dropna()
        residual_pred=float(residual_hist.mean()) if len(residual_hist)==3 else 0.0
        pred_change=births_pred-deaths_pred+float(r.inflyttade)-float(r.utflyttade)+residual_pred
        actual_change=float(r.delta_population)
        rows.append({
          "year":y,"kommun_kod":r.kommun_kod,
          "birth_rate_pred_raw":birth_rate_pred,"birth_bias_correction":birth_bias_corr,
          "birth_rate_pred":birth_rate_used,"death_rate_pred":float(dpr[i]),
          "births_pred":births_pred,"deaths_pred":deaths_pred,
          "inflow_obs":float(r.inflyttade),"outflow_obs":float(r.utflyttade),
          "residual_pred":residual_pred,
          "pred_change":pred_change,"actual_change":actual_change,
          "error_actual_minus_prediction":actual_change-pred_change,
          "birth_alpha":ba,"death_alpha":da
        })
        if r.kommun_kod=="2580":
            actual_birth_rate=float(r.fodelsetal_per_100)
            lulea_birth_errors.append(actual_birth_rate-birth_rate_pred)

r=pd.DataFrame(rows)

def metrics(df):
    e=df.error_actual_minus_prediction.to_numpy(float)
    return {
      "n_rows":int(len(df)),
      "rmse_persons":float(np.sqrt(np.mean(e*e))),
      "mae_persons":float(np.mean(np.abs(e))),
      "bias_actual_minus_prediction":float(np.mean(e))
    }

out={
 "status":"demographic_integrated_historical_backtest",
 "production_changed":False,
 "migration_mode":"observed counts; frozen migration forecasts not yet substituted",
 "birth_core":{"window_years":3,"features":SPECS["birth"]["features"],
                 "lulea_bias_rule":"rolling mean of previous 3 raw Lulea birth-rate forecast errors"},
 "death_core":{"window_years":3,"features":SPECS["death"]["features"]},
 "residual_rule":"rolling mean of previous 3 observed residuals",
 "all_municipalities":metrics(r),
 "lulea":metrics(r[r.kommun_kod.eq("2580")]),
 "lulea_years":[
   {
    "year":int(x.year),"births_pred":float(x.births_pred),"deaths_pred":float(x.deaths_pred),
    "residual_pred":float(x.residual_pred),"pred_change":float(x.pred_change),
    "actual_change":float(x.actual_change),"error_actual_minus_prediction":float(x.error_actual_minus_prediction)
   } for x in r[r.kommun_kod.eq("2580")].itertuples(index=False)
 ]
}
(D/"demographic_integrated_historical_backtest.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
