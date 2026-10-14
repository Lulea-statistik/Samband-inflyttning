#!/usr/bin/env python3
"""Isolated thematic additions to fixed dynamic baseline and commuter interaction.

Identical BAS samples, training-only feature selection, no thematic test-year
feature selection, no production change. Each theme is a predeclared block.
"""
import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data
from audit_commuting_theme_candidates import THEMES

D=Path("docs/data")
CONTROL="lag1_andel_fa_arbetsplatser_i_egen_kommun"
def main():
    sources,fair,target=source_data()
    data=sources["BAS"]
    audit=json.loads((D/"commuting_theme_candidate_coverage.json").read_text())
    groups={}
    for theme,items in audit["themes"].items():
        new=[r["feature"] for r in items if r["complete_2022_2024"] and not r["in_existing_pool"]]
        if new:groups[theme]=new
    incumbent=list(fair["incumbent_features"]);pool=list(fair["eligible_pool"])
    report={"status":"exploratory_theme_block_test","source":"BAS","test_years":[2023,2024],
            "fixed_theme_blocks":groups,"model_families":["dynamic","dynamic_interaction"],
            "fair_comparison":"Same rows and train-only dynamic selection; add each fixed full theme block to each base model",
            "production_model_changed":False,"results":{}}
    for yr in [2023,2024]:
        train=data.loc[data.year<yr].copy()
        test=data.loc[data.year==yr].copy()
        if len(train)<280 or len(test)!=290:raise RuntimeError("Nonmatching sample")
        c0=float(train.commuting.mean());j0=float(train[CONTROL].mean())
        for frame in [train,test]:
            frame["commute_c"]=frame.commuting-c0
            frame["commute_jobs"]=frame.commute_c*(frame[CONTROL]-j0)
        eligible=[c for c in pool if c in train and train[c].notna().all() and test[c].notna().all()]
        selected=_select_features(train,eligible,target)["selected"]
        outcomes={}
        for family,base in [("dynamic",selected),("dynamic_interaction",selected+["commute_c","commute_jobs"])]:
            for group,add in [("none",[]),*groups.items()]:
                cols=list(dict.fromkeys(base+add))
                est=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
                est.fit(train[cols],train[target])
                preds=est.predict(test[cols])
                scores=_geographic_error_metrics(test[target],preds)
                lidx=np.flatnonzero(test.kommun_kod.to_numpy()=="2580")
                outcomes[f"{family}__{group}"]={"features_added":add,"rmse":scores["rmse"],"mae":scores["mae"],
                    "lulea":[{"actual":float(test.iloc[i][target]),"predicted":float(preds[i])} for i in lidx]}
        report["results"][str(yr)]={"n_train":len(train),"n_test":len(test),"selected_dynamic":selected,"models":outcomes}
        print(json.dumps({"year":yr,"rmse":{k:round(v["rmse"],3) for k,v in outcomes.items()}},ensure_ascii=False),flush=True)
    report["limitations"]="Already inspected retrospective years; full blocks are not independently feature-selected. Apparent gain is exploratory; use future holdout to evaluate frozen candidate."
    (D/"commuting_theme_block_test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
