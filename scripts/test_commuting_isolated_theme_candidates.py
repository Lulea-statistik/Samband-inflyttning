#!/usr/bin/env python3
"""Isolated seven-variable screening against fixed dynamic-commuter-interaction research baseline.
Same observations, same train-only selected baseline per year. No production changes.
"""
import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features, _geographic_error_metrics
from test_commuting_annual_paired import source_data
from audit_commuting_theme_candidates import THEMES
D=Path("docs/data")
CONTROL="lag1_andel_fa_arbetsplatser_i_egen_kommun"
CANDIDATES={key:THEMES[key] for key in ("labor_dynamics","housing_sizes")}
def main():
    data,fair,target=source_data()
    d=data["BAS"]
    pool=list(fair["eligible_pool"])
    report={"status":"isolated_candidate_screen","years":[2023,2024],
            "source":"BAS","target":target,
            "comparison":"dynamic baseline with fixed commuter interaction plus exactly one extra variable",
            "selection_train_only":True,"production_model_changed":False,"results":{}}
    for year in (2023,2024):
        train=d.loc[d.year<year].copy()
        test=d.loc[d.year==year].copy()
        if len(train)<280 or len(test)!=290:raise RuntimeError("Bad annual coverage")
        mu=float(train.commuting.mean());jm=float(train[CONTROL].mean())
        for frame in (train,test):
            frame["commute_c"]=frame.commuting-mu
            frame["commute_jobs"]=frame.commute_c*(frame[CONTROL]-jm)
        eligible=[c for c in pool if c in train and train[c].notna().all() and test[c].notna().all()]
        selected=_select_features(train,eligible,target)["selected"]
        base=list(dict.fromkeys(selected+["commute_c","commute_jobs"]))
        comparisons={}
        for theme,vars in [("reference",[]),*CANDIDATES.items()]:
            for variable in (vars if vars else [None]):
                columns=base+([variable] if variable and variable not in base else [])
                if variable and (train[variable].isna().any() or test[variable].isna().any()):
                    raise RuntimeError(f"Missing values for {variable}")
                model=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
                model.fit(train[columns],train[target])
                yhat=model.predict(test[columns])
                metrics=_geographic_error_metrics(test[target],yhat)
                mask=test.kommun_kod.to_numpy()=="2580"
                key=variable or "reference"
                comparisons[key]={"theme":theme,"rmse":metrics["rmse"],"mae":metrics["mae"],
                  "lulea_actual":float(test.loc[mask,target].iloc[0]),
                  "lulea_prediction":float(yhat[np.flatnonzero(mask)[0]])}
        report["results"][str(year)]={"train_years":sorted(int(v) for v in train.year.unique()),"n_train":len(train),
            "n_test":len(test),"selected":selected,"comparisons":comparisons}
        print(json.dumps({"year":year,"rmse":{k:round(v["rmse"],3) for k,v in comparisons.items()}},ensure_ascii=False),flush=True)
    report["limitations"]="Repeated retrospective years; exploratory variable screening only, no data-unseen confirmation. A better result here cannot authorize production promotion."
    (D/"commuting_isolated_theme_candidates.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
