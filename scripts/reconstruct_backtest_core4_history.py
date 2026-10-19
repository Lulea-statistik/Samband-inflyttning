#!/usr/bin/env python3
"""Reconstruct historical core-4 predictors from current source histories and run rolling-origin backtests.

Frozen variable definitions:
- lag1_inflyttning_per_1000
- lag1_utflyttning_per_1000
- lag1_kolada_arbetslosa_18_65_pct (N03937, gender T)
- lag1_bostadsbestandsforandring_pct

Primary backtest:
- fixed 6-year training window
- one-year-ahead forecast
- shift origin one year at a time as far back as source history allows

Historical reconstruction caveat:
These are current historical source values, not archived values captured at each old forecast origin.
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
lock=json.loads((D/"three_year_forecast_frozen_candidate_set.json").read_text(encoding="utf-8"))
features=lock["features"]
target="inflyttning_per_1000"
PRIMARY_WINDOW=6
SENS=[3,4,5]

panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)
base=panel[["kommun_kod","year",target,"lag1_inflyttning_per_1000","lag1_utflyttning_per_1000"]].copy()

s=requests.Session()
s.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-core4-history/1.0"})

# ---- Kolada N03937 historical totals ----
kol_rows=[]
for year in range(2010,2026):
    r=s.get(
      f"https://api.kolada.se/v3/data/kpi/N03937/year/{year}",
      params={"region_type":"municipality","per_page":5000},
      timeout=90
    )
    r.raise_for_status()
    vals=r.json().get("values",[])
    for rec in vals:
        code=str(rec.get("municipality","")).zfill(4)
        if not re.fullmatch(r"\d{4}",code): continue
        total=next((x.get("value") for x in rec.get("values",[])
                    if x.get("gender")=="T" and x.get("value") is not None),None)
        if total is not None:
            kol_rows.append({"kommun_kod":code,"source_year":year,"n03937":float(total)})
kol=pd.DataFrame(kol_rows)

# target year Y uses lag1 source year Y-1
kol["year"]=kol["source_year"]+1
kol=kol.rename(columns={"n03937":"lag1_kolada_arbetslosa_18_65_pct"})
kol=kol[["kommun_kod","year","lag1_kolada_arbetslosa_18_65_pct"]]

# ---- SCB housing totals ----
url="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T04"
meta=s.get(url,timeout=90); meta.raise_for_status(); meta=meta.json()
vars={v["code"]:v for v in meta["variables"]}
regions=[x for x in vars["Region"]["values"] if re.fullmatch(r"\d{4}",str(x))]
years=[str(y) for y in vars["Tid"]["values"] if str(y).isdigit() and 1990<=int(y)<=2025]
query={
 "query":[
  {"code":"Region","selection":{"filter":"item","values":regions}},
  {"code":"Hustyp","selection":{"filter":"item","values":vars["Hustyp"]["values"]}},
  {"code":"Upplatelseform","selection":{"filter":"item","values":vars["Upplatelseform"]["values"]}},
  {"code":"ContentsCode","selection":{"filter":"item","values":["BO0104AH"]}},
  {"code":"Tid","selection":{"filter":"item","values":years}}
 ],
 "response":{"format":"json-stat2"}
}
rr=s.post(url,json=query,timeout=180); rr.raise_for_status(); js=rr.json()

def jsonstat_to_long(js):
    dims=js["id"]; sizes=js["size"]; values=js["value"]
    cats=[]
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

h=jsonstat_to_long(js)
h["Region"]=h["Region"].astype(str).str.zfill(4)
ht=(h.groupby(["Region","Tid"],as_index=False)["value"].sum()
      .rename(columns={"Region":"kommun_kod","Tid":"source_year","value":"bostader_totalt"}))
ht["source_year"]=ht["source_year"].astype(int)
ht=ht.sort_values(["kommun_kod","source_year"])
ht["bostadsbestandsforandring_pct"]=100*ht.groupby("kommun_kod")["bostader_totalt"].pct_change(fill_method=None)
# target Y uses predictor measured at Y-1
ht["year"]=ht["source_year"]+1
ht=ht.rename(columns={"bostadsbestandsforandring_pct":"lag1_bostadsbestandsforandring_pct"})
ht=ht[["kommun_kod","year","lag1_bostadsbestandsforandring_pct"]]

x=(base.merge(kol,on=["kommun_kod","year"],how="left")
       .merge(ht,on=["kommun_kod","year"],how="left"))

need=["kommun_kod","year",target]+features

coverage=[]
eligible=[]
for year in sorted(int(y) for y in x["year"].dropna().unique()):
    q=x[x.year==year][need].dropna()
    n=int(q["kommun_kod"].nunique())
    coverage.append({"year":year,"complete_municipalities":n})
    if n==290: eligible.append(year)

def met(y,p):
    e=np.asarray(p)-np.asarray(y)
    return {"rmse":float(np.sqrt(np.mean(e**2))),
            "mae":float(np.mean(np.abs(e))),
            "bias":float(np.mean(e)),
            "median_ae":float(np.median(np.abs(e)))}

results=[]
preds=[]
for window in SENS+[PRIMARY_WINDOW]:
    for fy in eligible:
        train_years=list(range(fy-window,fy))
        if not all(y in eligible for y in train_years): continue
        sets=[]
        for yy in train_years+[fy]:
            sets.append(set(x.loc[x.year==yy,need].dropna()["kommun_kod"]))
        common=set.intersection(*sets)
        if len(common)!=290: continue
        tr=x[x.year.isin(train_years)&x.kommun_kod.isin(common)][need].dropna().copy()
        te=x[(x.year==fy)&x.kommun_kod.isin(common)][need].dropna().copy()
        if len(tr)!=290*window or len(te)!=290: continue
        model=make_pipeline(StandardScaler(),LinearRegression()).fit(tr[features],tr[target])
        p=model.predict(te[features])
        m=met(te[target],p)
        l=te.reset_index(drop=True)
        li=l.index[l.kommun_kod=="2580"].tolist()
        lulea=None
        if li:
            i=li[0]
            lulea={"actual":float(l.loc[i,target]),"prediction":float(p[i]),
                   "residual_prediction_minus_actual":float(p[i]-l.loc[i,target])}
        results.append({"window_years":window,"forecast_year":fy,"training_years":train_years,
                        "n_train":len(tr),"n_test":len(te),**m,"lulea":lulea})
        for (_,row),pr in zip(te.iterrows(),p):
            preds.append({"window_years":window,"forecast_year":fy,"kommun_kod":row.kommun_kod,
                          "actual":float(row[target]),"prediction":float(pr),
                          "residual_prediction_minus_actual":float(pr-row[target])})

summary={}
for w in SENS+[PRIMARY_WINDOW]:
    rr=[r for r in results if r["window_years"]==w]
    summary[str(w)]={"forecast_count":len(rr)}
    if rr:
        summary[str(w)].update({
          "first_forecast_year":min(r["forecast_year"] for r in rr),
          "last_forecast_year":max(r["forecast_year"] for r in rr),
          "mean_rmse":float(np.mean([r["rmse"] for r in rr])),
          "median_rmse":float(np.median([r["rmse"] for r in rr])),
          "mean_mae":float(np.mean([r["mae"] for r in rr])),
          "mean_abs_bias":float(np.mean([abs(r["bias"]) for r in rr])),
          "mean_lulea_absolute_error":float(np.mean([abs(r["lulea"]["residual_prediction_minus_actual"]) for r in rr if r["lulea"]]))
        })

out={
 "status":"core4_historical_reconstructed_rolling_origin_backtest",
 "production_changed":False,
 "selection_phase_closed":True,
 "features":features,
 "primary_window_years":PRIMARY_WINDOW,
 "sensitivity_windows_years":SENS,
 "forecast_horizon_years":1,
 "eligible_complete_years":eligible,
 "coverage":coverage,
 "summary_by_window":summary,
 "yearly_results":results,
 "source_reconstruction":{
   "N03937":"current Kolada historical API, gender T, shifted one year",
   "housing":"current SCB BO0104T04 totals, annual pct_change, shifted one year",
   "migration":"existing panel lag1 migration variables"
 },
 "limitations":[
   "Not strict historical as-of: current source histories may include later revisions.",
   "N03937 age definition is 18-64 through 2022 and 18-65 from 2023.",
   "No variable reselection or model-form tuning occurs."
 ]
}
(D/"three_year_forecast_core4_historical_reconstructed_backtest.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
pd.DataFrame(preds).to_csv(D/"three_year_forecast_core4_historical_reconstructed_predictions.csv",index=False)
print(json.dumps({
 "eligible_complete_years":eligible,
 "summary_by_window":summary,
 "primary_yearly_results":[r for r in results if r["window_years"]==PRIMARY_WINDOW]
},ensure_ascii=False,indent=2))
