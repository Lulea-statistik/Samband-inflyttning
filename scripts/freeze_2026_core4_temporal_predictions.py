#!/usr/bin/env python3
"""Freeze prospective 2026 core-4 and core-4+3y-trend predictions.

Research-only temporal gate. This does not modify the production model.

Protocol locked before 2026 annual outcome:
- training target years: 2020-2025
- forecast target year: 2026
- baseline: frozen core-4 variable definitions, StandardScaler + OLS
- challenger: baseline + 3-year inflow trend
- no post-outcome refit, retuning or feature changes before scoring
- predictor year for 2026 is 2025
"""
import hashlib, json, re
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression

D=Path("docs/data")
OUT=D/"preoutcome_2026_core4_temporal"
OUT.mkdir(parents=True,exist_ok=True)
FEATURES=[
 "lag1_inflyttning_per_1000",
 "lag1_utflyttning_per_1000",
 "lag1_kolada_arbetslosa_18_65_pct",
 "lag1_bostadsbestandsforandring_pct"
]
TARGET="inflyttning_per_1000"
TRAIN_YEARS=list(range(2020,2026))
FORECAST_YEAR=2026

s=requests.Session()
s.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-2026-preoutcome-freeze/1.0"})

def dump(name,obj):
    p=OUT/name
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return p

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

# ---- SCB migration 2018-2025 ----
mig_url="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101J/Flyttningar97"
mig_meta=s.get(mig_url,timeout=90); mig_meta.raise_for_status(); mig_meta=mig_meta.json()
mv={v["code"]:v for v in mig_meta["variables"]}
regions=[x for x in mv["Region"]["values"] if re.fullmatch(r"\d{4}",str(x))]
years=[str(y) for y in mv["Tid"]["values"] if str(y).isdigit() and 2018<=int(y)<=2025]
# infer required dimension codes using known canonical names
qparts=[]
for code,v in mv.items():
    vals=v["values"]
    if code=="Region": sel=regions
    elif code=="Tid": sel=years
    elif code.lower().startswith("alder"): sel=[vals[0]] if len(vals)==1 else [x for x,t in zip(vals,v.get("valueTexts",[])) if "tot" in str(t).lower()] or [vals[0]]
    elif code.lower().startswith("kon"): sel=vals
    elif code=="ContentsCode": sel=[x for x in vals if x in ("BE0101AU","BE0101AV")]
    else: sel=vals
    qparts.append({"code":code,"selection":{"filter":"item","values":sel}})
mig_query={"query":qparts,"response":{"format":"json-stat2"}}
mr=s.post(mig_url,json=mig_query,timeout=180); mr.raise_for_status(); mig_js=mr.json()
dump("scb_migration_metadata.json",mig_meta); dump("scb_migration_query.json",mig_query); dump("scb_migration_values.json",mig_js)

# ---- SCB population 2018-2025 ----
pop_url="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101A/BefolkningNy"
pop_meta=s.get(pop_url,timeout=90); pop_meta.raise_for_status(); pop_meta=pop_meta.json()
pv={v["code"]:v for v in pop_meta["variables"]}
years_pop=[str(y) for y in pv["Tid"]["values"] if str(y).isdigit() and 2018<=int(y)<=2025]
qparts=[]
for code,v in pv.items():
    vals=v["values"]
    if code=="Region": sel=[x for x in vals if re.fullmatch(r"\d{4}",str(x))]
    elif code=="Tid": sel=years_pop
    elif code.lower().startswith("alder"): sel=[x for x,t in zip(vals,v.get("valueTexts",[])) if "tot" in str(t).lower()] or [vals[0]]
    elif code.lower().startswith("kon"): sel=vals
    elif code=="ContentsCode": sel=[x for x in vals if x=="BE0101N1"] or [vals[0]]
    else: sel=vals
    qparts.append({"code":code,"selection":{"filter":"item","values":sel}})
pop_query={"query":qparts,"response":{"format":"json-stat2"}}
pr=s.post(pop_url,json=pop_query,timeout=180); pr.raise_for_status(); pop_js=pr.json()
dump("scb_population_metadata.json",pop_meta); dump("scb_population_query.json",pop_query); dump("scb_population_values.json",pop_js)

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

mig=js2long(mig_js)
pop=js2long(pop_js)
# Normalize core keys
mig["Region"]=mig["Region"].astype(str).str.zfill(4)
pop["Region"]=pop["Region"].astype(str).str.zfill(4)
mig["Tid"]=mig["Tid"].astype(int); pop["Tid"]=pop["Tid"].astype(int)

# ContentsCode is expected in json-stat dimensions.
content_col="ContentsCode"
if content_col not in mig.columns: raise SystemExit("Migration ContentsCode missing")
magg=(mig.groupby(["Region","Tid",content_col],as_index=False)["value"].sum()
      .pivot(index=["Region","Tid"],columns=content_col,values="value").reset_index())
if "BE0101AU" not in magg or "BE0101AV" not in magg:
    raise SystemExit("Required migration contents missing")

pagg=pop.groupby(["Region","Tid"],as_index=False)["value"].sum().rename(columns={"value":"population"})
mp=magg.merge(pagg,on=["Region","Tid"],how="inner")
mp["inflyttning_per_1000"]=1000*mp["BE0101AU"]/mp["population"]
mp["utflyttning_per_1000"]=1000*mp["BE0101AV"]/mp["population"]
mp=mp.rename(columns={"Region":"kommun_kod","Tid":"year"})

# ---- Kolada N03937 2018-2025, preserve raw ----
kol_rows=[]
kol_files=[]
for y in range(2018,2026):
    r=s.get(f"https://api.kolada.se/v3/data/kpi/N03937/year/{y}",
            params={"region_type":"municipality","per_page":5000},timeout=90)
    r.raise_for_status(); js=r.json()
    p=dump(f"kolada_N03937_{y}.json",js); kol_files.append(p)
    for rec in js.get("values",[]):
        code=str(rec.get("municipality","")).zfill(4)
        if not re.fullmatch(r"\d{4}",code): continue
        total=next((x.get("value") for x in rec.get("values",[])
                    if x.get("gender")=="T" and x.get("value") is not None),None)
        if total is not None:
            kol_rows.append({"kommun_kod":code,"source_year":y,"n03937":float(total)})
kol=pd.DataFrame(kol_rows)

# ---- Housing 2017-2025, annual batched ----
h_url="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T04"
h_meta=s.get(h_url,timeout=90); h_meta.raise_for_status(); h_meta=h_meta.json()
dump("scb_housing_metadata.json",h_meta)
hv={v["code"]:v for v in h_meta["variables"]}
h_regions=[x for x in hv["Region"]["values"] if re.fullmatch(r"\d{4}",str(x))]
h_parts=[]; h_queries={}; h_raw={}
for y in range(2017,2026):
    yy=str(y)
    q={"query":[
      {"code":"Region","selection":{"filter":"item","values":h_regions}},
      {"code":"Hustyp","selection":{"filter":"item","values":hv["Hustyp"]["values"]}},
      {"code":"Upplatelseform","selection":{"filter":"item","values":hv["Upplatelseform"]["values"]}},
      {"code":"ContentsCode","selection":{"filter":"item","values":["BO0104AH"]}},
      {"code":"Tid","selection":{"filter":"item","values":[yy]}}
    ],"response":{"format":"json-stat2"}}
    h_queries[yy]=q
    rr=s.post(h_url,json=q,timeout=120)
    raws=[]
    if rr.status_code==403:
        for batch in [h_regions[:145],h_regions[145:]]:
            q2=json.loads(json.dumps(q)); q2["query"][0]["selection"]["values"]=batch
            r2=s.post(h_url,json=q2,timeout=120); r2.raise_for_status()
            js=r2.json(); raws.append(js); h_parts.append(js2long(js))
    else:
        rr.raise_for_status(); js=rr.json(); raws.append(js); h_parts.append(js2long(js))
    h_raw[yy]=raws
dump("scb_housing_queries.json",h_queries); dump("scb_housing_values_batched.json",h_raw)

h=pd.concat(h_parts,ignore_index=True)
h["Region"]=h["Region"].astype(str).str.zfill(4); h["Tid"]=h["Tid"].astype(int)
ht=(h.groupby(["Region","Tid"],as_index=False)["value"].sum()
      .rename(columns={"Region":"kommun_kod","Tid":"source_year","value":"bostader_totalt"}))
ht=ht.sort_values(["kommun_kod","source_year"])
ht["housing_change_pct"]=100*ht.groupby("kommun_kod")["bostader_totalt"].pct_change(fill_method=None)

# ---- Assemble target-year table 2020-2026 ----
rows=[]
for y in range(2020,2027):
    # target y uses migration y outcome if available; predictors from y-1
    base=mp[mp.year==y][["kommun_kod","inflyttning_per_1000"]].copy() if y<=2025 else pd.DataFrame({"kommun_kod":sorted(set(mp["kommun_kod"]))})
    prev=mp[mp.year==y-1][["kommun_kod","inflyttning_per_1000","utflyttning_per_1000"]].copy()
    prev=prev.rename(columns={"inflyttning_per_1000":"lag1_inflyttning_per_1000",
                              "utflyttning_per_1000":"lag1_utflyttning_per_1000"})
    ky=kol[kol.source_year==y-1][["kommun_kod","n03937"]].rename(columns={"n03937":"lag1_kolada_arbetslosa_18_65_pct"})
    hy=ht[ht.source_year==y-1][["kommun_kod","housing_change_pct"]].rename(columns={"housing_change_pct":"lag1_bostadsbestandsforandring_pct"})
    q=base.merge(prev,on="kommun_kod",how="inner").merge(ky,on="kommun_kod",how="inner").merge(hy,on="kommun_kod",how="inner")
    q["year"]=y
    rows.append(q)
x=pd.concat(rows,ignore_index=True)

# Temporal 3-year trend using observed inflow t-3,t-2,t-1
inflow=mp[["kommun_kod","year","inflyttning_per_1000"]].copy()
for lag in [1,3]:
    z=inflow.copy(); z["year"]=z["year"]+lag
    z=z.rename(columns={"inflyttning_per_1000":f"lag{lag}_trend_inflow"})
    x=x.merge(z,on=["kommun_kod","year"],how="left")
x["trend_3y_slope"]=(x["lag1_trend_inflow"]-x["lag3_trend_inflow"])/2.0

train=x[x.year.isin(TRAIN_YEARS)].dropna(subset=[TARGET]+FEATURES+["trend_3y_slope"]).copy()
forecast=x[x.year==FORECAST_YEAR].dropna(subset=FEATURES+["trend_3y_slope"]).copy()
common=set(forecast.kommun_kod)
for y in TRAIN_YEARS:
    common &= set(train[train.year==y].kommun_kod)
train=train[train.kommun_kod.isin(common)].copy()
forecast=forecast[forecast.kommun_kod.isin(common)].copy()
if len(common)!=290 or len(train)!=290*6 or len(forecast)!=290:
    raise SystemExit(f"Incomplete freeze: common={len(common)}, train={len(train)}, forecast={len(forecast)}")

models={
 "core4":{"features":FEATURES},
 "core4_plus_trend3y":{"features":FEATURES+["trend_3y_slope"]}
}
pred_out=forecast[["kommun_kod","year"]].copy()
model_meta={}
for name,spec in models.items():
    fs=spec["features"]
    model=make_pipeline(StandardScaler(),LinearRegression()).fit(train[fs],train[TARGET])
    pred_out[name+"_prediction_per_1000"]=model.predict(forecast[fs])
    sc=model.named_steps["standardscaler"]; lr=model.named_steps["linearregression"]
    model_meta[name]={
      "features":fs,
      "training_years":TRAIN_YEARS,
      "n_train":len(train),
      "scaler_mean":dict(zip(fs,map(float,sc.mean_))),
      "scaler_scale":dict(zip(fs,map(float,sc.scale_))),
      "standardized_intercept":float(lr.intercept_),
      "standardized_coefficients":dict(zip(fs,map(float,lr.coef_))),
      "raw_coefficients":dict(zip(fs,[float(c/s) for c,s in zip(lr.coef_,sc.scale_)])),
      "raw_intercept":float(lr.intercept_-np.sum(lr.coef_*sc.mean_/sc.scale_))
    }

pred_path=OUT/"predictions_2026.csv"; pred_out.sort_values("kommun_kod").to_csv(pred_path,index=False)
train_path=OUT/"training_matrix_2020_2025.csv"; train.sort_values(["year","kommun_kod"]).to_csv(train_path,index=False)
forecast_path=OUT/"predictor_matrix_2026.csv"; forecast.sort_values("kommun_kod").to_csv(forecast_path,index=False)

files=list(OUT.glob("*"))
manifest={
 "status":"preoutcome_2026_core4_temporal_predictions_frozen",
 "frozen_at_utc":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
 "production_changed":False,
 "forecast_year":FORECAST_YEAR,
 "training_years":TRAIN_YEARS,
 "municipalities":290,
 "baseline":"core4",
 "challenger":"core4_plus_trend3y",
 "trend_definition":"(inflow[t-1] - inflow[t-3]) / 2",
 "models":model_meta,
 "files_sha256":{p.name:sha(p) for p in files if p.name!="manifest.json"},
 "future_scoring_rules":{
   "use_frozen_predictions_only":True,
   "no_refit_before_score":True,
   "no_reselection":True,
   "no_temporal_redefinition":True,
   "primary_metric":"RMSE",
   "secondary_metrics":["MAE","bias","median_absolute_error","Lulea_absolute_error"],
   "promotion_rule":"challenger must beat baseline RMSE on untouched 2026 and show no material residual pathology; one year alone is supportive, not sufficient for automatic production promotion"
 }
}
dump("manifest.json",manifest)
print(json.dumps({
 "status":manifest["status"],
 "forecast_year":FORECAST_YEAR,
 "training_years":TRAIN_YEARS,
 "municipalities":290,
 "lulea":pred_out[pred_out.kommun_kod=="2580"].to_dict("records"),
 "prediction_summary":{
   c:{"mean":float(pred_out[c].mean()),"min":float(pred_out[c].min()),"max":float(pred_out[c].max())}
   for c in pred_out.columns if c.endswith("_per_1000")
 }
},ensure_ascii=False,indent=2))
