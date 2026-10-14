#!/usr/bin/env python3
"""Audit and evaluate long-term unemployment with identical rolling train windows.

No BAS or RAMS commuting data is used: the historic panel determines available
years. A candidate is considered only when target, candidate and the same blind
control columns cover all 290 municipalities in each train and test year.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error,mean_absolute_error
from build_analysis import _select_features
D=Path("docs/data")
CAND="lag1_kolada_langtidsarbetslosa_pct"
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km",
          "lag1_inkomst_tkr","lag1_andel_eftergymnasial","lag1_andel_studerande",
          "lag1_andel_fa_arbetsplatser_i_egen_kommun","lag1_kolada_arbetslosa_18_65_pct"]
FORBIDDEN=("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")
def main():
    p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    p["kommun_kod"]=p.kommun_kod.str.zfill(4)
    model=json.loads((D/"model.json").read_text())
    target=model["target"]
    required=[target,CAND]+CONTROLS
    absent=[c for c in required if c not in p.columns]
    if absent:raise RuntimeError(f"Missing columns: {absent}")
    if any(any(z in c for z in FORBIDDEN) for c in CONTROLS):raise RuntimeError("Demographic control")
    years=sorted(int(y) for y in p.year.dropna().unique())
    coverage={}
    for year in years:
        t=p.loc[p.year.eq(year)]
        coverage[str(year)]={"n_municipalities":int(t.kommun_kod.nunique()),
          "complete_joint":int(t.dropna(subset=required).kommun_kod.nunique()),
          "candidate_nonmissing":int(t[CAND].notna().sum()),
          "target_nonmissing":int(t[target].notna().sum())}
    complete=[y for y in years if coverage[str(y)]["complete_joint"]==290 and coverage[str(y)]["n_municipalities"]==290]
    # All forecast years in one comparison must have exactly the same training length.
    candidates={}
    for length in (3,5,10):
        forecasts=[y for y in complete if all(z in complete for z in range(y-length,y))]
        candidates[str(length)]=forecasts
    report={"status":"fixed_window_long_term_unemployment","panel_source":"docs/data/panel.csv",
      "definition":"one-year ahead, fixed rolling training years; identical common complete-case municipality-years",
      "feature_columns":CONTROLS,"candidate":CAND,"coverage_by_year":coverage,
      "eligible_forecast_years":candidates,"results":{},"production_model_changed":False}
    # Use consistent structural columns across all years. Avoid selecting over 21 features
    # with one-year training or differing features by test year; these are fixed a priori.
    for length,forecast_years in candidates.items():
        rows={}
        for year in forecast_years:
            train=p.loc[p.year.isin(range(year-int(length),year))].copy()
            test=p.loc[p.year.eq(year)].copy()
            if len(train)!=290*int(length) or len(test)!=290:raise RuntimeError("Missing municipality-year rows")
            train=train.sort_values(["year","kommun_kod"]);test=test.sort_values("kommun_kod")
            if train[required].isna().any().any() or test[required].isna().any().any():raise RuntimeError("Incomplete sample")
            outcome={}
            for key,features in {"reference":CONTROLS,"with_long_term_unemployment":CONTROLS+[CAND]}.items():
                fit=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
                fit.fit(train[features],train[target]);pred=fit.predict(test[features])
                truth=test[target].to_numpy()
                lx=np.flatnonzero(test.kommun_kod.to_numpy()=="2580")
                outcome[key]={"rmse":float(np.sqrt(mean_squared_error(truth,pred))),
                  "mae":float(mean_absolute_error(truth,pred)),
                  "lulea_actual":float(truth[lx[0]]),"lulea_pred":float(pred[lx[0]]),
                  "coefficient":float(fit.named_steps["ridgecv"].coef_[-1]) if key!="reference" else None}
            rows[str(year)]={"n_train":len(train),"n_test":len(test),"train_years":list(range(year-int(length),year)),
                              "models":outcome,"rmse_gain":outcome["reference"]["rmse"]-outcome["with_long_term_unemployment"]["rmse"]}
        report["results"][length]={"n_forecast_years":len(rows),"years":rows,
           "mean_rmse_gain":float(np.mean([x["rmse_gain"] for x in rows.values()])) if rows else None}
        print(f"window={length} eligible_forecast_years={forecast_years}",flush=True)
    report["decision"]="No automatic promotion. Require at least three test years in a fixed-length window, consistency and local checks; selection retrospective."
    report["limitations"]=["Preselected eight blind structural controls; not the full published model.",
      "Lagged variables reflect previous year's measurements, not all historic definitions are necessarily method-harmonized.",
      "Years previously explored cannot be treated as unseen confirmation."]
    (D/"fixed_window_long_term_unemployment_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
