#!/usr/bin/env python3
"""Research only: capped selection, equal opportunity for old/new variables."""
import hashlib,json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV,ElasticNetCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from build_analysis import _geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
BLOCK=("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"]
CAPS=[6,10,14]
def choose(train,features,target,k):
    features=list(dict.fromkeys(CONTROLS+features))
    z=StandardScaler().fit_transform(train[features])
    cv=list(GroupKFold(n_splits=3).split(z,train[target],groups=train.kommun_kod))
    m=ElasticNetCV(l1_ratio=[.5,.8,1.0],alphas=40,cv=cv,max_iter=10000,random_state=20261014,n_jobs=1)
    m.fit(z,train[target])
    order=sorted(range(len(features)),key=lambda i:(-abs(m.coef_[i]),features[i]))
    # Remove near-redundant members inside training only. No held-out target information is used.
    corr=pd.DataFrame(z,columns=features).corr().abs()
    selected=list(CONTROLS)
    if len(selected)>k: raise RuntimeError("Cap below mandatory controls")
    for i in order:
        c=features[i]
        if c in selected or abs(m.coef_[i])<1e-7:continue
        if any(float(corr.loc[c,chosen])>=.9 for chosen in selected):continue
        selected.append(c)
        if len(selected)>=k:break
    return selected,{"alpha":float(m.alpha_),"nonzero":int(np.sum(abs(m.coef_)>=1e-7))}
def main():
    data,fair,target=source_data()
    bas=data["BAS"]
    audit=json.loads((D/"fair_variable_eligibility_audit.json").read_text(encoding="utf-8"))
    pool=[r["feature"] for r in audit["features"] if r["complete_sample_2022_2024"] and r["blind_predictor_allowed_by_name"]]
    old=[f for f in fair["incumbent_features"] if f in pool]
    if len(pool)!=73 or len(old)!=22 or any(any(b in f for b in BLOCK) for f in pool):
        raise RuntimeError("Unexpected candidate specifications")
    results={}
    ids=sorted(bas.loc[bas.year.eq(2024),"kommun_kod"].unique())
    for cap in CAPS:
        predictions=[];freq={"original":Counter(),"expanded":Counter()};details=[]
        for fold in range(5):
            held={c for c in ids if int(hashlib.sha256(("validation-140:"+c).encode()).hexdigest()[:12],16)%5==fold}
            tr=bas[(bas.year<2024)&~bas.kommun_kod.isin(held)].copy()
            te=bas[(bas.year==2024)&bas.kommun_kod.isin(held)].copy()
            preds={};chosen={}
            for name,features in [("original",old),("expanded",pool)]:
                selected,meta=choose(tr,features,target,cap)
                est=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
                est.fit(tr[selected],tr[target]);preds[name]=est.predict(te[selected])
                chosen[name]=selected;freq[name].update(selected)
            for i,(_,row) in enumerate(te.iterrows()):
                predictions.append({"code":row.kommun_kod,"actual":float(row[target]),
                    **{name:float(v[i]) for name,v in preds.items()}})
            details.append({"fold":fold,"selected":chosen,"n_test":len(te)})
        p=pd.DataFrame(predictions)
        if len(p)!=290 or p.code.nunique()!=290:raise RuntimeError("Incomplete 2024 evaluation")
        results[str(cap)]={"metrics":{n:_geographic_error_metrics(p.actual,p[n]) for n in freq},
             "selection_frequency":{n:dict(v.most_common()) for n,v in freq.items()},
             "lulea":p.loc[p.code=="2580"].to_dict("records"),"folds":details}
        print(cap,{n:round(v["rmse"],3) for n,v in results[str(cap)]["metrics"].items()},flush=True)
    report={"status":"research_only_capped_blind_reselection","caps":CAPS,"controls":CONTROLS,
       "data_years":[2022,2023,2024],"test_year":2024,"n_municipalities":290,
       "candidate_counts":{"original":len(old),"expanded":len(pool)},"results":results,
       "production_changed":False,
       "limitations":["Feature count caps are exploratory and compared on repeatedly inspected 2024; choosing the best cap from this test would overfit.",
         "Coefficient magnitudes after correlated penalized estimation are not causal variable importance.",
         "High correlation threshold is computed on training data only.",
         "Source definitions and actual forecast-time publication remain unverified.",
         "A prespecified independent evaluation is required before model promotion."]}
    (D/"fair_blind_capped_reselection.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
