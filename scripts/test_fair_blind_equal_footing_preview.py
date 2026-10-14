#!/usr/bin/env python3
"""Research preview: equal-footing blind selection; no production changes."""
import hashlib,json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import ElasticNetCV,RidgeCV
from sklearn.pipeline import make_pipeline
from build_analysis import _geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
FORBIDDEN=("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"]
def select_train_only(d,variables,target):
    x=d[variables].to_numpy(dtype=float)
    scaler=StandardScaler().fit(x)
    z=scaler.transform(x)
    split=list(GroupKFold(n_splits=3).split(z,d[target],groups=d.kommun_kod))
    model=ElasticNetCV(l1_ratio=[.3,.5,.7,.9,1.0],alphas=25,cv=split,max_iter=8000,
                       random_state=20261014,n_jobs=1)
    model.fit(z,d[target].to_numpy(dtype=float))
    chosen=[v for v,coef in zip(variables,model.coef_) if abs(coef)>1e-7]
    return chosen,{"alpha":float(model.alpha_),"l1_ratio":float(model.l1_ratio_)}
def main():
    sources,fair,target=source_data()
    data=sources["BAS"]
    audit=json.loads((D/"fair_variable_eligibility_audit.json").read_text(encoding="utf-8"))
    pool=[f["feature"] for f in audit["features"] if f["complete_sample_2022_2024"] and f["blind_predictor_allowed_by_name"]]
    incumbent=[f for f in fair["incumbent_features"] if f in pool]
    for controls in CONTROLS:
        if controls not in pool:raise RuntimeError(f"Required control unavailable {controls}")
    if any(any(b in f for b in FORBIDDEN) for f in pool):raise RuntimeError("Blind eligibility failure")
    if len(pool)!=73:raise RuntimeError(f"Unexpected technical pool size {len(pool)}")
    ids=sorted(data.loc[data.year.eq(2024),"kommun_kod"].unique())
    all_predictions=[];selected_counts={"original_pool":Counter(),"equal_footing_pool":Counter()};folds=[]
    for fold in range(5):
        held={code for code in ids if int(hashlib.sha256(("validation-140:"+code).encode()).hexdigest()[:12],16)%5==fold}
        train=data[(data.year<2024)&(~data.kommun_kod.isin(held))].copy()
        test=data[(data.year==2024)&data.kommun_kod.isin(held)].copy()
        predictions={};selection={}
        for label,candidates in [("original_pool",incumbent),("equal_footing_pool",pool)]:
            selected,selection_meta=select_train_only(train,candidates,target)
            chosen=list(dict.fromkeys(CONTROLS+selected))
            selected_counts[label].update(selected)
            estimator=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            estimator.fit(train[chosen],train[target])
            predictions[label]=estimator.predict(test[chosen])
            selection[label]={"n_candidates":len(candidates),"n_selected":len(selected),
              "selected":selected,"inner_cv":selection_meta}
        for i,(_,row) in enumerate(test.iterrows()):
            all_predictions.append({"code":row.kommun_kod,"actual":float(row[target]),
                **{k:float(v[i]) for k,v in predictions.items()}})
        folds.append({"fold":fold,"n_train":len(train),"n_test":len(test),"selection":selection})
        print(f"fold {fold}: {len(test)} municipalities",flush=True)
    pred=pd.DataFrame(all_predictions)
    if len(pred)!=290 or pred.code.nunique()!=290:raise RuntimeError("Holdout coverage invalid")
    metrics={name:_geographic_error_metrics(pred.actual,pred[name]) for name in selected_counts}
    report={"status":"exploratory_equal_footing_blind_reselection","year":2024,"train_years":[2022,2023],
       "n_test_municipalities":290,"original_candidates":len(incumbent),"new_pool_candidates":len(pool),
       "mandatory_controls":CONTROLS,"metrics":metrics,
       "selected_frequency":{name:dict(counts.most_common()) for name,counts in selected_counts.items()},
       "folds":folds,"lulea":pred.loc[pred.code=="2580"].to_dict("records"),
       "production_changed":False,
       "limitations":["Both pools use identical train-only elastic-net selection and ridge refitting, not the legacy production selection routine.",
          "Screen is technical only: definition, source release timing and causal validity not verified.",
          "Existing 2024 test and geographic folds already inspected; not independent confirmation.",
          "No automatic production change or interpretation of individual selection as causal influence."]}
    (D/"fair_blind_equal_footing_preview.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"rmse":{k:v["rmse"] for k,v in metrics.items()}},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
