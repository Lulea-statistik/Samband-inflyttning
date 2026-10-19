#!/usr/bin/env python3
"""Diagnose weak core-4 rolling-origin years 2017-2019.

Focus:
- panel-wide level shift in target
- shifts in frozen predictors
- OLS coefficient drift by rolling window
- residual distribution and whether errors are broad or concentrated
- Lulea compared with national panel

No variable reselection, no production change.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression

D=Path("docs/data")
bt=json.loads((D/"three_year_forecast_core4_historical_reconstructed_backtest.json").read_text(encoding="utf-8"))
pred=pd.read_csv(D/"three_year_forecast_core4_historical_reconstructed_predictions.csv",dtype={"kommun_kod":str})
pred["kommun_kod"]=pred["kommun_kod"].astype(str).str.zfill(4)

features=bt["features"]
target="inflyttning_per_1000"
panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)

# Reuse reconstructed predictor values from the previous workflow output logic:
# current panel already has migration lag; derive current historical N03937/housing
# from backtest predictions is insufficient, so reconstruct by reading the script's
# output years from the panel where available and use source-reconstructed values
# from the same workflow by rebuilding lightweight from saved prediction years.
# For coefficient drift we can use the already reconstructed backtest by re-running
# the prior reconstruction script's data preparation through a compact import-free path:
import requests, re
s=requests.Session()
s.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-core4-diagnostic/1.0"})

# Kolada
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

# Housing annual total from SCB, batched by year
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

x=(panel[["kommun_kod","year",target,"lag1_inflyttning_per_1000","lag1_utflyttning_per_1000"]]
   .merge(kol,on=["kommun_kod","year"],how="left")
   .merge(ht,on=["kommun_kod","year"],how="left"))

# Year-level shifts
year_summary=[]
for y in range(2011,2025):
    q=x[x.year==y].dropna(subset=[target]+features)
    if q.empty: continue
    rec={"year":y,"n":len(q),"target_mean":float(q[target].mean()),"target_median":float(q[target].median())}
    for f in features:
        rec[f+"_mean"]=float(q[f].mean())
    year_summary.append(rec)

# Coefficient drift for 6-year windows
coef_rows=[]
for r in bt["yearly_results"]:
    if r["window_years"]!=6: continue
    fy=r["forecast_year"]; tys=r["training_years"]
    tr=x[x.year.isin(tys)].dropna(subset=[target]+features)
    te=x[x.year==fy].dropna(subset=[target]+features)
    common=set(te.kommun_kod)
    for yy in tys:
        common &= set(tr[tr.year==yy].kommun_kod)
    tr=tr[tr.kommun_kod.isin(common)]
    te=te[te.kommun_kod.isin(common)]
    pipe=make_pipeline(StandardScaler(),LinearRegression()).fit(tr[features],tr[target])
    sc=pipe.named_steps["standardscaler"]; lr=pipe.named_steps["linearregression"]
    raw_coef={f:float(c/s) for f,c,s in zip(features,lr.coef_,sc.scale_)}
    raw_intercept=float(lr.intercept_ - np.sum(lr.coef_*sc.mean_/sc.scale_))
    coef_rows.append({
      "forecast_year":fy,
      "training_years":tys,
      "intercept_raw":raw_intercept,
      **raw_coef
    })

# Residual concentration for each 6-year forecast year
res_diag=[]
for y in range(2017,2025):
    q=pred[(pred.window_years==6)&(pred.forecast_year==y)].copy()
    if q.empty: continue
    ae=q["residual_prediction_minus_actual"].abs()
    e=q["residual_prediction_minus_actual"]
    res_diag.append({
      "forecast_year":y,
      "n":len(q),
      "mean_error":float(e.mean()),
      "median_error":float(e.median()),
      "share_overpredicted":float((e>0).mean()),
      "p10_error":float(e.quantile(.10)),
      "p90_error":float(e.quantile(.90)),
      "share_abs_error_gt_10":float((ae>10).mean()),
      "top_10_abs_error_share":float(ae.nlargest(10).sum()/ae.sum())
    })

# Compare weak vs stronger eras
weak=[2017,2018,2019]
strong=[2020,2021,2022,2024]
ys=pd.DataFrame(year_summary)
era={}
for name,yrs in [("weak_2017_2019",weak),("strong_2020_2022_2024",strong)]:
    q=ys[ys.year.isin(yrs)]
    era[name]={c:float(q[c].mean()) for c in q.columns if c not in ["year","n"]}

out={
 "status":"core4_rolling_origin_weak_year_diagnostic",
 "production_changed":False,
 "selection_phase_closed":True,
 "weak_years":[2017,2018,2019],
 "year_summary":year_summary,
 "six_year_raw_coefficient_drift":coef_rows,
 "residual_diagnostics":res_diag,
 "era_comparison":era,
 "interpretation_rules":[
   "No variable additions/removals are evaluated.",
   "Diagnostics are descriptive and do not authorize retuning.",
   "Historical source values remain reconstructed current-history values, not exact archived vintages."
 ]
}
(D/"three_year_forecast_core4_weak_year_diagnostic.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({
 "era_comparison":era,
 "residual_diagnostics":res_diag,
 "six_year_raw_coefficient_drift":coef_rows
},ensure_ascii=False,indent=2))
