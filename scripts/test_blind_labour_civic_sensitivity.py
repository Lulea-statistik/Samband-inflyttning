#!/usr/bin/env python3
"""Research-only sensitivity of long-term unemployment and civic LOK support."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
LONG="lag1_kolada_langtidsarbetslosa_pct"
CIVIC="lag1_kolada_utbetalt_lok_stod_kr_per_inv"
BASE=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"]
STRUCTURE=["lag1_inkomst_tkr","lag1_andel_eftergymnasial","lag1_andel_studerande",
"lag1_andel_fa_arbetsplatser_i_egen_kommun","lag1_kolada_arbetslosa_18_65_pct"]
OPTIONS={"reference":[],"long_term":[LONG],"civic":[CIVIC],"both":[LONG,CIVIC]}
BLOCK=("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")
def main():
    sources,fair,target=source_data()
    d=sources["BAS"].copy()
    required=[LONG,CIVIC]+BASE+STRUCTURE
    for field in required:
        if field not in d or d[field].isna().any():
            raise RuntimeError(f"Insufficient identical complete-case data for {field}")
    pool=[f for f in fair["eligible_pool"] if f not in [LONG,CIVIC] and not any(x in f for x in BLOCK)]
    report={"research_only":True,"demographic_blind":True,"candidate_fields":[LONG,CIVIC],
       "fixed_structural_controls":BASE+STRUCTURE,"production_model_changed":False,
       "comparisons":{},"limitations":[
       "Only 2022-2024 complete comparable BAS observations; no valid 5/10-year rolling confirmation.",
       "2023 and 2024 have been repeatedly inspected and are not untouched prospective tests.",
       "Geographic strata are diagnostic; small strata have uncertain error estimates.",
       "LOK support may proxy for municipal wealth, size or civic infrastructure, not causality."]}
    scenarios={}
    scenarios["temporal_2023"]=(d.loc[d.year.eq(2022)].copy(),d.loc[d.year.eq(2023)].copy())
    scenarios["temporal_2024"]=(d.loc[d.year.lt(2024)].copy(),d.loc[d.year.eq(2024)].copy())
    ids=sorted(d.loc[d.year.eq(2024),"kommun_kod"].unique())
    for fold in range(5):
        held={code for code in ids if int(hashlib.sha256(("validation-140:"+code).encode()).hexdigest()[:12],16)%5==fold}
        scenarios[f"geographic_2024_fold_{fold}"]=(
            d.loc[(d.year.lt(2024))&(~d.kommun_kod.isin(held))].copy(),
            d.loc[(d.year.eq(2024))&(d.kommun_kod.isin(held))].copy())
    geographic=[]
    for name,(train,test) in scenarios.items():
        if len(train)<200 or len(test)<25:raise RuntimeError(f"Insufficient split {name}")
        eligible=[f for f in pool if f in train and train[f].notna().all() and test[f].notna().all()]
        selected=_select_features(train,eligible,target)["selected"]
        baseline=list(dict.fromkeys(selected+BASE+STRUCTURE))
        if LONG in baseline or CIVIC in baseline:raise RuntimeError("Candidate leakage")
        preds={}
        for variant,extra in OPTIONS.items():
            columns=list(dict.fromkeys(baseline+extra))
            est=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            est.fit(train[columns],train[target])
            preds[variant]=est.predict(test[columns])
        m={key:_geographic_error_metrics(test[target],pred) for key,pred in preds.items()}
        report["comparisons"][name]={"n_train":len(train),"n_test":len(test),
                                     "selected_features":len(selected),
                                     "metrics":m,
                                     "rmse_gain":{k:float(m["reference"]["rmse"]-m[k]["rmse"]) for k in OPTIONS if k!="reference"}}
        if name.startswith("geographic"):
            for i,(_,ob) in enumerate(test.iterrows()):
                geographic.append({"code":ob.kommun_kod,"actual":float(ob[target]),
                    "pop":float(ob["lag1_log_folkmangd"]),
                    "urban":float(ob["lag1_tatortsgrad_pct"]),
                    "distance":float(ob["lag1_regional_centre_distance_km"]),
                    **{k:float(v[i]) for k,v in preds.items()}})
        print(name,"complete",flush=True)
    g=pd.DataFrame(geographic)
    if len(g)!=290 or g.code.nunique()!=290:raise RuntimeError("Missing geographic observations")
    report["geographic_2024_pooled"]={k:_geographic_error_metrics(g.actual,g[k]) for k in OPTIONS}
    report["geographic_strata"]={}
    for attribute in ("pop","urban","distance"):
        q=pd.qcut(g[attribute].rank(method="first"),4,labels=["Q1","Q2","Q3","Q4"])
        report["geographic_strata"][attribute]={}
        for quartile in ("Q1","Q2","Q3","Q4"):
            t=g.loc[q==quartile]
            report["geographic_strata"][attribute][quartile]={
                "n":len(t),"rmse_gain":{k:float(_geographic_error_metrics(t.actual,t.reference)["rmse"]-
                      _geographic_error_metrics(t.actual,t[k])["rmse"]) for k in OPTIONS if k!="reference"}}
    report["lulea"]=g.loc[g.code=="2580"].to_dict("records")
    (D/"blind_labour_civic_sensitivity.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
