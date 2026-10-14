#!/usr/bin/env python3
"""Exploratory theme-balanced incumbent-vs-expanded reselection with nested municipality CV."""
import hashlib,json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from build_analysis import _geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"]
SIZES=[3,5,7,9,11]
def rank_by_theme(train,pool,theme_of,target,size):
    cols=list(dict.fromkeys(CONTROLS+pool))
    z=StandardScaler().fit_transform(train[cols])
    coefficients=Ridge(alpha=50).fit(z,train[target]).coef_
    # Only training coefficients used. One non-control variable per reviewed theme for diagnostics.
    candidate=sorted(((abs(float(coef)),col) for col,coef in zip(cols,coefficients) if col not in CONTROLS),
        key=lambda v:(-v[0],v[1]))
    chosen=list(CONTROLS);themes=set()
    for _,col in candidate:
        theme=theme_of[col]
        if theme in themes:continue
        chosen.append(col);themes.add(theme)
        if len(chosen)>=size:break
    return chosen
def estimate(tr,te,pool,theme_of,target,size):
    chosen=rank_by_theme(tr,pool,theme_of,target,size)
    model=make_pipeline(StandardScaler(),Ridge(alpha=50.0))
    model.fit(tr[chosen],tr[target])
    return model.predict(te[chosen]),chosen
def main():
    sources,fair,target=source_data()
    data=sources["BAS"]
    register=json.loads((D/"fair_variable_thematic_register.json").read_text(encoding="utf-8"))
    theme_of={r["feature"]:r["theme"] for r in register["records"]}
    old=[f for f in fair["incumbent_features"] if f in theme_of]
    expanded=list(theme_of)
    if len(old)!=22 or len(expanded)!=73:raise RuntimeError("Unexpected pools")
    predictions=[];folds=[];counts={"old":Counter(),"expanded":Counter()}
    municipalities=sorted(data.loc[data.year.eq(2024),"kommun_kod"].unique())
    for fold in range(5):
        held={c for c in municipalities if int(hashlib.sha256(("validation-140:"+c).encode()).hexdigest()[:12],16)%5==fold}
        train=data.loc[(data.year<2024)&(~data.kommun_kod.isin(held))].copy()
        test=data.loc[(data.year==2024)&data.kommun_kod.isin(held)].copy()
        output={};detail={}
        for label,pool in (("old",old),("expanded",expanded)):
            scores={size:[] for size in SIZES}
            split=GroupKFold(n_splits=4)
            for itr,ival in split.split(train,groups=train.kommun_kod):
                tr=train.iloc[itr];val=train.iloc[ival]
                for size in SIZES:
                    pred,_=estimate(tr,val,pool,theme_of,target,size)
                    scores[size].append(float(np.sqrt(np.mean((val[target].to_numpy()-pred)**2))))
            means={s:float(np.mean(v)) for s,v in scores.items()}
            errors={s:float(np.std(v,ddof=1)/np.sqrt(len(v))) for s,v in scores.items()}
            best=min(SIZES,key=lambda s:means[s])
            selected_size=min(s for s in SIZES if means[s]<=means[best]+errors[best])
            pred,selected=estimate(train,test,pool,theme_of,target,selected_size)
            output[label]=pred
            counts[label].update(selected)
            detail[label]={"best_size":best,"one_se_size":selected_size,
                           "inner_rmse":means,"inner_standard_error":errors,"selected":selected}
        for i,(_,row) in enumerate(test.iterrows()):
            predictions.append({"code":row.kommun_kod,"actual":float(row[target]),
                **{label:float(p[i]) for label,p in output.items()}})
        folds.append({"fold":fold,"n_test":len(test),"models":detail})
        print("fold",fold,"complete",flush=True)
    p=pd.DataFrame(predictions)
    if len(p)!=290 or p.code.nunique()!=290:raise RuntimeError("Incomplete geographic evaluation")
    report={"status":"exploratory_theme_balanced_equal_footing","years":[2022,2023,2024],
      "theme_policy":"one non-control variable per heuristic theme; controls always retained",
      "size_grid":SIZES,"candidate_counts":{"old":len(old),"expanded":len(expanded)},
      "metrics":{label:_geographic_error_metrics(p.actual,p[label]) for label in counts},
      "selection_frequency":{label:dict(v.most_common()) for label,v in counts.items()},
      "folds":folds,"lulea":p.loc[p.code=="2580"].to_dict("records"),
      "production_changed":False,"limitations":[
        "Heuristic theme assignments require scientific review; a strict one-per-theme restriction may exclude useful independent signals.",
        "All 2024 test geography repeatedly inspected: this is exploratory and does not validate production.",
        "Theme selection uses training-only standardized ridge coefficients, a proxy ranking rather than exhaustive group substitution.",
        "Source publication timing and definitional harmonization not yet verified.",
        "Fixed ridge alpha, four inner folds and the candidate size grid are methodological simplifications."]}
    (D/"fair_blind_theme_balanced_test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v["rmse"] for k,v in report["metrics"].items()}),flush=True)
if __name__=="__main__":main()
