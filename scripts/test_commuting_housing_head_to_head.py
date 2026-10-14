#!/usr/bin/env python3
"""Predeclared housing candidate screening on identical BAS forecast folds.

Existing dynamic commuter-interaction baseline, individually add one candidate.
No new feature selection based on test outcomes or promotion to production.
"""
import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
CONTROL="lag1_andel_fa_arbetsplatser_i_egen_kommun"
CANDIDATES=[
"lag1_smahuspris_medel_tkr",
"lag1_smahuspris_inkomstkvot_median",
"lag1_smahusforsaljningar_per_1000_smahus",
"lag1_andel_bostader_70_max",
"lag1_andel_bostader_151_plus",
"lag1_andel_smahus_151_plus",
]
def main():
    data,fair,target=source_data();d=data["BAS"];pool=list(fair["eligible_pool"])
    report={"status":"housing_candidate_head_to_head","source":"BAS","years":[2023,2024],
      "candidates":CANDIDATES,"omitted_incomplete":"lag1_lediga_allmannytta_pct",
      "selection_train_only":True,"production_model_changed":False,"results":{}}
    for year in [2023,2024]:
        tr=d.loc[d.year<year].copy();te=d.loc[d.year==year].copy()
        if len(te)!=290:raise RuntimeError("Incomplete test")
        cm=float(tr.commuting.mean());jm=float(tr[CONTROL].mean())
        for frame in (tr,te):
            frame["commute_c"]=frame.commuting-cm
            frame["commute_jobs"]=frame.commute_c*(frame[CONTROL]-jm)
        eligible=[x for x in pool if x in tr and tr[x].notna().all() and te[x].notna().all()]
        selected=_select_features(tr,eligible,target)["selected"]
        base=list(dict.fromkeys(selected+["commute_c","commute_jobs"]))
        comparisons={}
        for candidate in [None]+CANDIDATES:
            cols=list(dict.fromkeys(base+([candidate] if candidate else [])))
            if tr[cols].isna().any().any() or te[cols].isna().any().any():
                raise RuntimeError(f"Incomplete candidate: {candidate}")
            m=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            m.fit(tr[cols],tr[target]);pred=m.predict(te[cols])
            err=_geographic_error_metrics(te[target],pred)
            lu=np.flatnonzero(te.kommun_kod.to_numpy()=="2580")
            comparisons[candidate or "reference"]={"rmse":float(err["rmse"]),
                "mae":float(err["mae"]),"lulea_prediction":float(pred[lu[0]]),
                "lulea_actual":float(te.iloc[lu[0]][target]),
                "coefficient":float(m.named_steps["ridgecv"].coef_[cols.index(candidate)]) if candidate else None,
                "feature_count":len(cols)}
        report["results"][str(year)]={"n_train":len(tr),"n_test":len(te),
            "selected_features":selected,"comparisons":comparisons}
        print(json.dumps({"year":year,"rmse":{k:round(v["rmse"],3) for k,v in comparisons.items()}},ensure_ascii=False),flush=True)
    report["limitations"]="2023 and 2024 have been inspected repeatedly; descriptive exploratory comparisons only. No unseen future-year confirmation. Selected baseline includes historical demographics and is not demographically blind."
    (D/"commuting_housing_head_to_head.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
