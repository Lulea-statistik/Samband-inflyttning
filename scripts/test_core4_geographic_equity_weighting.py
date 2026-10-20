#!/usr/bin/env python3
import json, math
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")
panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)

features=[
 "lag1_inflyttning_per_1000",
 "lag1_utflyttning_per_1000",
 "lag1_kolada_arbetslosa_18_65_pct",
 "lag1_bostadsbestandsforandring_pct"
]
target="inflyttning_per_1000"
years=list(range(2017,2025))
window=6

# Use exactly the balanced historical core4 prediction panel as evaluation reference.
ref=pd.read_csv(D/"three_year_forecast_core4_historical_reconstructed_predictions.csv",
                dtype={"kommun_kod":str})
ref["kommun_kod"]=ref["kommun_kod"].astype(str).str.zfill(4)
ref=ref[(ref.window_years==6)&ref.forecast_year.isin(years)].copy()
official=sorted(ref.kommun_kod.unique())
if len(official)!=290: raise SystemExit("Expected 290 municipalities")

# Candidate weights based only on prior training-window residual difficulty.
# lambda=0 => ordinary OLS. Positive lambda upweights municipalities with larger
# historical absolute residuals, with capped weights to avoid instability.
lambdas=[0.0,0.25,0.5,1.0]
cap=2.0
eps=1e-9

rows=[]
for fy in years:
    train_years=list(range(fy-window,fy))
    tr=panel[panel.year.isin(train_years)&panel.kommun_kod.isin(official)].copy()
    te=panel[(panel.year==fy)&panel.kommun_kod.isin(official)].copy()
    need=features+[target]
    tr=tr.dropna(subset=need)
    te=te.dropna(subset=need)
    if len(tr)!=290*window or len(te)!=290:
        raise SystemExit(f"Incomplete panel for {fy}: {len(tr)} {len(te)}")

    # First-pass OLS on the training window only.
    base=make_pipeline(StandardScaler(),LinearRegression())
    base.fit(tr[features],tr[target])
    tr_pred=base.predict(tr[features])
    tr_resid=tr_pred-tr[target].to_numpy(float)
    tmp=pd.DataFrame({"kommun_kod":tr.kommun_kod.to_numpy(),"abs_resid":np.abs(tr_resid)})
    difficulty=tmp.groupby("kommun_kod").abs_resid.mean()
    med=float(difficulty.median())
    rel=(difficulty/(med+eps)).clip(lower=0.5,upper=cap)

    for lam in lambdas:
        if lam==0:
            weights=np.ones(len(tr),dtype=float)
        else:
            wmap={k:1.0+lam*(float(v)-1.0) for k,v in rel.items()}
            weights=np.asarray([max(0.25,min(cap,wmap[k])) for k in tr.kommun_kod],dtype=float)

        # Standardize explicitly because Pipeline fit_params differ by sklearn version.
        sc=StandardScaler().fit(tr[features])
        Xtr=sc.transform(tr[features]); Xte=sc.transform(te[features])
        lr=LinearRegression().fit(Xtr,tr[target],sample_weight=weights)
        pred=lr.predict(Xte)
        for (_,r),p in zip(te.iterrows(),pred):
            rows.append({
              "forecast_year":fy,
              "lambda":lam,
              "kommun_kod":r["kommun_kod"],
              "actual":float(r[target]),
              "prediction":float(p),
              "error":float(p-r[target])
            })

o=pd.DataFrame(rows)
o.to_csv(D/"core4_geographic_equity_weighted_challenger_predictions.csv",index=False)

def q(x,p): return float(np.quantile(np.asarray(x,float),p))
def metrics(df):
    e=df.error.to_numpy(float); ae=np.abs(e)
    by=df.groupby("kommun_kod").error.apply(lambda x: float(np.sqrt(np.mean(np.square(x.to_numpy(float))))))
    vals=by.to_numpy(float)
    return {
      "pooled_rmse":float(np.sqrt(np.mean(e*e))),
      "pooled_mae":float(np.mean(ae)),
      "mean_municipality_rmse":float(np.mean(vals)),
      "median_municipality_rmse":q(vals,.5),
      "sd_municipality_rmse":float(np.std(vals,ddof=1)),
      "p90_municipality_rmse":q(vals,.9),
      "p95_municipality_rmse":q(vals,.95),
      "worst_decile_mean_rmse":float(np.mean(np.sort(vals)[-29:])),
      "max_municipality_rmse":float(np.max(vals)),
      "share_municipalities_rmse_gt_10":float(np.mean(vals>10))
    }

summary={}
for lam in lambdas:
    m=metrics(o[o["lambda"]==lam])
    summary[str(lam)]=m
base=summary["0.0"]
for lam in lambdas:
    m=summary[str(lam)]
    m["delta_vs_ols_pct"]={
      "pooled_rmse":100*(m["pooled_rmse"]/base["pooled_rmse"]-1),
      "p90_municipality_rmse":100*(m["p90_municipality_rmse"]/base["p90_municipality_rmse"]-1),
      "worst_decile_mean_rmse":100*(m["worst_decile_mean_rmse"]/base["worst_decile_mean_rmse"]-1),
      "sd_municipality_rmse":100*(m["sd_municipality_rmse"]/base["sd_municipality_rmse"]-1)
    }

# Pareto in pooled RMSE + p90 municipality RMSE.
pareto=[]
for lam in lambdas:
    a=summary[str(lam)]
    dom=False
    for other in lambdas:
        if other==lam: continue
        b=summary[str(other)]
        if (b["pooled_rmse"]<=a["pooled_rmse"] and b["p90_municipality_rmse"]<=a["p90_municipality_rmse"]
            and (b["pooled_rmse"]<a["pooled_rmse"] or b["p90_municipality_rmse"]<a["p90_municipality_rmse"])):
            dom=True; break
    if not dom: pareto.append(lam)

res={
 "status":"core4_geographic_equity_weighted_challenger",
 "production_changed":False,
 "structural_core4_changed":False,
 "variable_selection_reopened":False,
 "evaluation_years":years,
 "n_municipalities":290,
 "training_window_years":6,
 "features":features,
 "weighting":{
   "difficulty":"municipality mean absolute in-sample residual within each historical training window",
   "relative_to":"median municipality difficulty in that training window",
   "weight_formula":"1 + lambda * (relative_difficulty - 1)",
   "relative_difficulty_bounds":[0.5,cap],
   "final_weight_bounds":[0.25,cap],
   "lambdas":lambdas,
   "leakage_guard":"forecast-year outcome is never used to construct weights"
 },
 "summary":summary,
 "pareto_lambdas":pareto,
 "decision_rule":"Promising only if p90 and worst-decile municipality RMSE improve with no more than 1% deterioration in pooled RMSE; production remains frozen."
}
(D/"core4_geographic_equity_weighted_challenger.json").write_text(
 json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(res,ensure_ascii=False,indent=2))
