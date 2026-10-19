#!/usr/bin/env python3
"""Rolling geographic residual adjustment of frozen core-4 historical forecasts.

Research-only. Structural core-4 is unchanged.

Primary question:
Does a strictly out-of-time geographic residual layer reduce geographic extremes?

Evaluation:
- Uses 6-year core-4 rolling-origin predictions for 2017-2024.
- Adjustment evaluation begins 2019 so each scored year has >=2 prior residual years.
- For forecast year y, the adjustment is trained only on residuals from years < y.
- Same 290 municipalities are evaluated each year.

Pre-specified adjustment arms:
1) core4: no adjustment.
2) geo3_ridge: Ridge residual model using fixed geographic controls:
   lag1_log_folkmangd, lag1_tatortsgrad_pct, lag1_regional_centre_distance_km.
   Fixed alpha=10. No tuning.
3) county_shrinkage: prior residual mean by county prefix, empirically shrunk toward 0:
   adjustment = -(n/(n+20))*mean(prediction-actual).
4) geo3_plus_county: Ridge residual model using geo3 plus one-hot county, fixed alpha=10.

Correction sign:
historical residual is prediction-actual, so adjusted prediction = core4_prediction - predicted_residual.

This does not alter the core-4 model or variable selection.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

D=Path("docs/data")
PRED=D/"three_year_forecast_core4_historical_reconstructed_predictions.csv"
PANEL=D/"panel.csv"
OUT=D/"three_year_forecast_core4_geographic_residual_adjustment.json"
OUTCSV=D/"three_year_forecast_core4_geographic_residual_adjustment_predictions.csv"

GEO=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"]
ALPHA=10.0
SHRINK_K=20.0
EVAL_YEARS=list(range(2019,2025))

pred=pd.read_csv(PRED,dtype={"kommun_kod":str})
pred["kommun_kod"]=pred["kommun_kod"].astype(str).str.zfill(4)
pred=pred[pred["window_years"].eq(6)].copy()
pred=pred.rename(columns={"forecast_year":"year"})
pred["county"]=pred["kommun_kod"].str[:2]

panel=pd.read_csv(PANEL,dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)
missing=[c for c in GEO if c not in panel.columns]
if missing:
    raise SystemExit(f"Missing geographic controls in panel: {missing}")
geo=panel[["kommun_kod","year"]+GEO].copy()
for c in GEO:
    geo[c]=pd.to_numeric(geo[c],errors="coerce")

# Regional-centre distance is a time-invariant geographic attribute.
# Historical panel vintages have gaps for some years, so recover one fixed
# municipality value from any available panel year and use it across years.
dist_static=(geo.dropna(subset=["lag1_regional_centre_distance_km"])
               .groupby("kommun_kod")["lag1_regional_centre_distance_km"]
               .median())
geo["lag1_regional_centre_distance_km"]=geo.apply(
    lambda r: dist_static.get(r["kommun_kod"],r["lag1_regional_centre_distance_km"])
    if pd.isna(r["lag1_regional_centre_distance_km"]) else r["lag1_regional_centre_distance_km"],
    axis=1
)

pred=pred.merge(geo,on=["kommun_kod","year"],how="left",validate="one_to_one")

if pred.groupby("year")["kommun_kod"].nunique().min()!=290:
    raise SystemExit("Historical six-year prediction panel is not complete 290 municipalities/year")
for c in GEO:
    if pred.loc[pred["year"].isin(range(2017,2025)),c].isna().any():
        miss=int(pred.loc[pred["year"].isin(range(2017,2025)),c].isna().sum())
        raise SystemExit(f"Missing geographic control {c} in 2017-2024 prediction panel: {miss} rows")

def met(actual,forecast):
    e=np.asarray(forecast)-np.asarray(actual)
    ae=np.abs(e)
    return {
      "n":int(len(e)),
      "rmse":float(np.sqrt(np.mean(e**2))),
      "mae":float(np.mean(ae)),
      "bias_prediction_minus_actual":float(np.mean(e)),
      "median_absolute_error":float(np.median(ae)),
      "p90_absolute_error":float(np.quantile(ae,.90)),
      "p95_absolute_error":float(np.quantile(ae,.95)),
      "max_absolute_error":float(np.max(ae)),
      "share_abs_error_gt_10":float(np.mean(ae>10))
    }

rows=[]
year_details=[]
for y in EVAL_YEARS:
    tr=pred[pred["year"]<y].copy()
    te=pred[pred["year"].eq(y)].copy()
    if tr["year"].nunique()<2:
        raise SystemExit(f"Need >=2 prior years before scoring {y}")

    # Arm 2: continuous geographic residual ridge.
    m_geo=make_pipeline(StandardScaler(),Ridge(alpha=ALPHA))
    m_geo.fit(tr[GEO],tr["residual_prediction_minus_actual"])
    geo_res=m_geo.predict(te[GEO])

    # Arm 3: county residual shrinkage.
    cs=(tr.groupby("county")["residual_prediction_minus_actual"]
          .agg(["mean","count"]).reset_index())
    cs["shrunk_residual"]=cs["mean"]*(cs["count"]/(cs["count"]+SHRINK_K))
    cmap=dict(zip(cs["county"],cs["shrunk_residual"]))
    county_res=te["county"].map(cmap).fillna(0.0).to_numpy()

    # Arm 4: continuous geography plus county effects.
    pre=ColumnTransformer([
      ("geo",StandardScaler(),GEO),
      ("county",OneHotEncoder(handle_unknown="ignore"),["county"])
    ])
    m_both=make_pipeline(pre,Ridge(alpha=ALPHA))
    m_both.fit(tr[GEO+["county"]],tr["residual_prediction_minus_actual"])
    both_res=m_both.predict(te[GEO+["county"]])

    te["core4"]=te["prediction"]
    te["geo3_ridge"]=te["prediction"]-geo_res
    te["county_shrinkage"]=te["prediction"]-county_res
    te["geo3_plus_county"]=te["prediction"]-both_res

    for _,r in te.iterrows():
        rows.append({
          "year":int(y),"kommun_kod":r["kommun_kod"],"county":r["county"],
          "actual":float(r["actual"]),
          "core4":float(r["core4"]),
          "geo3_ridge":float(r["geo3_ridge"]),
          "county_shrinkage":float(r["county_shrinkage"]),
          "geo3_plus_county":float(r["geo3_plus_county"])
        })
    yd={"year":y,"training_residual_years":sorted(map(int,tr["year"].unique())),"models":{}}
    for name in ["core4","geo3_ridge","county_shrinkage","geo3_plus_county"]:
        yd["models"][name]=met(te["actual"],te[name])
    year_details.append(yd)

o=pd.DataFrame(rows)
o.to_csv(OUTCSV,index=False)

summary={name:met(o["actual"],o[name]) for name in ["core4","geo3_ridge","county_shrinkage","geo3_plus_county"]}
base=summary["core4"]
for name in ["geo3_ridge","county_shrinkage","geo3_plus_county"]:
    summary[name]["rmse_change_vs_core4_pct"]=100*(summary[name]["rmse"]/base["rmse"]-1)
    summary[name]["p95_abs_error_change_vs_core4_pct"]=100*(summary[name]["p95_absolute_error"]/base["p95_absolute_error"]-1)
    summary[name]["max_abs_error_change_vs_core4_pct"]=100*(summary[name]["max_absolute_error"]/base["max_absolute_error"]-1)

# Persistent geographic diagnostics on core4 residuals.
o["core4_residual"]=o["core4"]-o["actual"]
county=(o.groupby("county").agg(
    n=("core4_residual","size"),
    mean_residual=("core4_residual","mean"),
    mae=("core4_residual",lambda x:float(np.mean(np.abs(x)))),
    p95_abs_error=("core4_residual",lambda x:float(np.quantile(np.abs(x),.95)))
).reset_index())
county_extremes=county.reindex(county["mean_residual"].abs().sort_values(ascending=False).index).head(10).to_dict("records")

l=o[o["kommun_kod"].eq("2580")].copy()
lulea=[]
for _,r in l.iterrows():
    rec={"year":int(r["year"]),"actual":float(r["actual"])}
    for name in ["core4","geo3_ridge","county_shrinkage","geo3_plus_county"]:
        rec[name]=float(r[name]); rec[name+"_error"]=float(r[name]-r["actual"])
    lulea.append(rec)

result={
 "status":"core4_geographic_residual_adjustment_research",
 "production_changed":False,
 "structural_core4_changed":False,
 "variable_selection_reopened":False,
 "evaluation_years":EVAL_YEARS,
 "n_municipalities":290,
 "design":{
   "base_predictions":"6-year rolling-origin core4",
   "out_of_time_rule":"each forecast year adjustment trained only on earlier forecast residual years",
   "geo3_features":GEO,
   "ridge_alpha_fixed":ALPHA,
   "county_definition":"first two digits of municipality code",
   "county_shrinkage_k":SHRINK_K
 },
 "summary":summary,
 "year_details":year_details,
 "county_core4_extremes":county_extremes,
 "lulea":lulea,
 "decision_rule":"A geographic layer is only promising if it improves overall RMSE while also reducing p95/max absolute error; no production promotion from this retrospective test."
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({
 "status":result["status"],
 "summary":summary,
 "lulea":lulea,
 "county_core4_extremes":county_extremes
},ensure_ascii=False,indent=2))
