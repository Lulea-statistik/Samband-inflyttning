#!/usr/bin/env python3
"""Predefined two-variable follow-up for commuting challenger.
Research only: observed 2023/24 previously used to choose these candidates.
Use the same sample and train-only baseline feature selection. No production edits.
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
D=Path("docs/data")
JOB="lag1_sysselsatta_bostad_forandring_pct"
SMALL="lag1_andel_bostader_70_max"
CONTROL="lag1_andel_fa_arbetsplatser_i_egen_kommun"
FORMS={"reference":[],"employment":[JOB],"small_housing":[SMALL],"employment_and_small_housing":[JOB,SMALL]}
def main():
    sources,fair,target=source_data()
    d=sources["BAS"];pool=list(fair["eligible_pool"])
    report={"status":"exploratory_two_candidate_stability","candidates":[JOB,SMALL],
      "years":[2023,2024],"production_model_changed":False,"data_source":"BAS",
      "warning":"Both candidates selected after looking at historical outcomes. This is NOT independent validation.","results":{}}
    for year in [2023,2024]:
        tr=d.loc[d.year<year].copy();te=d.loc[d.year==year].copy()
        cm=float(tr.commuting.mean());jm=float(tr[CONTROL].mean())
        for frame in (tr,te):
            frame["commute_c"]=frame.commuting-cm
            frame["commute_jobs"]=frame.commute_c*(frame[CONTROL]-jm)
        allowed=[c for c in pool if c in tr and tr[c].notna().all() and te[c].notna().all()]
        selected=_select_features(tr,allowed,target)["selected"]
        base=list(dict.fromkeys(selected+["commute_c","commute_jobs"]))
        preds={};scores={}
        for name,extras in FORMS.items():
            features=list(dict.fromkeys(base+extras))
            est=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            est.fit(tr[features],tr[target]);p=est.predict(te[features])
            preds[name]=p;scores[name]=_geographic_error_metrics(te[target],p)
        groups=pd.qcut(te.commuting.rank(method="first"),4,labels=["Q1","Q2","Q3","Q4"])
        quartiles=[]
        for g in ["Q1","Q2","Q3","Q4"]:
            ix=(groups==g).to_numpy()
            quartiles.append({"group":g,"n":int(ix.sum()),
              "rmse":{name:_geographic_error_metrics(te[target].to_numpy()[ix],p[ix])["rmse"] for name,p in preds.items()}})
        pos=np.flatnonzero(te.kommun_kod.to_numpy()=="2580")
        report["results"][str(year)]={"train_years":sorted(int(y) for y in tr.year.unique()),
          "n_train":len(tr),"n_test":len(te),"metrics":scores,"quartiles":quartiles,
          "lulea":[{"actual":float(te.iloc[i][target]),**{name:float(p[i]) for name,p in preds.items()}} for i in pos]}
        print(json.dumps({"year":year,"rmse":{k:round(v["rmse"],4) for k,v in scores.items()}},ensure_ascii=False),flush=True)
    (D/"commuting_two_candidate_stability.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
