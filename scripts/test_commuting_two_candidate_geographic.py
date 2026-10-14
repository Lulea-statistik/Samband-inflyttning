#!/usr/bin/env python3
"""Geographic municipality-holdout stress for employment and small-home challenger.

Same deterministic geographic splits, same dynamic selection in training only,
and identical holdout outcomes. Retrospective 2024 is NOT prospective validation.
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

D=Path("docs/data")
JOB="lag1_sysselsatta_bostad_forandring_pct"
SMALL="lag1_andel_bostader_70_max"
CONTROL="lag1_andel_fa_arbetsplatser_i_egen_kommun"
ADDITIONS={"reference":[],"employment":[JOB],"small_housing":[SMALL],"combined":[JOB,SMALL]}

def metrics(y,p):
    return _geographic_error_metrics(pd.Series(y),pd.Series(p))

def main():
    sources,fair,target=source_data(); d=sources["BAS"]
    pool=list(fair["eligible_pool"])
    report={"status":"geographic_holdout_stress","year":2024,"train_years":[2022,2023],
            "design":"Five deterministic municipality holdouts; each holdout absent from both training years",
            "retrospective_selection_warning":"Variants chosen from previously inspected 2023-2024 outcomes, not independent validation.",
            "production_model_changed":False,"coefficient_checks":[]}
    result_rows=[]
    for fold in range(5):
        ids=sorted(d.loc[d.year==2024].kommun_kod.unique())
        held={c for c in ids if int(hashlib.sha256(("validation-140:"+c).encode()).hexdigest()[:12],16)%5==fold}
        train=d.loc[(d.year<2024)&(~d.kommun_kod.isin(held))].copy()
        test=d.loc[(d.year==2024)&d.kommun_kod.isin(held)].copy()
        if len(test)<25 or len(train)<350:raise RuntimeError(f"Bad fold {fold}")
        cm=float(train.commuting.mean()); jm=float(train[CONTROL].mean())
        for frame in (train,test):
            frame["commute_c"]=frame.commuting-cm
            frame["commute_jobs"]=frame.commute_c*(frame[CONTROL]-jm)
        eligible=[c for c in pool if c in train and train[c].notna().all() and test[c].notna().all()]
        selected=_select_features(train,eligible,target)["selected"]
        base=list(dict.fromkeys(selected+["commute_c","commute_jobs"]))
        pred={}
        for name,added in ADDITIONS.items():
            cols=list(dict.fromkeys(base+added))
            model=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            model.fit(train[cols],train[target]);pred[name]=model.predict(test[cols])
            if JOB in cols:
                ridge=model.named_steps["ridgecv"]
                ix=cols.index(JOB)
                report["coefficient_checks"].append({"fold":fold,"model":name,
                    "standardized_job_coefficient":float(ridge.coef_[ix])})
        for i,(_,row) in enumerate(test.iterrows()):
            result_rows.append({"kommun_kod":row.kommun_kod,"out_share":float(row.commuting),
                "actual":float(row[target]),"fold":fold,**{k:float(v[i]) for k,v in pred.items()}})
        print(f"fold {fold} complete: {len(test)} municipalities",flush=True)
    df=pd.DataFrame(result_rows).sort_values("kommun_kod")
    if len(df)!=290 or df.kommun_kod.nunique()!=290:raise RuntimeError("Incomplete 290 municipality holdout")
    actual=df.actual.to_numpy()
    report["metrics"]={k:metrics(actual,df[k].to_numpy()) for k in ADDITIONS}
    report["quartiles"]=[]
    qs=pd.qcut(df.out_share.rank(method="first"),4,labels=["Q1","Q2","Q3","Q4"])
    for q in ["Q1","Q2","Q3","Q4"]:
        t=df.loc[qs==q]
        report["quartiles"].append({"group":q,"n":len(t),
            "rmse":{k:metrics(t.actual.to_numpy(),t[k].to_numpy())["rmse"] for k in ADDITIONS}})
    report["lulea"]=df.loc[df.kommun_kod=="2580"].to_dict("records")
    rng=np.random.default_rng(20261014)
    report["bootstrap"]={}
    for name in ("employment","small_housing","combined"):
        differences=[]
        for _ in range(2000):
            ix=rng.integers(0,len(df),len(df))
            ref=actual[ix]-df.reference.to_numpy()[ix]
            alternative=actual[ix]-df[name].to_numpy()[ix]
            differences.append(float(np.sqrt(np.mean(ref**2))-np.sqrt(np.mean(alternative**2))))
        report["bootstrap"][name]={"rmse_gain":float(report["metrics"]["reference"]["rmse"]-report["metrics"][name]["rmse"]),
            "ci95":[float(np.quantile(differences,.025)),float(np.quantile(differences,.975))],
            "improved_municipalities":int((abs(actual-df[name].to_numpy())<abs(actual-df.reference.to_numpy())).sum())}
    # Also track model's signed job coefficient under annual temporal validation.
    for year in (2023,2024):
        train=d.loc[d.year<year].copy(); test=d.loc[d.year==year].copy()
        cm=float(train.commuting.mean());jm=float(train[CONTROL].mean())
        for frame in (train,test):
            frame["commute_c"]=frame.commuting-cm
            frame["commute_jobs"]=frame.commute_c*(frame[CONTROL]-jm)
        eligible=[c for c in pool if c in train and train[c].notna().all() and test[c].notna().all()]
        selected=_select_features(train,eligible,target)["selected"]
        cols=list(dict.fromkeys(selected+["commute_c","commute_jobs",JOB,SMALL]))
        model=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
        model.fit(train[cols],train[target])
        report["coefficient_checks"].append({"train_years":sorted(int(z) for z in train.year.unique()),"test_year":year,
            "model":"combined","standardized_job_coefficient":float(model.named_steps["ridgecv"].coef_[cols.index(JOB)])})
    (D/"commuting_two_candidate_geographic_stress.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:round(v["rmse"],4) for k,v in report["metrics"].items()}),flush=True)
if __name__=="__main__": main()
