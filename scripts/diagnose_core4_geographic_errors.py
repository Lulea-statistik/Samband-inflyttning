#!/usr/bin/env python3
"""Diagnose geographic concentration of frozen core-4 forecast errors.

Research-only diagnostic. No model changes, no variable selection.

Uses six-year rolling-origin core-4 predictions, forecast years 2019-2024.
Examines whether absolute errors and signed bias concentrate by:
- county
- municipality population-size decile
- urbanisation decile
- regional-centre-distance decile
- lagged inflow level decile

Also reports which municipalities repeatedly appear in the worst error decile.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
PRED=D/"three_year_forecast_core4_historical_reconstructed_predictions.csv"
PANEL=D/"panel.csv"
OUT=D/"three_year_forecast_core4_geographic_error_diagnostic.json"
OUTCSV=D/"three_year_forecast_core4_geographic_error_rows.csv"

YEARS=list(range(2019,2025))
FEATURES=[
 "lag1_log_folkmangd",
 "lag1_tatortsgrad_pct",
 "lag1_regional_centre_distance_km",
 "lag1_inflyttning_per_1000"
]

p=pd.read_csv(PRED,dtype={"kommun_kod":str})
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
p=p[(p["window_years"].eq(6)) & (p["forecast_year"].isin(YEARS))].copy()
p=p.rename(columns={"forecast_year":"year"})
p["county"]=p["kommun_kod"].str[:2]
p["error"]=p["prediction"]-p["actual"]
p["abs_error"]=p["error"].abs()

panel=pd.read_csv(PANEL,dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)
missing=[c for c in FEATURES if c not in panel.columns]
if missing:
    raise SystemExit(f"Missing diagnostic features: {missing}")
x=panel[["kommun_kod","year"]+FEATURES].copy()
for c in FEATURES:
    x[c]=pd.to_numeric(x[c],errors="coerce")

# Distance is time-invariant; backfill from any available year for each municipality.
dist=(x.dropna(subset=["lag1_regional_centre_distance_km"])
        .groupby("kommun_kod")["lag1_regional_centre_distance_km"].median())
mask=x["lag1_regional_centre_distance_km"].isna()
x.loc[mask,"lag1_regional_centre_distance_km"]=x.loc[mask,"kommun_kod"].map(dist)

p=p.merge(x,on=["kommun_kod","year"],how="left",validate="one_to_one")
if len(p)!=290*len(YEARS):
    raise SystemExit(f"Unexpected row count: {len(p)}")
for c in FEATURES:
    if p[c].isna().any():
        raise SystemExit(f"Missing {c}: {int(p[c].isna().sum())}")

def metrics(g):
    e=g["error"].to_numpy()
    ae=np.abs(e)
    return {
      "n":int(len(g)),
      "rmse":float(np.sqrt(np.mean(e**2))),
      "mae":float(np.mean(ae)),
      "bias":float(np.mean(e)),
      "p90_abs_error":float(np.quantile(ae,.90)),
      "p95_abs_error":float(np.quantile(ae,.95)),
      "share_abs_error_gt_10":float(np.mean(ae>10))
    }

def grouped(df,col):
    return [
      {col:str(k),**metrics(g)}
      for k,g in df.groupby(col,dropna=False)
    ]

# Quantile bins are formed separately within each forecast year to avoid time-level composition effects.
bin_specs={
 "population_decile":"lag1_log_folkmangd",
 "urbanisation_decile":"lag1_tatortsgrad_pct",
 "distance_decile":"lag1_regional_centre_distance_km",
 "inflow_level_decile":"lag1_inflyttning_per_1000"
}
for new,col in bin_specs.items():
    vals=[]
    for y,g in p.groupby("year"):
        # rank(method=first) guarantees ten bins even under ties.
        bins=pd.qcut(g[col].rank(method="first"),10,labels=False)+1
        vals.extend(pd.Series(bins,index=g.index).items())
    s=pd.Series({i:int(v) for i,v in vals})
    p[new]=p.index.to_series().map(s)

# Worst-error decile separately per year.
p["worst_error_decile"]=False
for y,g in p.groupby("year"):
    threshold=float(g["abs_error"].quantile(.90))
    p.loc[g.index,"worst_error_decile"]=g["abs_error"]>=threshold

repeat=(p.groupby("kommun_kod").agg(
  years=("year","count"),
  worst_decile_years=("worst_error_decile","sum"),
  mean_error=("error","mean"),
  mean_abs_error=("abs_error","mean"),
  max_abs_error=("abs_error","max")
).reset_index())
repeat=repeat.sort_values(["worst_decile_years","mean_abs_error"],ascending=[False,False])

# Lulea context.
l=p[p["kommun_kod"].eq("2580")][
 ["year","actual","prediction","error","abs_error","county"]+list(bin_specs)
].to_dict("records")

result={
 "status":"core4_geographic_error_diagnostic",
 "production_changed":False,
 "structural_core4_changed":False,
 "variable_selection_reopened":False,
 "evaluation_years":YEARS,
 "n_rows":int(len(p)),
 "n_municipalities":int(p["kommun_kod"].nunique()),
 "overall":metrics(p),
 "by_county":grouped(p,"county"),
 "by_population_decile":grouped(p,"population_decile"),
 "by_urbanisation_decile":grouped(p,"urbanisation_decile"),
 "by_distance_decile":grouped(p,"distance_decile"),
 "by_inflow_level_decile":grouped(p,"inflow_level_decile"),
 "repeated_worst_error_municipalities":repeat.head(40).to_dict("records"),
 "lulea":l,
 "interpretation_rule":"Use this diagnostic to identify stable error concentration before defining any further geographic correction. Do not tune a correction on these same results without labeling it exploratory."
}
p.to_csv(OUTCSV,index=False)
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({
 "overall":result["overall"],
 "top_repeated":result["repeated_worst_error_municipalities"][:15],
 "lulea":l
},ensure_ascii=False,indent=2))
