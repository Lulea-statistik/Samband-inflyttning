#!/usr/bin/env python3
"""Diagnose unstable job-growth coefficient and collinearity with fixed BAS folds.

Research-only; coefficients are predictive conditional associations, not causal.
2023 and 2024 are repeatedly inspected, so no prospective claims.
"""
import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data

D=Path("docs/data")
JOB="lag1_sysselsatta_bostad_forandring_pct"
MARKET="lag1_andel_fa_arbetsplatser_i_egen_kommun"
CHECK=["lag1_sysselsatta_bostad_forandring_pct","lag1_sysselsatta_arbetsstalle_forandring_pct",
       "lag1_sysselsatta_bostad_sasongsvariation_pct","lag1_sysselsatta_arbetsstalle_sasongsvariation_pct",
       "lag1_andel_fa_arbetsplatser_i_egen_kommun"]
def main():
    sources,fair,target=source_data()
    d=sources["BAS"];pool=list(fair["eligible_pool"])
    report={"status":"job_growth_sign_stability_research","source":"BAS","years":[2023,2024],
       "production_model_changed":False,"results":{},
       "limitation":"Retrospective years already used repeatedly; conditional coefficients are not causal effects."}
    for yr in (2023,2024):
        train=d.loc[d.year<yr].copy();test=d.loc[d.year==yr].copy()
        c0=float(train.commuting.mean());m0=float(train[MARKET].mean())
        for frame in (train,test):
            frame["commute_c"]=frame.commuting-c0
            frame["commute_jobs"]=frame.commute_c*(frame[MARKET]-m0)
        eligible=[c for c in pool if c in train and train[c].notna().all() and test[c].notna().all()]
        selected=_select_features(train,eligible,target)["selected"]
        base=list(dict.fromkeys(selected+["commute_c","commute_jobs"]))
        specs={"univariate_job":[JOB],
            "basic_adjusted":[JOB,"commute_c","commute_jobs"],
            "baseline_without_job":base,
            "baseline_with_job":list(dict.fromkeys(base+[JOB])),
            "baseline_job_and_other_growth":list(dict.fromkeys(base+[JOB,"lag1_sysselsatta_arbetsstalle_forandring_pct"])),
            "baseline_job_and_seasonality":list(dict.fromkeys(base+[JOB,"lag1_sysselsatta_bostad_sasongsvariation_pct"]))}
        models={}
        for name,cols in specs.items():
            est=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            est.fit(train[cols],train[target]);pred=est.predict(test[cols])
            coef=float(est.named_steps["ridgecv"].coef_[cols.index(JOB)]) if JOB in cols else None
            models[name]={"rmse":_geographic_error_metrics(test[target],pred)["rmse"],
                "mae":_geographic_error_metrics(test[target],pred)["mae"],
                "standardized_job_coefficient":coef,
                "chosen_alpha":float(est.named_steps["ridgecv"].alpha_),
                "feature_count":len(cols)}
        corrs={}
        for col in CHECK[1:]:
            corrs[col]=float(train[[JOB,col]].corr().iloc[0,1])
        model_corr={col:float(train[[JOB,col]].corr().iloc[0,1]) for col in selected if col!=JOB and train[col].std()>0}
        strongest=sorted(model_corr.items(),key=lambda kv:abs(kv[1]),reverse=True)[:10]
        report["results"][str(yr)]={"n_train":len(train),"n_test":len(test),
            "train_years":sorted(int(y) for y in train.year.unique()),"models":models,
            "pairwise_correlations":corrs,"top_correlations_with_selected_features":strongest,
            "job_train_mean":float(train[JOB].mean()),"job_train_sd":float(train[JOB].std()),
            "job_test_mean":float(test[JOB].mean())}
        print(json.dumps({"year":yr,"models":{k:{"rmse":round(v["rmse"],3),"job_coefficient":v["standardized_job_coefficient"]} for k,v in models.items()}},ensure_ascii=False),flush=True)
    (D/"commuting_job_sign_diagnostic.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
