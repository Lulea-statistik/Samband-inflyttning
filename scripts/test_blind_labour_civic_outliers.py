#!/usr/bin/env python3
"""Research only: outlier sensitivity of blind civic and unemployment signals."""
import hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features, _geographic_error_metrics
from test_commuting_annual_paired import source_data

D=Path("docs/data")
LONG="lag1_kolada_langtidsarbetslosa_pct"
CIVIC="lag1_kolada_utbetalt_lok_stod_kr_per_inv"
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km",
"lag1_inkomst_tkr","lag1_andel_eftergymnasial","lag1_andel_studerande",
"lag1_andel_fa_arbetsplatser_i_egen_kommun","lag1_kolada_arbetslosa_18_65_pct"]
FORMS={"reference":[],"long_term":[LONG],"civic":[CIVIC],"both":[LONG,CIVIC]}
BLOCK=("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")

def fit_predict(train,test,cols,winsor=False):
    a=train[cols].copy();b=test[cols].copy()
    if winsor:
        for c in [LONG,CIVIC]:
            if c in cols:
                lo,hi=train[c].quantile([.025,.975])
                a[c]=a[c].clip(lo,hi);b[c]=b[c].clip(lo,hi)
    model=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
    model.fit(a,train["__target"])
    return model.predict(b)

def main():
    sources,fair,target=source_data();d=sources["BAS"].copy()
    if d[[LONG,CIVIC]+CONTROLS+[target]].isna().any().any():
        raise RuntimeError("Incomplete common comparison sample")
    if d.loc[d.year.eq(2024),"kommun_kod"].nunique()!=290:
        raise RuntimeError("Missing municipalities")
    d["__target"]=d[target]
    pool=[c for c in fair["eligible_pool"] if c not in (LONG,CIVIC) and not any(x in c for x in BLOCK)]
    records=[];fold_info=[]
    ids=sorted(d.loc[d.year.eq(2024),"kommun_kod"].unique())
    for fold in range(5):
        held={c for c in ids if int(hashlib.sha256(("validation-140:"+c).encode()).hexdigest()[:12],16)%5==fold}
        train=d[(d.year<2024)&(~d.kommun_kod.isin(held))].copy()
        test=d[(d.year==2024)&d.kommun_kod.isin(held)].copy()
        eligible=[c for c in pool if c in train and train[c].notna().all() and test[c].notna().all()]
        selected=_select_features(train,eligible,target)["selected"]
        baseline=list(dict.fromkeys(selected+CONTROLS))
        if any(c in baseline for c in (LONG,CIVIC)):raise RuntimeError("Candidate leakage")
        preds={}
        for name,extra in FORMS.items():
            cols=list(dict.fromkeys(baseline+extra))
            preds[name]=fit_predict(train,test,cols)
            preds[name+"_winsor"]=fit_predict(train,test,cols,winsor=True)
        for i,(_,row) in enumerate(test.iterrows()):
            records.append({"code":row.kommun_kod,"fold":fold,"actual":float(row[target]),
                "long":float(row[LONG]),"civic_value":float(row[CIVIC]),
                "population_log":float(row["lag1_log_folkmangd"]),
                **{k:float(v[i]) for k,v in preds.items()}})
        fold_info.append({"fold":fold,"n_test":len(test),"n_features":len(baseline)})
    g=pd.DataFrame(records).sort_values("code").reset_index(drop=True)
    if len(g)!=290 or g.code.nunique()!=290:raise RuntimeError("Incomplete predictions")
    def metric(s):
        return {n:{"rmse":float(np.sqrt(np.mean((s.actual-s[n])**2))),
                   "mae":float(np.mean(np.abs(s.actual-s[n])))} for n in FORMS}
    def gains(s,alt):
        return float(np.sqrt(np.mean((s.actual-s.reference)**2))-
                     np.sqrt(np.mean((s.actual-s[alt])**2)))
    reference_errors=np.abs(g.actual-g.reference)
    sort_indices=np.argsort(reference_errors.to_numpy())
    diagnostics={}
    for trim in [0,1,3,5,10]:
        keep=sort_indices[:len(g)-trim] if trim else sort_indices
        s=g.iloc[keep]
        diagnostics[f"exclude_{trim}_largest_reference_errors"]={"n":len(s),
            "gain":{n:gains(s,n) for n in list(FORMS)[1:]}}
    for field in ("long","civic_value"):
        values=g[field].rank(method="first")
        groups=pd.qcut(values,4,labels=["Q1","Q2","Q3","Q4"])
        diagnostics[field+"_quartiles"]={str(q):{"n":int((groups==q).sum()),
            "gain":{n:gains(g.loc[groups==q],n) for n in list(FORMS)[1:]}} for q in ["Q1","Q2","Q3","Q4"]}
    report={"research_only":True,"demographically_blind":True,"year":2024,"n":290,
        "folds":fold_info,"reference_is_identical_across_comparisons":True,
        "metrics":metric(g),"winsorized_metrics":{
           n:{"rmse":float(np.sqrt(np.mean((g.actual-g[n+"_winsor"])**2))),
              "mae":float(np.mean(abs(g.actual-g[n+"_winsor"])))} for n in FORMS},
        "diagnostics":diagnostics,
        "largest_reference_errors":g.assign(abs_error=reference_errors).nlargest(10,"abs_error")[
           ["code","fold","actual","reference","long_term","civic","both","abs_error"]].to_dict("records"),
        "lulea":g.loc[g.code=="2580",["code","actual","reference","long_term","civic","both",
            "long_term_winsor","civic_winsor","both_winsor"]].to_dict("records"),
        "production_model_changed":False,
        "limitations":["Outlier deletion uses observed reference errors; sensitivity diagnostic, not operational evaluation.",
                       "Train-only candidate winsorization uses 2.5th and 97.5th percentiles of the training sample.",
                       "Years/folds previously inspected; no prospective independent validation.",
                       "Municipal aggregate associations do not demonstrate causality."]}
    (D/"blind_labour_civic_outlier_stress.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"rmse":{k:v["rmse"] for k,v in report["metrics"].items()},
        "winsor_rmse":{k:v["rmse"] for k,v in report["winsorized_metrics"].items()}},indent=2),flush=True)
if __name__=="__main__":main()
