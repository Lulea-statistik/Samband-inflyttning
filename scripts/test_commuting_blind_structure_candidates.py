#!/usr/bin/env python3
"""Demographically blind structural candidate comparison, separate from forecast model.

No lagged migration, population growth, age profile or historical migrant profile.
Retain structural log population, regional geography, housing and labor controls.
"""
import json
from pathlib import Path
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
FORBIDDEN={"lag1_inflyttning_per_1000","lag1_utflyttning_per_1000",
  "lag1_befolkningstillvaxt_pct","lag1_andel_20_34","lag1_inflyttare_medelalder"}
CANDIDATES={"long_term_unemployment":"lag1_kolada_langtidsarbetslosa_pct",
  "natural_land":"lag1_naturpraglad_mark_andel_land_pct",
  "coastal_urban":"lag1_strand_hav_bostader_tatort_per_1000"}
STRUCTURAL=["lag1_log_folkmangd","lag1_tatortsgrad_pct",
  "lag1_regional_centre_distance_km"]
def main():
    sources,fair,target=source_data();d=sources["BAS"]
    pool=[c for c in fair["eligible_pool"] if c not in FORBIDDEN]
    # Controls are fixed and structurally interpretable, not chosen after results.
    pool=list(dict.fromkeys(pool+STRUCTURAL))
    forbidden_fragments=("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")
    if any(any(z in f for z in forbidden_fragments) for f in pool):
        raise RuntimeError("Demographic blind exclusion failed")
    report={"status":"blind_structure_environment_unemployment","regime":"BAS",
      "years":[2023,2024],"no_history_migration_predictors":True,
      "fixed_structural_controls":STRUCTURAL,"candidates":CANDIDATES,
      "production_model_changed":False,"results":{}}
    for year in (2023,2024):
        train=d.loc[d.year<year].copy();test=d.loc[d.year==year].copy()
        available=[c for c in pool if c in train and train[c].notna().all() and test[c].notna().all()]
        controls=[c for c in STRUCTURAL if c in available]
        if len(controls)<2:raise RuntimeError(f"Insufficient structural controls for year {year}: {controls}")
        selected=_select_features(train,available,target)["selected"]
        baseline=list(dict.fromkeys(selected+controls))
        if not baseline:raise RuntimeError("Missing structural feature base")
        comparisons={}
        for name,variable in [("reference",None),*CANDIDATES.items()]:
            cols=list(dict.fromkeys(baseline+([variable] if variable else [])))
            if any(c not in train for c in cols) or train[cols].isna().any().any() or test[cols].isna().any().any():
                raise RuntimeError(f"Missing model inputs {name}")
            fit=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            fit.fit(train[cols],train[target]);pred=fit.predict(test[cols])
            m=_geographic_error_metrics(test[target],pred)
            lx=np.flatnonzero(test.kommun_kod.to_numpy()=="2580")
            comparisons[name]={"rmse":float(m["rmse"]),"mae":float(m["mae"]),
              "already_selected":bool(variable in baseline) if variable else False,
              "feature_count":len(cols),
              "coefficient":float(fit.named_steps["ridgecv"].coef_[cols.index(variable)]) if variable else None,
              "lulea_prediction":float(pred[lx[0]]),"lulea_actual":float(test.iloc[lx[0]][target])}
        report["results"][str(year)]={"n_train":len(train),"n_test":len(test),
            "selected":selected,"actual_controls":controls,"comparisons":comparisons}
        print(json.dumps({"year":year,"rmse":{k:round(v["rmse"],4) for k,v in comparisons.items()}},ensure_ascii=False),flush=True)
    report["limitations"]=["This research uses a BAS-only complete sample and modified pool; not the published full-history structural model.",
     "Already inspected years, no unseen validation.",
     "Municipal-level conditional association is not causal."]
    (D/"commuting_blind_structure_candidates.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
