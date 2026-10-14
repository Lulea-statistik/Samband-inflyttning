#!/usr/bin/env python3
"""Retrospective geographic municipality holdout: nature, coastal housing, long-term unemployment."""
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
CONTROL="lag1_andel_fa_arbetsplatser_i_egen_kommun"
ADDITIONS={"reference":[],"coastal_urban":["lag1_strand_hav_bostader_tatort_per_1000"],
           "natural_land":["lag1_naturpraglad_mark_andel_land_pct"],
           "long_term_unemployment":["lag1_kolada_langtidsarbetslosa_pct"]}
def metric(y,p):
    return _geographic_error_metrics(pd.Series(y),pd.Series(p))
def main():
    sources,fair,target=source_data();d=sources["BAS"];pool=list(fair["eligible_pool"])
    out={"status":"geographic_environment_unemployment_stress","year":2024,
         "train_years":[2022,2023],"candidates":ADDITIONS,
         "design":"five reproducible municipality holdouts, no held municipality in training years",
         "production_model_changed":False,"folds":[]}
    records=[]; ids=sorted(d.loc[d.year.eq(2024)].kommun_kod.unique())
    for fold in range(5):
        held={c for c in ids if int(hashlib.sha256(("validation-140:"+c).encode()).hexdigest()[:12],16)%5==fold}
        tr=d.loc[(d.year<2024)&(~d.kommun_kod.isin(held))].copy()
        te=d.loc[(d.year==2024)&(d.kommun_kod.isin(held))].copy()
        if len(te)<25 or len(tr)<350:raise RuntimeError(f"Fold {fold} incomplete")
        cm=float(tr.commuting.mean()); jm=float(tr[CONTROL].mean())
        for frame in (tr,te):
            frame["commute_c"]=frame.commuting-cm
            frame["commute_jobs"]=frame.commute_c*(frame[CONTROL]-jm)
        eligible=[c for c in pool if c in tr and tr[c].notna().all() and te[c].notna().all()]
        selected=_select_features(tr,eligible,target)["selected"]
        base=list(dict.fromkeys(selected+["commute_c","commute_jobs"]))
        preds={};coefficients={}
        for key,added in ADDITIONS.items():
            cols=list(dict.fromkeys(base+added))
            if tr[cols].isna().any().any() or te[cols].isna().any().any():raise RuntimeError(f"Missing {key}")
            m=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            m.fit(tr[cols],tr[target]);preds[key]=m.predict(te[cols])
            coefficients[key]=float(m.named_steps["ridgecv"].coef_[cols.index(added[0])]) if added else None
        out["folds"].append({"fold":fold,"n_test":len(te),"coefficients":coefficients})
        for i,(_,row) in enumerate(te.iterrows()):
            records.append({"kommun_kod":row.kommun_kod,"actual":float(row[target]),
                "out_share":float(row.commuting),"fold":fold,
                **{key:float(value[i]) for key,value in preds.items()}})
        print(f"completed fold {fold}, {len(te)} municipalities",flush=True)
    df=pd.DataFrame(records).sort_values("kommun_kod")
    if len(df)!=290 or df.kommun_kod.nunique()!=290:raise RuntimeError("Incomplete municipality holdout")
    actual=df.actual.to_numpy()
    out["metrics"]={k:metric(actual,df[k].to_numpy()) for k in ADDITIONS}
    out["quartiles"]=[]
    q=pd.qcut(df.out_share.rank(method="first"),4,labels=["Q1","Q2","Q3","Q4"])
    for label in ["Q1","Q2","Q3","Q4"]:
        subset=df.loc[q==label]
        out["quartiles"].append({"group":label,"n":len(subset),
            "rmse":{k:metric(subset.actual,subset[k])["rmse"] for k in ADDITIONS}})
    out["lulea"]=df.loc[df.kommun_kod=="2580"].to_dict("records")
    rng=np.random.default_rng(20261014);out["bootstrap"]={}
    for name in ADDITIONS:
        if name=="reference":continue
        gains=[];alt=df[name].to_numpy();ref=df.reference.to_numpy()
        for _ in range(2000):
            ix=rng.integers(0,len(df),len(df))
            gains.append(float(np.sqrt(np.mean((actual[ix]-ref[ix])**2))-np.sqrt(np.mean((actual[ix]-alt[ix])**2))))
        out["bootstrap"][name]={"rmse_gain":float(out["metrics"]["reference"]["rmse"]-out["metrics"][name]["rmse"]),
          "ci95":[float(np.quantile(gains,.025)),float(np.quantile(gains,.975))],
          "n_municipalities_improved":int((abs(actual-alt)<abs(actual-ref)).sum())}
    out["limitations"]=["Candidates chosen from repeatedly inspected 2023/2024 data; bootstrap is exploratory, not independent confirmation.",
       "Baseline has lagged demographic variables, so this does not establish structural causal effects.",
       "Same geographic split as prior exploratory tests, not previously untouched geography."]
    (D/"commuting_environment_unemployment_geographic.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
