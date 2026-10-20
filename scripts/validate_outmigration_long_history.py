#!/usr/bin/env python3
"""Long historical rolling-origin validation for compact outmigration core.

Goal:
- require consistency across many forecast origins, not only recent years;
- use only variables with full 290-municipality coverage back to 2003;
- keep recent-only variables (e.g. fritidshus structure) out of the long-history core;
- compare identical common samples with 3, 5, 6 and 10 year rolling training windows.

Research only. No production changes.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)

TARGET="utflyttning_per_1000"
MODELS={
 "lag1_only":["lag1_utflyttning_per_1000"],
 "lag1_plus_age20_34":["lag1_utflyttning_per_1000","lag1_andel_20_34"],
 "lag1_plus_log_population":["lag1_utflyttning_per_1000","lag1_log_folkmangd"],
 "lag1_plus_age_population":["lag1_utflyttning_per_1000","lag1_andel_20_34","lag1_log_folkmangd"]
}
WINDOWS=[3,5,6,10]
ALPHAS=[0.0,0.1,1.0,10.0]

for c in sorted(set([TARGET]+sum(MODELS.values(),[]))):
    if c not in p: raise RuntimeError(f"Missing {c}")
    p[c]=pd.to_numeric(p[c],errors="coerce")

# All long-history features are fully available from target year 2003 onward.
FIRST_DATA_YEAR=2003
LAST_FORECAST_YEAR=2024

def pipe(alpha):
    return make_pipeline(StandardScaler(),Ridge(alpha=1e-10 if alpha==0 else alpha))

def select_alpha(train,features):
    # Rolling-origin inner validation inside the available training window:
    # use the final training year as validation where possible.
    years=sorted(train.year.unique())
    if len(years)<3:
        return 0.0
    val_year=years[-1]
    fit=train[train.year<val_year]
    val=train[train.year==val_year]
    scores=[]
    for a in ALPHAS:
        m=pipe(a);m.fit(fit[features],fit[TARGET]);pr=m.predict(val[features])
        e=val[TARGET].to_numpy(float)-pr
        scores.append((float(np.sqrt(np.mean(e*e))),a))
    scores.sort(key=lambda z:(z[0],-z[1]))
    return scores[0][1]

rows=[]
for window in WINDOWS:
    first_forecast=FIRST_DATA_YEAR+window
    for fy in range(first_forecast,LAST_FORECAST_YEAR+1):
        train_years=list(range(fy-window,fy))
        for name,features in MODELS.items():
            tr=p[p.year.isin(train_years)].dropna(subset=[TARGET]+features).copy()
            te=p[p.year.eq(fy)].dropna(subset=[TARGET]+features).copy()
            if len(tr)!=290*window or len(te)!=290:
                continue
            if tr.groupby("year").kommun_kod.nunique().min()!=290 or te.kommun_kod.nunique()!=290:
                continue
            alpha=select_alpha(tr,features)
            m=pipe(alpha);m.fit(tr[features],tr[TARGET]);pr=m.predict(te[features])
            for (_,r),pred in zip(te.iterrows(),pr):
                rows.append({
                  "window":window,"forecast_year":fy,"model":name,
                  "kommun_kod":r["kommun_kod"],"actual":float(r[TARGET]),
                  "prediction":float(pred),"error":float(pred-r[TARGET]),"alpha":alpha
                })

o=pd.DataFrame(rows)
if o.empty: raise RuntimeError("No rolling-origin predictions")

def metric(df):
    e=df.error.to_numpy(float)
    return {"rmse":float(np.sqrt(np.mean(e*e))),
            "mae":float(np.mean(np.abs(e))),
            "bias_prediction_minus_actual":float(np.mean(e)),
            "n":int(len(df))}

summary={}
for window in WINDOWS:
    q=o[o.window.eq(window)]
    if q.empty: continue
    years=[int(x) for x in sorted(q.forecast_year.unique())]
    models={}
    base=None
    for name in MODELS:
        z=q[q.model.eq(name)]
        if z.empty: continue
        overall=metric(z)
        yearly=[]
        for fy,g in z.groupby("forecast_year"):
            m=metric(g);m["forecast_year"]=int(fy);yearly.append(m)
        models[name]={"overall":overall,"yearly":yearly}
        if name=="lag1_only": base=overall
    if base:
        for name,v in models.items():
            v["delta_rmse_pct_vs_lag1_only"]=100*(v["overall"]["rmse"]/base["rmse"]-1)
            v["delta_mae_pct_vs_lag1_only"]=100*(v["overall"]["mae"]/base["mae"]-1)
            # count forecast years with lower RMSE than lag1-only
            base_y={x["forecast_year"]:x["rmse"] for x in models["lag1_only"]["yearly"]}
            wins=0; losses=0; ties=0; diffs=[]
            for x in v["yearly"]:
                d=100*(x["rmse"]/base_y[x["forecast_year"]]-1)
                diffs.append(d)
                if d < -1e-9: wins+=1
                elif d > 1e-9: losses+=1
                else: ties+=1
            v["year_consistency"]={
              "wins_vs_lag1_only":wins,"losses_vs_lag1_only":losses,"ties":ties,
              "share_years_better":float(wins/len(diffs)),
              "median_year_delta_rmse_pct":float(np.median(diffs)),
              "worst_year_delta_rmse_pct":float(np.max(diffs)),
              "best_year_delta_rmse_pct":float(np.min(diffs))
            }
    summary[str(window)]={"forecast_years":years,"models":models}

# Cross-window stability.
cross=[]
for name in MODELS:
    vals=[]; shares=[]; worst=[]
    for w in WINDOWS:
        d=summary.get(str(w),{}).get("models",{}).get(name)
        if d:
            vals.append(d["delta_rmse_pct_vs_lag1_only"])
            shares.append(d["year_consistency"]["share_years_better"])
            worst.append(d["year_consistency"]["worst_year_delta_rmse_pct"])
    cross.append({
      "model":name,"features":MODELS[name],
      "mean_delta_rmse_pct_vs_lag1_only":float(np.mean(vals)),
      "mean_share_years_better":float(np.mean(shares)),
      "worst_observed_year_delta_rmse_pct":float(np.max(worst)),
      "windows_evaluated":len(vals)
    })
cross.sort(key=lambda r:(r["mean_delta_rmse_pct_vs_lag1_only"],-r["mean_share_years_better"],r["worst_observed_year_delta_rmse_pct"]))

res={
 "status":"outmigration_long_history_rolling_origin_validation",
 "production_changed":False,"inflow_model_changed":False,
 "target":TARGET,
 "principle":"Selection must be consistent over many historical forecast origins; recent-only variables are not eligible for the long-history core.",
 "windows":WINDOWS,
 "models":MODELS,
 "summary":summary,
 "cross_window_ranking":cross,
 "recent_only_variables_excluded_from_core":["lag1_log_fritidshus_per_1000_inv"],
 "decision_guidance":"Prefer a compact model only if it improves aggregate RMSE across windows, wins in a clear majority of forecast years, and has no severe historical failure years."
}
(D/"outmigration_long_history_rolling_origin_validation.json").write_text(
 json.dumps(res,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
o.to_csv(D/"outmigration_long_history_rolling_origin_predictions.csv",index=False)
print(json.dumps(res,ensure_ascii=False,indent=2))
