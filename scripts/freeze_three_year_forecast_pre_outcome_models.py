#!/usr/bin/env python3
"""Freeze pre-outcome model parameters for the locked 3-year forecast branch.

No selection and no production change.
- Core4 OLS is fitted on the frozen four predictors.
- Full no-lookahead Ridge benchmark is fitted on the frozen 76-variable universe,
  with alpha selected by grouped 3-fold CV on the same training data.
- Training rows, feature order and model parameters are hashed/frozen.
"""
import hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")
lock=json.loads((D/"three_year_forecast_frozen_candidate_set.json").read_text(encoding="utf-8"))
core=lock["features"]
target="inflyttning_per_1000"
years=[2021,2022,2023]
ALPHAS=[0.01,0.1,1,3,10,30,100]

panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)

emp=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
emp["kommun_kod"]=emp["kommun_kod"].astype(str).str.zfill(4)
codes=set(emp.loc[emp.target_year==2024,"kommun_kod"])
extra=(emp.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct")
       .reset_index()
       .rename(columns={"target_year":"year",
                        "residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
                        "workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"}))

q=(panel[panel.kommun_kod.isin(codes)&panel.year.isin(years)]
   .merge(extra,on=["year","kommun_kod"],how="left",validate="one_to_one")
   .sort_values(["kommun_kod","year"]).reset_index(drop=True))

pool=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))["records"]
pool_names={r["feature"] for r in pool}
gate=json.loads((D/"neutral_80_candidate_data_gate.json").read_text(encoding="utf-8"))["variables"]
lookahead={"lag1_valdeltagande_pct","lag1_valdeltagande_gap_pp"}
full=sorted(
    n for n in pool_names
    if n in q and n not in lookahead
    and all(gate[n][str(y)]==290 for y in years)
)

cols=["kommun_kod","year",target]+full
work=q[cols].dropna().sort_values(["kommun_kod","year"]).reset_index(drop=True)
assert len(work)==870, len(work)
assert work.kommun_kod.nunique()==290
assert set(core).issubset(set(full))

# Canonical training-data hash.
canon=work[["kommun_kod","year",target]+full].to_csv(index=False,float_format="%.15g")
training_sha256=hashlib.sha256(canon.encode("utf-8")).hexdigest()

y=work[target].to_numpy(float)
groups=work["kommun_kod"].to_numpy()
Xc=work[core].to_numpy(float)
Xf=work[full].to_numpy(float)

# Freeze core4 using the exact StandardScaler -> OLS refit convention.
scaler_c=StandardScaler().fit(Xc)
Xcs=scaler_c.transform(Xc)
ols=LinearRegression().fit(Xcs,y)

# For interpretability also convert to original-unit coefficients.
coef_std=np.asarray(ols.coef_,dtype=float)
coef_raw=coef_std/scaler_c.scale_
intercept_raw=float(ols.intercept_ - np.sum(coef_std*scaler_c.mean_/scaler_c.scale_))

# Freeze full Ridge alpha by grouped CV using the registered grid.
cv=GroupKFold(3)
scores=[]
for alpha in ALPHAS:
    losses=[]
    for tr,va in cv.split(Xf,y,groups):
        m=make_pipeline(StandardScaler(),Ridge(alpha=alpha)).fit(Xf[tr],y[tr])
        pred=m.predict(Xf[va])
        losses.append(float(np.sqrt(np.mean((y[va]-pred)**2))))
    scores.append({"alpha":float(alpha),"mean_rmse":float(np.mean(losses))})
scores=sorted(scores,key=lambda r:(r["mean_rmse"],r["alpha"]))
chosen_alpha=scores[0]["alpha"]

scaler_f=StandardScaler().fit(Xf)
Xfs=scaler_f.transform(Xf)
ridge=Ridge(alpha=chosen_alpha).fit(Xfs,y)

out={
 "status":"pre_outcome_models_frozen",
 "production_changed":False,
 "branch":"three_year_forecast",
 "frozen_at":"2026-10-16",
 "training_years":years,
 "target":target,
 "n_rows":int(len(work)),
 "n_municipalities":int(work.kommun_kod.nunique()),
 "training_data_sha256":training_sha256,
 "core4":{
   "features":core,
   "method":"StandardScaler + OLS",
   "scaler_mean":{f:float(v) for f,v in zip(core,scaler_c.mean_)},
   "scaler_scale":{f:float(v) for f,v in zip(core,scaler_c.scale_)},
   "standardized_intercept":float(ols.intercept_),
   "standardized_coefficients":{f:float(v) for f,v in zip(core,coef_std)},
   "raw_unit_intercept":intercept_raw,
   "raw_unit_coefficients":{f:float(v) for f,v in zip(core,coef_raw)}
 },
 "full_ridge_benchmark":{
   "features":full,
   "feature_count":len(full),
   "alpha_grid":ALPHAS,
   "inner_group_cv_scores":scores,
   "chosen_alpha":chosen_alpha,
   "method":"StandardScaler + Ridge",
   "scaler_mean":{f:float(v) for f,v in zip(full,scaler_f.mean_)},
   "scaler_scale":{f:float(v) for f,v in zip(full,scaler_f.scale_)},
   "intercept":float(ridge.intercept_),
   "coefficients":{f:float(v) for f,v in zip(full,ridge.coef_)}
 },
 "future_validation_rule":{
   "refit_before_scoring":False,
   "reselect_before_scoring":False,
   "retune_alpha_before_scoring":False,
   "score_exact_frozen_parameters":True,
   "required_predictor_vintage":"captured before future outcome publication"
 },
 "notes":[
   "These frozen parameters are for untouched future validation, not production deployment.",
   "Core4 raw-unit coefficients are algebraically equivalent to the frozen standardized OLS pipeline.",
   "Any future model update must occur only after the pre-registered untouched score is recorded."
 ]
}
(D/"three_year_forecast_pre_outcome_frozen_models.json").write_text(
    json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
)
print(json.dumps({
  "training_sha256":training_sha256,
  "core4_raw_unit_intercept":intercept_raw,
  "core4_raw_unit_coefficients":out["core4"]["raw_unit_coefficients"],
  "full_ridge_chosen_alpha":chosen_alpha,
  "full_feature_count":len(full)
},ensure_ascii=False,indent=2))
