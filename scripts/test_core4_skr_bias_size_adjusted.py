#!/usr/bin/env python3
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

D=Path("docs/data")
IN=D/"three_year_forecast_core4_demographic_skr_north_bias_rows.csv"
OUT=D/"three_year_forecast_core4_skr_bias_size_adjusted.json"

df=pd.read_csv(IN,dtype={"kommun_kod":str})
df["kommun_kod"]=df["kommun_kod"].astype(str).str.zfill(4)
if "residual" not in df.columns:
    df["residual"]=df["prediction"]-df["actual"]
df["population"]=np.exp(pd.to_numeric(df["lag1_log_folkmangd"],errors="coerce"))

df["population_decile"]=0
for y,g in df.groupby("year"):
    bins=pd.qcut(g["population"].rank(method="first"),10,labels=False)+1
    df.loc[g.index,"population_decile"]=bins.astype(int)

cells=[]
for (dec,grp),g in df.groupby(["population_decile","skr_group"]):
    if len(g)<3: continue
    cells.append({
      "population_decile":int(dec),"skr_group":grp,"n":int(len(g)),
      "municipalities":int(g["kommun_kod"].nunique()),
      "mean_residual":float(g["residual"].mean()),
      "mae":float(g["residual"].abs().mean())
    })
cells_df=pd.DataFrame(cells)

adj_groups=[]
for grp,g in cells_df.groupby("skr_group"):
    adj_groups.append({
      "skr_group":grp,
      "n_deciles":int(g["population_decile"].nunique()),
      "equal_weight_mean_residual_across_population_deciles":float(g["mean_residual"].mean()),
      "weighted_mean_residual":float(np.average(g["mean_residual"],weights=g["n"])),
      "mean_mae_across_population_deciles":float(g["mae"].mean())
    })

num_features=[
 "lag1_log_folkmangd","lag1_andel_20_34","lag1_inflyttare_medelalder",
 "lag1_andel_studerande","lag1_andel_eftergymnasial",
 "lag1_befolkningstillvaxt_pct","northing_sweref99tm"
]
for c in num_features:
    df[c]=pd.to_numeric(df[c],errors="coerce")
if df[num_features+["skr_group","residual"]].isna().any().any():
    raise SystemExit("Missing values in adjusted SKR diagnostic")

y=df["residual"].to_numpy()
base=Pipeline([
 ("prep",ColumnTransformer([("num",StandardScaler(),num_features)])),
 ("reg",LinearRegression())
])
base.fit(df,y)
r2_base=float(base.score(df,y))

full=Pipeline([
 ("prep",ColumnTransformer([
   ("num",StandardScaler(),num_features),
   ("skr",OneHotEncoder(drop="first",handle_unknown="ignore",sparse_output=False),["skr_group"])
 ])),
 ("reg",LinearRegression())
])
full.fit(df,y)
r2_full=float(full.score(df,y))

base_pred=base.predict(df)
df["residual_after_size_demo_north"]=df["residual"]-base_pred
adjusted=[]
for grp,g in df.groupby("skr_group"):
    adjusted.append({
      "skr_group":grp,"n":int(len(g)),
      "municipalities":int(g["kommun_kod"].nunique()),
      "mean_raw_residual":float(g["residual"].mean()),
      "mean_residual_after_size_demo_north":float(g["residual_after_size_demo_north"].mean()),
      "mae_after_size_demo_north":float(g["residual_after_size_demo_north"].abs().mean())
    })

prep=full.named_steps["prep"]
coef_map=dict(zip(prep.get_feature_names_out(),map(float,full.named_steps["reg"].coef_)))
skr_coefs={k.split("skr__skr_group_",1)[1]:v for k,v in coef_map.items() if k.startswith("skr__skr_group_")}

lgrp=df.loc[df["kommun_kod"].eq("2580"),"skr_group"].iloc[0]
result={
 "status":"core4_skr_bias_size_adjusted_diagnostic",
 "production_changed":False,
 "structural_core4_changed":False,
 "variable_selection_reopened":False,
 "within_population_decile_cells":cells,
 "skr_equal_weight_across_population_deciles":sorted(adj_groups,key=lambda x:x["skr_group"]),
 "regression_control":{
   "base_features":num_features,
   "base_r2":r2_base,
   "base_plus_skr_r2":r2_full,
   "incremental_r2_from_skr":r2_full-r2_base,
   "skr_coefficients_vs_reference_A1":skr_coefs,
   "note":"Diagnostic only; not a forecast correction."
 },
 "skr_adjusted_residual_means":sorted(adjusted,key=lambda x:x["skr_group"]),
 "lulea":{"skr_group":lgrp,"group_adjusted_context":next(x for x in adjusted if x["skr_group"]==lgrp)},
 "interpretation_guardrail":"Persistent C7/C8 positive residual after adjustment means bias is not explained only by small population; this does not prove causality."
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({
 "equal_weight":result["skr_equal_weight_across_population_deciles"],
 "adjusted":result["skr_adjusted_residual_means"],
 "regression":result["regression_control"],
 "lulea":result["lulea"]
},ensure_ascii=False,indent=2))
