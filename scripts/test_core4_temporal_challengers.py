#!/usr/bin/env python3
"""Evaluate pre-specified temporal challengers on top of frozen core-4.

Structural core-4 remains unchanged.
Temporal research challengers:
A) annual momentum = lag1 inflow - lag2 inflow
B) 3-year linear slope in inflow using t-3,t-2,t-1

Protocol:
- 6-year rolling training window
- one-year-ahead forecast
- same 290 municipalities and same forecast years as core-4 historical reconstruction
- temporal features use only pre-outcome information
- no variable reselection
- research only, no production change
"""
import json, re
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression

D=Path("docs/data")
base_bt=json.loads((D/"three_year_forecast_core4_historical_reconstructed_backtest.json").read_text(encoding="utf-8"))
features=base_bt["features"]
target="inflyttning_per_1000"
WINDOW=6

panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)
panel=panel.sort_values(["kommun_kod","year"]).copy()

# Build purely historical temporal features from observed inflow series.
g=panel.groupby("kommun_kod",group_keys=False)
panel["lag1_inflow"]=g[target].shift(1)
panel["lag2_inflow"]=g[target].shift(2)
panel["lag3_inflow"]=g[target].shift(3)
panel["momentum_1y"]=panel["lag1_inflow"]-panel["lag2_inflow"]
# slope across t-3,t-2,t-1 for equally spaced x = 0,1,2:
# slope = (y_last-y_first)/2
panel["trend_3y_slope"]=(panel["lag1_inflow"]-panel["lag3_inflow"])/2.0

# Reconstruct the two source-limited core features exactly as historical backtest did.
s=requests.Session()
s.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-temporal-challenger/1.0"})

kol_rows=[]
for year in range(2010,2026):
    r=s.get(f"https://api.kolada.se/v3/data/kpi/N03937/year/{year}",
            params={"region_type":"municipality","per_page":5000},timeout=90)
    r.raise_for_status()
    for rec in r.json().get("values",[]):
        code=str(rec.get("municipality","")).zfill(4)
        if not re.fullmatch(r"\d{4}",code): continue
        total=next((x.get("value") for x in rec.get("values",[])
                    if x.get("gender")=="T" and x.get("value") is not None),None)
        if total is not None:
            kol_rows.append({"kommun_kod":code,"year":year+1,
                             "lag1_kolada_arbetslosa_18_65_pct":float(total)})
kol=pd.DataFrame(kol_rows)

url="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T04"
meta=s.get(url,timeout=90); meta.raise_for_status(); meta=meta.json()
vars={v["code"]:v for v in meta["variables"]}
regions=[x for x in vars["Region"]["values"] if re.fullmatch(r"\d{4}",str(x))]
years=[str(y) for y in vars["Tid"]["values"] if str(y).isdigit() and 1990<=int(y)<=2025]

def js2long(js):
    dims=js["id"]; sizes=js["size"]; values=js["value"]; cats=[]
    for d in dims:
        idx=js["dimension"][d]["category"]["index"]
        cats.append(sorted(idx,key=idx.get) if isinstance(idx,dict) else list(idx))
    out=[]
    for flat,v in enumerate(values):
        if v is None: continue
        rem=flat; pos=[]
        for sz in reversed(sizes):
            pos.append(rem%sz); rem//=sz
        pos=list(reversed(pos))
        row={d:cats[i][pos[i]] for i,d in enumerate(dims)}
        row["value"]=float(v); out.append(row)
    return pd.DataFrame(out)

parts=[]
for yy in years:
    q={"query":[
      {"code":"Region","selection":{"filter":"item","values":regions}},
      {"code":"Hustyp","selection":{"filter":"item","values":vars["Hustyp"]["values"]}},
      {"code":"Upplatelseform","selection":{"filter":"item","values":vars["Upplatelseform"]["values"]}},
      {"code":"ContentsCode","selection":{"filter":"item","values":["BO0104AH"]}},
      {"code":"Tid","selection":{"filter":"item","values":[yy]}}
    ],"response":{"format":"json-stat2"}}
    rr=s.post(url,json=q,timeout=120)
    if rr.status_code==403:
        for batch in [regions[:145],regions[145:]]:
            q2=json.loads(json.dumps(q)); q2["query"][0]["selection"]["values"]=batch
            r2=s.post(url,json=q2,timeout=120); r2.raise_for_status()
            parts.append(js2long(r2.json()))
    else:
        rr.raise_for_status(); parts.append(js2long(rr.json()))

h=pd.concat(parts,ignore_index=True)
h["Region"]=h["Region"].astype(str).str.zfill(4)
ht=(h.groupby(["Region","Tid"],as_index=False)["value"].sum()
      .rename(columns={"Region":"kommun_kod","Tid":"source_year","value":"bostader_totalt"}))
ht["source_year"]=ht["source_year"].astype(int)
ht=ht.sort_values(["kommun_kod","source_year"])
ht["lag1_bostadsbestandsforandring_pct"]=100*ht.groupby("kommun_kod")["bostader_totalt"].pct_change(fill_method=None)
ht["year"]=ht["source_year"]+1
ht=ht[["kommun_kod","year","lag1_bostadsbestandsforandring_pct"]]

x=(panel[["kommun_kod","year",target,
          "lag1_inflyttning_per_1000","lag1_utflyttning_per_1000",
          "momentum_1y","trend_3y_slope"]]
   .merge(kol,on=["kommun_kod","year"],how="left")
   .merge(ht,on=["kommun_kod","year"],how="left"))

models={
 "core4":features,
 "core4_plus_momentum1y":features+["momentum_1y"],
 "core4_plus_trend3y":features+["trend_3y_slope"],
}

def metrics(y,p):
    e=np.asarray(p)-np.asarray(y)
    return {
      "rmse":float(np.sqrt(np.mean(e**2))),
      "mae":float(np.mean(np.abs(e))),
      "bias":float(np.mean(e)),
      "median_ae":float(np.median(np.abs(e)))
    }

forecast_years=[r["forecast_year"] for r in base_bt["yearly_results"] if r["window_years"]==6]
results=[]
for fy in forecast_years:
    train_years=list(range(fy-WINDOW,fy))
    for name,fs in models.items():
        need=["kommun_kod","year",target]+fs
        sets=[]
        for yy in train_years+[fy]:
            sets.append(set(x.loc[x.year==yy,need].dropna()["kommun_kod"]))
        common=set.intersection(*sets)
        if len(common)!=290: continue
        tr=x[x.year.isin(train_years)&x.kommun_kod.isin(common)][need].dropna()
        te=x[(x.year==fy)&x.kommun_kod.isin(common)][need].dropna()
        if len(tr)!=290*WINDOW or len(te)!=290: continue
        model=make_pipeline(StandardScaler(),LinearRegression()).fit(tr[fs],tr[target])
        p=model.predict(te[fs])
        m=metrics(te[target],p)
        li=np.flatnonzero(te["kommun_kod"].to_numpy()=="2580")
        lulea=None
        if len(li)==1:
            i=int(li[0])
            lulea={"actual":float(te.iloc[i][target]),
                   "prediction":float(p[i]),
                   "residual_prediction_minus_actual":float(p[i]-te.iloc[i][target])}
        lr=model.named_steps["linearregression"]; sc=model.named_steps["standardscaler"]
        raw={f:float(c/s) for f,c,s in zip(fs,lr.coef_,sc.scale_)}
        results.append({
          "model":name,"forecast_year":fy,"training_years":train_years,
          **m,"lulea":lulea,"raw_coefficients":raw
        })

summary={}
for name in models:
    rr=[r for r in results if r["model"]==name]
    summary[name]={
      "n_forecasts":len(rr),
      "mean_rmse":float(np.mean([r["rmse"] for r in rr])) if rr else None,
      "median_rmse":float(np.median([r["rmse"] for r in rr])) if rr else None,
      "mean_mae":float(np.mean([r["mae"] for r in rr])) if rr else None,
      "mean_abs_bias":float(np.mean([abs(r["bias"]) for r in rr])) if rr else None,
      "mean_lulea_abs_error":float(np.mean([abs(r["lulea"]["residual_prediction_minus_actual"]) for r in rr])) if rr else None
    }

base=summary["core4"]["mean_rmse"]
for name in ["core4_plus_momentum1y","core4_plus_trend3y"]:
    if summary[name]["mean_rmse"] is not None:
        summary[name]["rmse_change_vs_core4_pct"]=100*(summary[name]["mean_rmse"]/base-1)

out={
 "status":"core4_temporal_challenger_research_backtest",
 "production_changed":False,
 "structural_core4_changed":False,
 "temporal_module_status":"research_only",
 "primary_window_years":6,
 "forecast_years":forecast_years,
 "challengers":{
   "core4_plus_momentum1y":"adds lag1 inflow minus lag2 inflow",
   "core4_plus_trend3y":"adds slope across inflow at t-3,t-2,t-1"
 },
 "summary":summary,
 "yearly_results":results,
 "guardrails":[
   "No structural variable reselection.",
   "No production promotion from this diagnostic alone.",
   "Temporal features use only information available before each forecast year.",
   "Historical predictor vintages are reconstructed current histories, not exact archived vintages."
 ]
}
(D/"three_year_forecast_core4_temporal_challenger_backtest.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"summary":summary,"yearly_results":results},ensure_ascii=False,indent=2))
