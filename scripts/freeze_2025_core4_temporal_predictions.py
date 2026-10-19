#!/usr/bin/env python3
"""Freeze prospective 2025 core-4 and core-4+3y-trend predictions.

This is the earliest currently valid prospective untouched temporal test because
the verified source snapshot contains migration/population through 2024.

Protocol:
- training target years 2019-2024 (fixed 6-year window)
- forecast target year 2025
- baseline: core-4, StandardScaler + OLS
- challenger: core-4 + pre-registered 3-year inflow trend
- exact frozen source snapshot 20261016T203726Z for predictor reconstruction
- no refit/reselection/redefinition after 2025 outcome inspection
"""
import hashlib, json, re
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression

D=Path("docs/data")
SNAP=D/"source_snapshots"/"20261016T203726Z"
OUT=D/"preoutcome_2025_core4_temporal"
OUT.mkdir(parents=True,exist_ok=True)

FEATURES=[
 "lag1_inflyttning_per_1000",
 "lag1_utflyttning_per_1000",
 "lag1_kolada_arbetslosa_18_65_pct",
 "lag1_bostadsbestandsforandring_pct"
]
TARGET="inflyttning_per_1000"
TRAIN_YEARS=list(range(2019,2025))
FORECAST_YEAR=2025

def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

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
        row["value"]=float(v)
        out.append(row)
    return pd.DataFrame(out)

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

manifest=load_json(SNAP/"manifest.json")
if manifest.get("captured_at_utc")!="20261016T203726Z":
    raise SystemExit("Unexpected source snapshot")
if "2024" not in manifest["sources"]["migration"]["years"]:
    raise SystemExit("2024 migration missing from frozen snapshot")
if "2024" not in manifest["sources"]["population"]["years"]:
    raise SystemExit("2024 population missing from frozen snapshot")
if "2025" not in manifest["sources"]["housing"]["years"]:
    raise SystemExit("2025 housing missing from frozen snapshot")

mig=js2long(load_json(SNAP/"scb_migration_values.json"))
pop=js2long(load_json(SNAP/"scb_population_values.json"))
housing=js2long(load_json(SNAP/"scb_housing_values.json"))

for df in (mig,pop,housing):
    df["Region"]=df["Region"].astype(str).str.zfill(4)
    df["Tid"]=df["Tid"].astype(int)

# Migration snapshot query is explicitly total age, sex 1/2, contents AU/AV.
magg=(mig.groupby(["Region","Tid","ContentsCode"],as_index=False)["value"].sum()
      .pivot(index=["Region","Tid"],columns="ContentsCode",values="value").reset_index())
if "BE0101AU" not in magg.columns or "BE0101AV" not in magg.columns:
    raise SystemExit("Frozen migration contents missing")

# Population snapshot query is total age, all civil states, sex 1/2.
pagg=(pop.groupby(["Region","Tid"],as_index=False)["value"].sum()
      .rename(columns={"value":"population"}))

mp=magg.merge(pagg,on=["Region","Tid"],how="inner")
mp["inflyttning_per_1000"]=1000*mp["BE0101AU"]/mp["population"]
mp["utflyttning_per_1000"]=1000*mp["BE0101AV"]/mp["population"]
mp=mp.rename(columns={"Region":"kommun_kod","Tid":"year"})

# Housing totals and annual change from immutable snapshot.
ht=(housing.groupby(["Region","Tid"],as_index=False)["value"].sum()
    .rename(columns={"Region":"kommun_kod","Tid":"source_year","value":"bostader_totalt"}))
ht=ht.sort_values(["kommun_kod","source_year"])
ht["housing_change_pct"]=100*ht.groupby("kommun_kod")["bostader_totalt"].pct_change(fill_method=None)

# Kolada totals T from snapshot.
kol_rows=[]
for y in range(2019,2026):
    p=SNAP/f"kolada_N03937_{y}.json"
    if not p.exists(): continue
    js=load_json(p)
    for rec in js.get("values",[]):
        code=str(rec.get("municipality","")).zfill(4)
        if not re.fullmatch(r"\d{4}",code): continue
        total=next((x.get("value") for x in rec.get("values",[])
                    if x.get("gender")=="T" and x.get("value") is not None),None)
        if total is not None:
            kol_rows.append({"kommun_kod":code,"source_year":y,"n03937":float(total)})
kol=pd.DataFrame(kol_rows)

# Build training rows 2019-2024 from the already frozen/reconstructed historical panel logic.
# The earliest 2019 training row needs 2018 predictor values, which predate the immutable
# 2019-start source snapshot. We therefore freeze those historical training values now,
# while the 2025 forecast predictors remain strictly snapshot-derived from source year 2024.

# Current reconstructed history for the 2019 training boundary only.
import requests
s=requests.Session()
s.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-2025-training-boundary/1.0"})

# N03937 source year 2018 for target 2019.
r=s.get("https://api.kolada.se/v3/data/kpi/N03937/year/2018",
        params={"region_type":"municipality","per_page":5000},timeout=90)
r.raise_for_status()
kol18=[]
for rec in r.json().get("values",[]):
    code=str(rec.get("municipality","")).zfill(4)
    if not re.fullmatch(r"\d{4}",code): continue
    total=next((x.get("value") for x in rec.get("values",[])
                if x.get("gender")=="T" and x.get("value") is not None),None)
    if total is not None:
        kol18.append({"kommun_kod":code,"n03937_2018":float(total)})
kol18=pd.DataFrame(kol18)

# Housing 2017-2018 to derive 2018 stock change for target 2019.
h_url="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T04"
hmeta=s.get(h_url,timeout=90); hmeta.raise_for_status(); hmeta=hmeta.json()
hv={v["code"]:v for v in hmeta["variables"]}
regions18=[x for x in hv["Region"]["values"] if re.fullmatch(r"\d{4}",str(x))]
parts18=[]
for yy in ["2017","2018"]:
    q={"query":[
      {"code":"Region","selection":{"filter":"item","values":regions18}},
      {"code":"Hustyp","selection":{"filter":"item","values":hv["Hustyp"]["values"]}},
      {"code":"Upplatelseform","selection":{"filter":"item","values":hv["Upplatelseform"]["values"]}},
      {"code":"ContentsCode","selection":{"filter":"item","values":["BO0104AH"]}},
      {"code":"Tid","selection":{"filter":"item","values":[yy]}}
    ],"response":{"format":"json-stat2"}}
    rr=s.post(h_url,json=q,timeout=120)
    if rr.status_code==403:
        for batch in [regions18[:145],regions18[145:]]:
            q2=json.loads(json.dumps(q)); q2["query"][0]["selection"]["values"]=batch
            r2=s.post(h_url,json=q2,timeout=120); r2.raise_for_status()
            parts18.append(js2long(r2.json()))
    else:
        rr.raise_for_status(); parts18.append(js2long(rr.json()))
if not parts18 or all(p.empty for p in parts18):
    raise SystemExit(f"2017-2018 housing reconstruction empty: region_count={len(regions18)}")
hh=pd.concat(parts18,ignore_index=True)
hh["Region"]=hh["Region"].astype(str).str.zfill(4); hh["Tid"]=hh["Tid"].astype(int)
hh=(hh.groupby(["Region","Tid"],as_index=False)["value"].sum()
    .rename(columns={"Region":"kommun_kod","Tid":"source_year","value":"bostader_totalt"}))
hh=hh.sort_values(["kommun_kod","source_year"])
hh["housing_change_pct"]=100*hh.groupby("kommun_kod")["bostader_totalt"].pct_change(fill_method=None)
h18=hh[hh.source_year==2018][["kommun_kod","housing_change_pct"]]
hstock18=hh[hh.source_year==2018][["kommun_kod","bostader_totalt"]].rename(
    columns={"bostader_totalt":"bostader_2018"})

# Bridge the immutable housing snapshot boundary:
# snapshot starts in 2019, so its internal pct_change cannot derive the 2019 change.
# Combine the reconstructed 2018 stock with frozen snapshot 2019 stock.
hstock19=ht[ht.source_year==2019][["kommun_kod","bostader_totalt"]].rename(
    columns={"bostader_totalt":"bostader_2019"})
h19_bridge=hstock18.merge(hstock19,on="kommun_kod",how="inner")
h19_bridge["housing_change_2019_pct"]=100*(
    h19_bridge["bostader_2019"]/h19_bridge["bostader_2018"]-1.0)
h19_map=dict(zip(h19_bridge["kommun_kod"],h19_bridge["housing_change_2019_pct"]))
mask19=ht["source_year"].eq(2019)
ht.loc[mask19,"housing_change_pct"]=ht.loc[mask19,"kommun_kod"].map(h19_map)

# Historical migration predictors and target outcomes for 2019-2024 from the existing panel.
panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)
hist=panel[panel.year.isin(TRAIN_YEARS)][[
  "kommun_kod","year",TARGET,
  "lag1_inflyttning_per_1000","lag1_utflyttning_per_1000"
]].copy()

# For 2020-2024, use frozen snapshot-derived N03937/housing lag values.
rows=[]
for y in TRAIN_YEARS:
    base=hist[hist.year==y].copy()
    if y==2019:
        q=(base.merge(kol18,on="kommun_kod",how="inner")
               .merge(h18,on="kommun_kod",how="inner")
               .rename(columns={
                 "n03937_2018":"lag1_kolada_arbetslosa_18_65_pct",
                 "housing_change_pct":"lag1_bostadsbestandsforandring_pct"}))
    else:
        ky=(kol[kol.source_year==y-1][["kommun_kod","n03937"]]
            .rename(columns={"n03937":"lag1_kolada_arbetslosa_18_65_pct"}))
        hy=(ht[ht.source_year==y-1][["kommun_kod","housing_change_pct"]]
            .rename(columns={"housing_change_pct":"lag1_bostadsbestandsforandring_pct"}))
        q=base.merge(ky,on="kommun_kod",how="inner").merge(hy,on="kommun_kod",how="inner")
    rows.append(q)
train_base=pd.concat(rows,ignore_index=True)

# 2025 forecast row: strictly predictor source year 2024 from immutable snapshot.
prev=mp[mp.year==2024][["kommun_kod","inflyttning_per_1000","utflyttning_per_1000"]].copy()
prev=prev.rename(columns={
  "inflyttning_per_1000":"lag1_inflyttning_per_1000",
  "utflyttning_per_1000":"lag1_utflyttning_per_1000"})
ky=(kol[kol.source_year==2024][["kommun_kod","n03937"]]
    .rename(columns={"n03937":"lag1_kolada_arbetslosa_18_65_pct"}))
hy=(ht[ht.source_year==2024][["kommun_kod","housing_change_pct"]]
    .rename(columns={"housing_change_pct":"lag1_bostadsbestandsforandring_pct"}))
forecast_base=(prev.merge(ky,on="kommun_kod",how="inner")
                   .merge(hy,on="kommun_kod",how="inner"))
forecast_base["year"]=2025

x=pd.concat([train_base,forecast_base],ignore_index=True,sort=False)

# Pre-outcome 3-year slope: (inflow[t-1]-inflow[t-3])/2.
# Use the existing observed inflow history, which is already known before the 2025 score.
inflow_hist=panel[["kommun_kod","year",TARGET]].copy().rename(columns={TARGET:"inflow"})
for lag in (1,3):
    z=inflow_hist.copy()
    z["year"]=z["year"]+lag
    z=z.rename(columns={"inflow":f"lag{lag}_trend_inflow"})
    x=x.merge(z,on=["kommun_kod","year"],how="left")
x["trend_3y_slope"]=(x["lag1_trend_inflow"]-x["lag3_trend_inflow"])/2.0

need=FEATURES+["trend_3y_slope"]

# Coverage diagnostics: make future failures identify the exact year/field.
coverage={}
for y in TRAIN_YEARS+[FORECAST_YEAR]:
    q=x[x.year==y].copy()
    fields=([TARGET]+need) if y in TRAIN_YEARS else need
    coverage[str(y)]={
      "rows_before_complete_filter":int(len(q)),
      "unique_municipalities":int(q["kommun_kod"].nunique()) if len(q) else 0,
      "non_null_by_field":{col:int(q[col].notna().sum()) for col in fields},
      "complete_rows":int(q.dropna(subset=fields).shape[0])
    }
print(json.dumps({"coverage_before_common_intersection":coverage},ensure_ascii=False,indent=2))

train=x[x.year.isin(TRAIN_YEARS)].dropna(subset=[TARGET]+need).copy()
forecast=x[x.year==FORECAST_YEAR].dropna(subset=need).copy()

sets=[set(forecast.kommun_kod)]
for y in TRAIN_YEARS:
    sets.append(set(train[train.year==y].kommun_kod))
common=set.intersection(*sets)
train=train[train.kommun_kod.isin(common)].copy()
forecast=forecast[forecast.kommun_kod.isin(common)].copy()

if len(common)!=290 or len(train)!=290*6 or len(forecast)!=290:
    raise SystemExit(f"Incomplete freeze: common={len(common)}, train={len(train)}, forecast={len(forecast)}")

models={
 "core4":FEATURES,
 "core4_plus_trend3y":FEATURES+["trend_3y_slope"]
}
pred=forecast[["kommun_kod","year"]].copy()
model_meta={}
for name,fs in models.items():
    model=make_pipeline(StandardScaler(),LinearRegression()).fit(train[fs],train[TARGET])
    pred[name+"_prediction_per_1000"]=model.predict(forecast[fs])
    sc=model.named_steps["standardscaler"]; lr=model.named_steps["linearregression"]
    model_meta[name]={
      "features":fs,
      "training_years":TRAIN_YEARS,
      "n_train":int(len(train)),
      "scaler_mean":dict(zip(fs,map(float,sc.mean_))),
      "scaler_scale":dict(zip(fs,map(float,sc.scale_))),
      "standardized_intercept":float(lr.intercept_),
      "standardized_coefficients":dict(zip(fs,map(float,lr.coef_))),
      "raw_coefficients":dict(zip(fs,[float(c/s) for c,s in zip(lr.coef_,sc.scale_)])),
      "raw_intercept":float(lr.intercept_-np.sum(lr.coef_*sc.mean_/sc.scale_))
    }

train_path=OUT/"training_matrix_2019_2024.csv"
forecast_path=OUT/"predictor_matrix_2025.csv"
pred_path=OUT/"predictions_2025.csv"
train.sort_values(["year","kommun_kod"]).to_csv(train_path,index=False)
forecast.sort_values("kommun_kod").to_csv(forecast_path,index=False)
pred.sort_values("kommun_kod").to_csv(pred_path,index=False)

freeze={
 "status":"preoutcome_2025_core4_temporal_predictions_frozen",
 "production_changed":False,
 "source_snapshot":"20261016T203726Z",
 "training_boundary_note":"2019 training row requires 2018 N03937/housing values, reconstructed and frozen at this commit; 2020-2024 training structural predictors and all 2025 forecast predictors use the immutable snapshot where available.",
 "forecast_year":2025,
 "training_years":TRAIN_YEARS,
 "municipalities":290,
 "baseline":"core4",
 "challenger":"core4_plus_trend3y",
 "trend_definition":"(inflow[t-1] - inflow[t-3]) / 2",
 "models":model_meta,
 "files_sha256":{
   train_path.name:sha(train_path),
   forecast_path.name:sha(forecast_path),
   pred_path.name:sha(pred_path)
 },
 "future_scoring_rules":{
   "use_frozen_predictions_only":True,
   "no_refit_before_score":True,
   "no_reselection":True,
   "no_temporal_redefinition":True,
   "primary_metric":"RMSE",
   "secondary_metrics":["MAE","bias","median_absolute_error","Lulea_absolute_error"],
   "promotion_rule":"challenger must beat baseline RMSE on untouched 2025 and show no material residual pathology; one future year is supportive, not sufficient for automatic production promotion"
 }
}
(OUT/"manifest.json").write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

print(json.dumps({
 "status":freeze["status"],
 "forecast_year":2025,
 "training_years":TRAIN_YEARS,
 "municipalities":290,
 "lulea":pred[pred.kommun_kod=="2580"].to_dict("records"),
 "prediction_summary":{
   c:{"mean":float(pred[c].mean()),"min":float(pred[c].min()),"max":float(pred[c].max())}
   for c in pred.columns if c.endswith("_per_1000")
 }
},ensure_ascii=False,indent=2))
