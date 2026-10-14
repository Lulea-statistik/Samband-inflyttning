#!/usr/bin/env python3
"""Decompose changing job-growth sign: fixed feature sets versus growing training set.

Select two feature sets on the allowed training folds separately; then hold each
fixed across the 2023/2024 training-period fits. Research only.
"""
import json
from pathlib import Path
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data

D=Path("docs/data")
JOB="lag1_sysselsatta_bostad_forandring_pct"
CONTROL="lag1_andel_fa_arbetsplatser_i_egen_kommun"
def main():
    sources,fair,target=source_data();d=sources["BAS"]
    pool=list(fair["eligible_pool"])
    train22=d.loc[d.year.eq(2022)].copy()
    train2324=d.loc[d.year.isin([2022,2023])].copy()
    sets={}
    for name,frame in [("selected_on_2022",train22),("selected_on_2022_2023",train2324)]:
        eligible=[c for c in pool if c in frame.columns and frame[c].notna().all()]
        sets[name]=_select_features(frame,eligible,target)["selected"]
    # Keep feature membership unchanged; refit only scaling, regression and train centers.
    report={"status":"fixed_feature_set_job_sign_decomposition","feature_sets":sets,
        "results":{},"production_model_changed":False,
        "limitation":"2024 feature set was selected using 2023 outcomes; applying it retroactively to 2023 is diagnostic, not valid forecast validation."}
    for period,train_years,forecast in [("train_2022",[2022],2023),("train_2022_2023",[2022,2023],2024)]:
        train=d.loc[d.year.isin(train_years)].copy();test=d.loc[d.year.eq(forecast)].copy()
        cm=float(train.commuting.mean());jm=float(train[CONTROL].mean())
        for frame in (train,test):
            frame["commute_c"]=frame.commuting-cm
            frame["commute_jobs"]=frame.commute_c*(frame[CONTROL]-jm)
        report["results"][period]={}
        for set_name,base in sets.items():
            for variant,cols in {
              "linear_and_interaction":list(dict.fromkeys(base+["commute_c","commute_jobs",JOB])),
              "without_job":list(dict.fromkeys(base+["commute_c","commute_jobs"]))
            }.items():
                missing=[c for c in cols if c not in train.columns or train[c].isna().any() or test[c].isna().any()]
                if missing:raise RuntimeError(f"Missing features {missing} on {period} {set_name}")
                model=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
                model.fit(train[cols],train[target])
                pred=model.predict(test[cols])
                report["results"][period][set_name+"__"+variant]={
                    "feature_count":len(cols),
                    "job_coefficient":float(model.named_steps["ridgecv"].coef_[cols.index(JOB)]) if JOB in cols else None,
                    "alpha":float(model.named_steps["ridgecv"].alpha_),
                    "rmse":float(_geographic_error_metrics(test[target],pred)["rmse"]),
                    "mae":float(_geographic_error_metrics(test[target],pred)["mae"])}
        print(json.dumps({"period":period,"models":{k:{"coef":v["job_coefficient"],"rmse":round(v["rmse"],3)} for k,v in report["results"][period].items()}},ensure_ascii=False),flush=True)
    (D/"commuting_job_sign_fixed_sets.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\\n",encoding="utf-8")
if __name__=="__main__":main()
