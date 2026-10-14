#!/usr/bin/env python3
"""Exploratory nested municipal CV selecting complexity via the one-SE rule."""
import hashlib,json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import GroupKFold
from build_analysis import _geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"]
SIZES=[3,5,7,10,14,20]
def ranked(tr,features,target,size):
    allvars=list(dict.fromkeys(CONTROLS+features))
    scaler=StandardScaler().fit(tr[allvars])
    z=scaler.transform(tr[allvars])
    score=Ridge(alpha=50.0).fit(z,tr[target]).coef_
    corr=pd.DataFrame(z,columns=allvars).corr().abs()
    chosen=list(CONTROLS)
    candidates=sorted(range(len(allvars)),key=lambda i:(-abs(score[i]),allvars[i]))
    for i in candidates:
        f=allvars[i]
        if f in chosen:continue
        if any(pd.notna(corr.loc[f,c]) and corr.loc[f,c]>=.90 for c in chosen):continue
        chosen.append(f)
        if len(chosen)>=size:break
    return chosen
def predict(tr,te,features,target,size):
    selected=ranked(tr,features,target,size)
    model=make_pipeline(StandardScaler(),Ridge(alpha=50.0))
    model.fit(tr[selected],tr[target])
    return model.predict(te[selected]),selected
def main():
    sources,fair,target=source_data();data=sources["BAS"]
    audit=json.loads((D/"fair_variable_eligibility_audit.json").read_text(encoding="utf-8"))
    candidates=[v["feature"] for v in audit["features"] if v["complete_sample_2022_2024"] and v["blind_predictor_allowed_by_name"]]
    old=[f for f in fair["incumbent_features"] if f in candidates]
    if len(candidates)!=73 or len(old)!=22:raise RuntimeError("Candidate inventory changed")
    ids=sorted(data.loc[data.year.eq(2024),"kommun_kod"].unique())
    preds=[];outer=[]
    for fold in range(5):
        held={c for c in ids if int(hashlib.sha256(("validation-140:"+c).encode()).hexdigest()[:12],16)%5==fold}
        tr=data[(data.year<2024)&(~data.kommun_kod.isin(held))].copy()
        te=data[(data.year==2024)&data.kommun_kod.isin(held)].copy()
        row={"fold":fold,"n_train":len(tr),"n_test":len(te),"choices":{}}
        output={}
        for label,features in [("original",old),("expanded",candidates)]:
            cv=GroupKFold(n_splits=4)
            records={k:[] for k in SIZES}
            for ai,bi in cv.split(tr,groups=tr.kommun_kod):
                train=tr.iloc[ai];val=tr.iloc[bi]
                for size in SIZES:
                    p,_=predict(train,val,features,target,size)
                    records[size].append(float(np.sqrt(np.mean((val[target].to_numpy()-p)**2))))
            avg={k:float(np.mean(v)) for k,v in records.items()}
            se={k:float(np.std(v,ddof=1)/np.sqrt(len(v))) for k,v in records.items()}
            best=min(SIZES,key=lambda k:avg[k])
            chosen=min(k for k in SIZES if avg[k]<=avg[best]+se[best])
            p,selected=predict(tr,te,features,target,chosen)
            output[label]=p
            row["choices"][label]={"best_mean_size":best,"one_se_size":chosen,"inner_rmse":avg,
                "inner_se":se,"selected":selected}
        for i,(_,ob) in enumerate(te.iterrows()):
            preds.append({"code":ob.kommun_kod,"actual":float(ob[target]),
              **{key:float(val[i]) for key,val in output.items()}})
        outer.append(row)
        print(f"completed outer fold {fold}",flush=True)
    dataout=pd.DataFrame(preds)
    if len(dataout)!=290 or dataout.code.nunique()!=290:raise RuntimeError("Held out municipalities missing")
    report={"status":"exploratory_nested_one_se_size_selection","size_grid":SIZES,
     "outer_groups":5,"inner_groups":4,"fixed_controls":CONTROLS,
     "candidate_counts":{"original":len(old),"expanded":len(candidates)},
     "metrics":{x:_geographic_error_metrics(dataout.actual,dataout[x]) for x in ("original","expanded")},
     "outer_folds":outer,"lulea":dataout.loc[dataout.code=="2580"].to_dict("records"),
     "production_changed":False,"limitations":[
       "The selected complexity and variables use only outer training municipalities; outer test evaluates 2024 only.",
       "2024 and these geographic folds have already been explored, so results are not independent confirmation.",
       "Ridge alpha 50 fixed as an exploratory convention and not separately validated as optimal.",
       "One-SE uses four inner geographic folds; standard error may be unstable and folds are not independent.",
       "Source publication timing, data definition and thematic eligibility still require review."]}
    (D/"fair_blind_nested_one_se.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"rmse":{k:v["rmse"] for k,v in report["metrics"].items()}},ensure_ascii=False))
if __name__=="__main__":main()
