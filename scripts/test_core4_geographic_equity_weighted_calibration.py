#!/usr/bin/env python3
"""Geographic-equity weighted calibration of frozen core-4 predictions.

Research-only challenger:
- frozen 6-year rolling-origin core-4 predictions are inputs;
- for each forecast year, only earlier forecast years are used;
- municipality difficulty is measured from prior absolute forecast errors;
- difficult municipalities receive more weight when fitting actual ~ core4_prediction;
- structural feature set and core-4 refit remain untouched.

Goal: reduce cross-municipality tail error while keeping pooled RMSE nearly unchanged.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

D=Path("docs/data")
P=D/"three_year_forecast_core4_historical_reconstructed_predictions.csv"
OUT=D/"core4_geographic_equity_weighted_calibration.json"
OUTCSV=D/"core4_geographic_equity_weighted_calibration_predictions.csv"

WINDOW=6
EVAL_YEARS=list(range(2020,2025))
LAMBDAS=[0.0,0.25,0.5,0.75,1.0,1.5,2.0]
CAP=3.0

p=pd.read_csv(P,dtype={"kommun_kod":str})
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
p=p[p["window_years"].eq(WINDOW)].copy().rename(columns={"forecast_year":"year"})
if p.groupby("year")["kommun_kod"].nunique().min()!=290:
    raise SystemExit("Incomplete six-year rolling-origin prediction panel")

def metrics(df,pred_col):
    e=(df[pred_col]-df["actual"]).to_numpy(float)
    pooled_rmse=float(np.sqrt(np.mean(e*e)))
    pooled_mae=float(np.mean(np.abs(e)))
    by=df.assign(_e=e).groupby("kommun_kod")["_e"].apply(
        lambda x: float(np.sqrt(np.mean(np.square(x.to_numpy(float))))))
    vals=by.to_numpy(float)
    return {
      "n":int(len(df)),
      "pooled_rmse":pooled_rmse,
      "pooled_mae":pooled_mae,
      "mean_municipality_rmse":float(np.mean(vals)),
      "median_municipality_rmse":float(np.quantile(vals,.5)),
      "sd_municipality_rmse":float(np.std(vals,ddof=1)),
      "p90_municipality_rmse":float(np.quantile(vals,.9)),
      "p95_municipality_rmse":float(np.quantile(vals,.95)),
      "worst_decile_mean_rmse":float(np.mean(np.sort(vals)[-29:])),
      "max_municipality_rmse":float(np.max(vals)),
      "share_municipalities_rmse_gt_10":float(np.mean(vals>10))
    }

rows=[]
selection=[]
for y in EVAL_YEARS:
    hist=p[p["year"]<y].copy()
    te=p[p["year"].eq(y)].copy()
    if hist["year"].nunique()<3:
        raise SystemExit(f"Insufficient prior forecast years before {y}")

    hist["abs_error"]=(hist["prediction"]-hist["actual"]).abs()
    difficulty=hist.groupby("kommun_kod")["abs_error"].mean()
    med=float(difficulty.median())
    rel=(difficulty/med).clip(lower=0.5,upper=CAP)

    scored=[]
    for lam in LAMBDAS:
        weights={k:max(0.25,min(CAP,1.0+lam*(float(v)-1.0))) for k,v in rel.items()}
        w=np.asarray([weights[k] for k in hist["kommun_kod"]],dtype=float)
        lr=LinearRegression().fit(
            hist[["prediction"]].to_numpy(float),
            hist["actual"].to_numpy(float),
            sample_weight=w
        )
        hist_pred=lr.predict(hist[["prediction"]].to_numpy(float))
        h=hist.copy()
        h["calibrated"]=hist_pred
        m=metrics(h,"calibrated")
        scored.append((lam,lr,m,weights))

    # Selection objective targets tail while preserving pooled accuracy:
    # among candidates within +1% pooled RMSE of the best historical candidate,
    # choose lowest p90 municipality RMSE; tie-break on pooled RMSE then lambda.
    best_pooled=min(x[2]["pooled_rmse"] for x in scored)
    feasible=[x for x in scored if x[2]["pooled_rmse"]<=best_pooled*1.01]
    feasible.sort(key=lambda x:(x[2]["p90_municipality_rmse"],x[2]["pooled_rmse"],x[0]))
    lam,lr,hm,weights=feasible[0]

    pred=lr.predict(te[["prediction"]].to_numpy(float))
    for (_,r),pr in zip(te.iterrows(),pred):
        rows.append({
          "year":int(y),
          "kommun_kod":r["kommun_kod"],
          "actual":float(r["actual"]),
          "core4":float(r["prediction"]),
          "challenger":float(pr),
          "selected_lambda":float(lam),
          "calibration_intercept":float(lr.intercept_),
          "calibration_slope":float(lr.coef_[0]),
          "municipality_weight":float(weights[r["kommun_kod"]])
        })
    selection.append({
      "year":int(y),
      "selected_lambda":float(lam),
      "historical_best_pooled_rmse":float(best_pooled),
      "historical_selected_pooled_rmse":hm["pooled_rmse"],
      "historical_selected_p90_municipality_rmse":hm["p90_municipality_rmse"],
      "calibration_intercept":float(lr.intercept_),
      "calibration_slope":float(lr.coef_[0])
    })

o=pd.DataFrame(rows)
o.to_csv(OUTCSV,index=False)

base=o.rename(columns={"core4":"pred"})
chal=o.rename(columns={"challenger":"pred"})
bm=metrics(base,"pred")
cm=metrics(chal,"pred")
delta={
 "pooled_rmse":100*(cm["pooled_rmse"]/bm["pooled_rmse"]-1),
 "p90_municipality_rmse":100*(cm["p90_municipality_rmse"]/bm["p90_municipality_rmse"]-1),
 "worst_decile_mean_rmse":100*(cm["worst_decile_mean_rmse"]/bm["worst_decile_mean_rmse"]-1),
 "sd_municipality_rmse":100*(cm["sd_municipality_rmse"]/bm["sd_municipality_rmse"]-1)
}
promising=bool(
    delta["p90_municipality_rmse"]<0
    and delta["worst_decile_mean_rmse"]<0
    and delta["pooled_rmse"]<=1.0
)

res={
 "status":"core4_geographic_equity_weighted_calibration",
 "production_changed":False,
 "structural_core4_changed":False,
 "variable_selection_reopened":False,
 "evaluation_years":EVAL_YEARS,
 "n_municipalities":290,
 "base_predictions":"frozen 6-year rolling-origin core4",
 "method":{
   "calibration":"weighted linear regression actual ~ frozen core4 prediction",
   "difficulty":"municipality mean absolute forecast error over prior forecast years only",
   "weight_formula":"1 + lambda * (relative_difficulty - 1)",
   "lambda_grid":LAMBDAS,
   "weight_cap":CAP,
   "selection":"within 1% of best historical pooled RMSE, minimize historical p90 municipality RMSE",
   "out_of_time_rule":"forecast-year outcome never used in weights or calibration fit"
 },
 "selection_history":selection,
 "summary":{"core4":bm,"challenger":cm},
 "delta_vs_core4_pct":delta,
 "promising":promising,
 "decision_rule":"Promising only if p90 and worst-decile municipality RMSE improve while pooled RMSE deteriorates by no more than 1%."
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(res,ensure_ascii=False,indent=2))
