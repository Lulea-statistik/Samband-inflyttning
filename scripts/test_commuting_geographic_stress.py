#!/usr/bin/env python3
"""Stress-test frozen commuting feature forms using geographical 2024 CV.
Train-only selection; same observations and folds; bootstrap municipality-paired
RMSE difference; yearly historical context is read from earlier comparison.
No model promotion or production edits.
"""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data
from test_commuting_smooth_weight import sigmoid,CONTROL
D=Path("docs/data")
FORMS={"none":[],"linear":["commute_c"],"interaction":["commute_c","commute_jobs"],
       "smooth":["commute_gated"],"linear_plus_smooth":["commute_c","commute_gated"]}
def features(train,test):
    mean=float(train.commuting.mean()); med=float(train.commuting.median())
    iqr=float(train.commuting.quantile(.75)-train.commuting.quantile(.25))
    if iqr<=0:raise RuntimeError("Invalid commuting IQR")
    jobmean=float(train[CONTROL].mean())
    for frame in (train,test):
        frame["commute_c"]=frame.commuting-mean
        frame["commute_jobs"]=frame.commute_c*(frame[CONTROL]-jobmean)
        frame["commute_gated"]=frame.commute_c*sigmoid(4*(frame.commuting-med)/iqr)
def score(y,p):return _geographic_error_metrics(pd.Series(y),pd.Series(p))
def bootstrap(y,ref,challenger,seed):
    rng=np.random.default_rng(seed);N=len(y);diff=[]
    for _ in range(2000):
        ix=rng.integers(0,N,N)
        diff.append(np.sqrt(np.mean((y[ix]-ref[ix])**2))-np.sqrt(np.mean((y[ix]-challenger[ix])**2)))
    return {"difference_rmse":float(score(y,ref)["rmse"]-score(y,challenger)["rmse"]),
            "ci95":[float(np.quantile(diff,.025)),float(np.quantile(diff,.975))],
            "n_improved":int((np.abs(y-challenger)<np.abs(y-ref)).sum()),
            "n_worsened":int((np.abs(y-challenger)>np.abs(y-ref)).sum())}
def main():
    sources,fair,target=source_data()
    pool=list(fair["eligible_pool"])
    incumbent=list(fair["incumbent_features"])
    d=sources["BAS"]
    # Strict geographical CV: train from 2022-23 other municipalities, evaluate 2024.
    rows=[]
    for fold in range(5):
        ids=sorted(d.loc[d.year==2024].kommun_kod.unique())
        hold={id for id in ids if int(hashlib.sha256(("validation-140:"+id).encode()).hexdigest()[:12],16)%5==fold}
        train=d.loc[d.year.lt(2024)&~d.kommun_kod.isin(hold)].copy()
        test=d.loc[d.year.eq(2024)&d.kommun_kod.isin(hold)].copy()
        if len(train)<350 or len(test)<25:raise RuntimeError(f"Bad geographical fold {fold}: {len(train)} {len(test)}")
        features(train,test)
        eligible=[c for c in pool if c in train and train[c].notna().all() and test[c].notna().all()]
        selected=_select_features(train,eligible,target)["selected"]
        models={}
        for family,base in (("incumbent",incumbent),("dynamic",selected)):
            for form,add in FORMS.items():
                fs=list(dict.fromkeys(base+add))
                estimator=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
                estimator.fit(train[fs],train[target])
                models[f"{family}_{form}"]=estimator.predict(test[fs])
        for i,(_,row) in enumerate(test.iterrows()):
            rows.append({"municipality":row.kommun_kod,"actual":float(row[target]),
                         "out_share":float(row.commuting),
                         "fold":fold,**{name:float(pred[i]) for name,pred in models.items()}})
        print(f"completed geographic fold {fold}; train={len(train)} test={len(test)}",flush=True)
    p=pd.DataFrame(rows).sort_values("municipality")
    if len(p)!=290 or p.municipality.nunique()!=290:raise RuntimeError("Incomplete municipality holdout")
    y=p.actual.to_numpy()
    result={"status":"frozen_form_geographic_stress_test","test_year":2024,"train_years":[2022,2023],
       "n":len(p),"folds":5,"method":"same geographic folds, no held municipality in any training year",
       "bootstrap_resamples":2000,"production_model_changed":False,
       "limitation":"Retrospective 2024 was used when designing all feature forms; bootstrap intervals ignore form selection and temporal generalization.",
       "metrics":{},"paired":{},"quartiles":[],"lulea":[]}
    for key in models:
        result["metrics"][key]=score(y,p[key].to_numpy())
    for family in ("dynamic","incumbent"):
        zero=p[f"{family}_none"].to_numpy()
        linear=p[f"{family}_linear"].to_numpy()
        for variant in ("linear","interaction","smooth","linear_plus_smooth"):
            result["paired"][f"{family}_{variant}_vs_none"]=bootstrap(y,zero,p[f"{family}_{variant}"].to_numpy(),20261014)
            if variant!="linear":
                result["paired"][f"{family}_{variant}_vs_linear"]=bootstrap(y,linear,p[f"{family}_{variant}"].to_numpy(),20261015)
    q=pd.qcut(p.out_share.rank(method="first"),4,labels=["Q1","Q2","Q3","Q4"])
    for group in ("Q1","Q2","Q3","Q4"):
        sub=p.loc[q==group]
        result["quartiles"].append({"group":group,"n":len(sub),
             "mean_out_share":float(sub.out_share.mean()),
             "rmse":{key:score(sub.actual.to_numpy(),sub[key].to_numpy())["rmse"] for key in models}})
    result["lulea"]=p.loc[p.municipality=="2580"].to_dict("records")
    (D/"commuting_geographic_stress_test.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"rmse":{k:round(v["rmse"],3) for k,v in result["metrics"].items()}},ensure_ascii=False))
if __name__=="__main__":main()
