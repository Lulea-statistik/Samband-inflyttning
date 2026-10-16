#!/usr/bin/env python3
"""Score a future untouched outcome against frozen models and frozen predictor snapshot.

This script is intentionally non-adaptive:
- no refit
- no variable selection
- no alpha tuning
- no live source values
- no temporal adjustment

Usage:
  python scripts/score_three_year_forecast_untouched.py \
      --outcome-csv path/to/outcome.csv \
      --outcome-year YYYY

Required outcome columns:
  kommun_kod, inflyttning_per_1000
"""
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
SNAP=D/"source_snapshots"/"20261016T203726Z"
MODEL=D/"three_year_forecast_pre_outcome_frozen_models.json"
VERIFY=D/"forecast_core_snapshot_verification.json"

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--outcome-csv",required=True)
    p.add_argument("--outcome-year",required=True,type=int)
    p.add_argument("--output",default="docs/data/three_year_forecast_untouched_score.json")
    return p.parse_args()

def jsonstat_to_long(js):
    dims=js["id"]
    sizes=js["size"]
    vals=js["value"]
    cats=[]
    for d in dims:
        idx=js["dimension"][d]["category"]["index"]
        if isinstance(idx,dict):
            ordered=sorted(idx,key=idx.get)
        else:
            ordered=list(idx)
        cats.append(ordered)
    rows=[]
    for flat,v in enumerate(vals):
        if v is None:
            continue
        rem=flat
        pos=[]
        for sz in reversed(sizes):
            pos.append(rem%sz); rem//=sz
        pos=list(reversed(pos))
        r={d:cats[i][pos[i]] for i,d in enumerate(dims)}
        r["value"]=float(v)
        rows.append(r)
    return pd.DataFrame(rows)

def load_predictors(year):
    # lag1 means source year = forecast/outcome year - 1
    sy=year-1

    mig=json.loads((SNAP/"scb_migration_values.json").read_text(encoding="utf-8"))
    m=jsonstat_to_long(mig)
    m=m[m["Tid"].astype(str)==str(sy)].copy()
    m["Region"]=m["Region"].astype(str).str.zfill(4)
    # sum sexes; contents already separate
    mp=(m.groupby(["Region","ContentsCode"],as_index=False)["value"].sum()
          .pivot(index="Region",columns="ContentsCode",values="value").reset_index())
    mp=mp.rename(columns={"BE0101AU":"inflyttade","BE0101AV":"utflyttade"})

    pop=json.loads((SNAP/"scb_population_values.json").read_text(encoding="utf-8"))
    p=jsonstat_to_long(pop)
    p=p[p["Tid"].astype(str)==str(sy)].copy()
    p["Region"]=p["Region"].astype(str).str.zfill(4)
    # query includes all civil states and both sexes; sum to municipality total
    pp=p.groupby("Region",as_index=False)["value"].sum().rename(columns={"value":"folkmangd"})

    hou=json.loads((SNAP/"scb_housing_values.json").read_text(encoding="utf-8"))
    h=jsonstat_to_long(hou)
    h["Region"]=h["Region"].astype(str).str.zfill(4)
    hs=(h.groupby(["Region","Tid"],as_index=False)["value"].sum()
          .pivot(index="Region",columns="Tid",values="value").reset_index())
    prev=str(sy-1); cur=str(sy)
    if prev not in hs.columns or cur not in hs.columns:
        raise SystemExit(f"Housing snapshot lacks years {prev}/{cur}")
    hs["lag1_bostadsbestandsforandring_pct"]=100*(hs[cur]/hs[prev]-1)

    # Kolada source year sy
    kp=SNAP/f"kolada_N03937_{sy}.json"
    if not kp.exists():
        raise SystemExit(f"Snapshot lacks N03937 for source year {sy}")
    kj=json.loads(kp.read_text(encoding="utf-8"))
    rows=kj.get("values",kj.get("data",kj))
    if isinstance(rows,dict):
        rows=rows.get("values",[])
    out=[]
    for r in rows:
        rid=str(r.get("municipality",r.get("region",r.get("region_id","")))).zfill(4)
        val=r.get("value")
        if isinstance(val,list):
            # prefer total/non-gender value if present, else mean available numerics
            nums=[]
            for x in val:
                if isinstance(x,dict) and x.get("value") is not None:
                    nums.append(float(x["value"]))
            val=(sum(nums)/len(nums)) if nums else None
        if val is None:
            continue
        try: val=float(val)
        except: continue
        out.append((rid,val))
    k=pd.DataFrame(out,columns=["Region","lag1_kolada_arbetslosa_18_65_pct"]).drop_duplicates("Region")

    x=mp.merge(pp,on="Region",how="inner").merge(
        hs[["Region","lag1_bostadsbestandsforandring_pct"]],on="Region",how="inner"
    ).merge(k,on="Region",how="inner")
    x["lag1_inflyttning_per_1000"]=1000*x["inflyttade"]/x["folkmangd"]
    x["lag1_utflyttning_per_1000"]=1000*x["utflyttade"]/x["folkmangd"]
    return x.rename(columns={"Region":"kommun_kod"})

def predict_core4(x,model):
    c=model["core4"]
    pred=np.full(len(x),float(c["standardized_intercept"]))
    for f in c["features"]:
        z=(x[f].to_numpy(float)-float(c["scaler_mean"][f]))/float(c["scaler_scale"][f])
        pred += float(c["standardized_coefficients"][f])*z
    return pred

def predict_full_ridge(x,model):
    # Untouched scorer only supports full benchmark if every frozen full-Ridge feature
    # is present in the supplied predictor table. For the source-snapshot-only path,
    # this will normally be unavailable.
    f=model["full_ridge_benchmark"]["features"]
    missing=[c for c in f if c not in x.columns]
    if missing:
        return None,missing
    b=model["full_ridge_benchmark"]
    pred=np.full(len(x),float(b["intercept"]))
    for c in f:
        z=(x[c].to_numpy(float)-float(b["scaler_mean"][c]))/float(b["scaler_scale"][c])
        pred += float(b["coefficients"][c])*z
    return pred,[]

def metrics(y,p):
    e=p-y
    return {
      "rmse":float(np.sqrt(np.mean(e**2))),
      "mae":float(np.mean(np.abs(e))),
      "bias_mean_signed_error":float(np.mean(e)),
      "median_absolute_error":float(np.median(np.abs(e)))
    }

args=parse_args()
verify=json.loads(VERIFY.read_text(encoding="utf-8"))
assert verify["status"]=="forecast_core_snapshot_verified"
assert verify["snapshot"]=="20261016T203726Z"
model=json.loads(MODEL.read_text(encoding="utf-8"))
assert model["status"]=="pre_outcome_models_frozen"

outcome=pd.read_csv(args.outcome_csv,dtype={"kommun_kod":str})
outcome["kommun_kod"]=outcome["kommun_kod"].astype(str).str.zfill(4)
need={"kommun_kod","inflyttning_per_1000"}
if not need.issubset(outcome.columns):
    raise SystemExit(f"Outcome file must contain {sorted(need)}")

x=load_predictors(args.outcome_year)
df=x.merge(outcome[["kommun_kod","inflyttning_per_1000"]],on="kommun_kod",how="inner",validate="one_to_one")
if df.empty:
    raise SystemExit("No matched municipalities")

df["core4_prediction"]=predict_core4(df,model)
core_metrics=metrics(df["inflyttning_per_1000"].to_numpy(float),df["core4_prediction"].to_numpy(float))

bench_pred,missing=predict_full_ridge(df,model)
bench_metrics=None
if bench_pred is not None:
    df["full_ridge_prediction"]=bench_pred
    bench_metrics=metrics(df["inflyttning_per_1000"].to_numpy(float),bench_pred)

lulea=df[df["kommun_kod"]=="2580"]
lulea_res=None
if len(lulea)==1:
    lulea_res={
      "actual":float(lulea.iloc[0]["inflyttning_per_1000"]),
      "core4_prediction":float(lulea.iloc[0]["core4_prediction"]),
      "core4_residual_prediction_minus_actual":float(lulea.iloc[0]["core4_prediction"]-lulea.iloc[0]["inflyttning_per_1000"])
    }

result={
 "status":"untouched_temporal_score_recorded",
 "production_changed":False,
 "outcome_year":args.outcome_year,
 "source_snapshot":"20261016T203726Z",
 "frozen_model_file":str(MODEL),
 "rules":{
   "refit":False,"reselection":False,"retune":False,"live_source_values":False
 },
 "n_municipalities_scored":int(len(df)),
 "core4_ols":core_metrics,
 "full_ridge_benchmark":bench_metrics,
 "full_ridge_unavailable_missing_features":missing,
 "lulea":lulea_res,
 "residuals":[
   {
    "kommun_kod":r.kommun_kod,
    "actual":float(r.inflyttning_per_1000),
    "core4_prediction":float(r.core4_prediction),
    "core4_residual_prediction_minus_actual":float(r.core4_prediction-r.inflyttning_per_1000)
   } for r in df.itertuples(index=False)
 ],
 "interpretation_gate":{
   "production_promotion_not_automatic":True,
   "record_score_before_any_model_change":True
 }
}
Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k!="residuals"},ensure_ascii=False,indent=2))
