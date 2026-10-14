#!/usr/bin/env python3
"""Explore smoothly gated outcommuting effect; methodology regimes never pooled.

Fixed train-only gate: logistic((outcommuting - training median)/training IQR).
For comparability use the same source, outcomes, samples and annual fitting as
the earlier interaction experiment. This is retrospective exploratory testing.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data

OUT=Path("docs/data")
CONTROL="lag1_andel_fa_arbetsplatser_i_egen_kommun"

def sigmoid(z):
    z=np.clip(z,-35,35)
    return 1/(1+np.exp(-z))

def main():
    sources,fair,target=source_data()
    incumbent=list(fair["incumbent_features"])
    pool=list(fair["eligible_pool"])
    report={"status":"exploratory_smooth_commuting_complete",
            "sources_separate":True,
            "gate":"sigmoid(4*(outcommuting-share - train median)/train IQR)",
            "gate_fitted_on_training_only":True,
            "note":"Fixed smooth weighting, not a test-tuned threshold. Gate is monotone, not a conditional claim about causal effects.",
            "production_model_changed":False,"results":{}}
    for source,whole in sources.items():
        report["results"][source]={}
        for year in sorted(whole.year.unique())[1:]:
            train=whole.loc[whole.year<year].copy()
            test=whole.loc[whole.year==year].copy()
            if len(train)<280 or len(test)!=290:raise RuntimeError(f"Invalid annual sample {source} {year}")
            median=float(train.commuting.median())
            iqr=float(train.commuting.quantile(.75)-train.commuting.quantile(.25))
            if iqr<=0:raise RuntimeError("Invalid commute share interquartile spread")
            commute_mean=float(train.commuting.mean())
            job_mean=float(train[CONTROL].mean())
            for frame in (train,test):
                frame["commuting_centered"]=frame.commuting-commute_mean
                frame["commuting_market_interaction"]=frame.commuting_centered*(frame[CONTROL]-job_mean)
                frame["smooth_gate"]=sigmoid(4*(frame.commuting-median)/iqr)
                frame["commuting_gated"]=frame.commuting_centered*frame.smooth_gate
            allowed=[c for c in pool if c in train and train[c].notna().all() and test[c].notna().all()]
            selected=_select_features(train,allowed,target)["selected"]
            groups={"none":[],"linear":["commuting_centered"],
                    "interaction":["commuting_centered","commuting_market_interaction"],
                    "smooth":["commuting_gated"],
                    "linear_plus_smooth":["commuting_centered","commuting_gated"]}
            model_preds={}
            for family,base in (("incumbent",incumbent),("dynamic",selected)):
                for variant,add in groups.items():
                    cols=list(dict.fromkeys(base+add))
                    est=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
                    est.fit(train[cols],train[target])
                    model_preds[f"{family}_{variant}"]=est.predict(test[cols])
            summary={"n_train":len(train),"n_test":len(test),
                     "train_years":sorted(int(x) for x in train.year.unique()),
                     "gate_median":median,"gate_iqr":iqr,
                     "dynamic_selected":selected,
                     "metrics":{name:_geographic_error_metrics(test[target],pred) for name,pred in model_preds.items()},
                     "quartiles":[]}
            groupings=pd.qcut(test.commuting.rank(method="first"),4,labels=["Q1","Q2","Q3","Q4"])
            for q in ["Q1","Q2","Q3","Q4"]:
                ix=(groupings==q).to_numpy()
                summary["quartiles"].append({"quartile":q,"n":int(ix.sum()),
                    "mean_share":float(test.commuting.to_numpy()[ix].mean()),
                    "mean_gate_weight":float(test.smooth_gate.to_numpy()[ix].mean()),
                    "rmse":{k:_geographic_error_metrics(test[target].to_numpy()[ix],pred[ix])["rmse"] for k,pred in model_preds.items()}})
            lulea=np.flatnonzero(test.kommun_kod.to_numpy()=="2580")
            summary["lulea"]=[{"actual":float(test.iloc[i][target]),"outcommuting_share":float(test.iloc[i].commuting),
                "weight":float(test.iloc[i].smooth_gate),**{k:float(pred[i]) for k,pred in model_preds.items()}} for i in lulea]
            report["results"][source][str(year)]=summary
            print(json.dumps({"source":source,"year":int(year),
                "dynamic_rmse":{k:round(v["rmse"],3) for k,v in summary["metrics"].items() if k.startswith("dynamic_")}},ensure_ascii=False),flush=True)
    report["caution"]="Previously explored years, not independent prospective validation. Any apparent gain must be re-evaluated on an untouched outcome year."
    (OUT/"commuting_smooth_weight_test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")

if __name__=="__main__":main()
