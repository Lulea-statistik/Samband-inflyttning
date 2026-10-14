#!/usr/bin/env python3
"""Research-only civic associations candidate test in demographically blind BAS structure model."""
import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data
from audit_commuting_theme_candidates import THEMES
D=Path("docs/data")
FORBIDDEN={"lag1_inflyttning_per_1000","lag1_utflyttning_per_1000","lag1_befolkningstillvaxt_pct","lag1_andel_20_34","lag1_inflyttare_medelalder"}
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"]
CIVIC=THEMES["civic_associations"]
def main():
    sources,fair,target=source_data();d=sources["BAS"]
    pool=list(dict.fromkeys([x for x in fair["eligible_pool"] if x not in FORBIDDEN]+CONTROLS))
    if any(any(z in x for z in ("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")) for x in pool):
        raise RuntimeError("Historical demographics leaked")
    out={"status":"blind_civic_individual_screen","source":"BAS","candidates":CIVIC,
      "years":[2023,2024],"production_model_changed":False,"results":{}}
    for year in (2023,2024):
        tr=d.loc[d.year<year].copy();te=d.loc[d.year==year].copy()
        eligible=[c for c in pool if c in tr and tr[c].notna().all() and te[c].notna().all()]
        missing=[c for c in CONTROLS if c not in eligible]
        if missing:raise RuntimeError(f"Missing controls {missing}")
        selected=_select_features(tr,eligible,target)["selected"]
        baseline=list(dict.fromkeys(selected+CONTROLS))
        comparisons={}
        for key,extra in [("reference",[]),*[(c,[c]) for c in CIVIC],("all_civic",CIVIC)]:
            cols=list(dict.fromkeys(baseline+extra))
            if tr[cols].isna().any().any() or te[cols].isna().any().any():raise RuntimeError(f"Missing candidate {key}")
            m=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            m.fit(tr[cols],tr[target]);pred=m.predict(te[cols])
            v=_geographic_error_metrics(te[target],pred);ix=np.flatnonzero(te.kommun_kod.to_numpy()=="2580")
            comparisons[key]={"rmse":float(v["rmse"]),"mae":float(v["mae"]),"feature_count":len(cols),
                "lulea_pred":float(pred[ix[0]]),"lulea_actual":float(te.iloc[ix[0]][target]),
                "candidate_coefficients":{c:float(m.named_steps["ridgecv"].coef_[cols.index(c)]) for c in extra}}
        out["results"][str(year)]={"selected":selected,"n_train":len(tr),"n_test":len(te),"comparisons":comparisons}
        print(json.dumps({"year":year,"rmse":{k:round(v["rmse"],3) for k,v in comparisons.items()}},ensure_ascii=False),flush=True)
    out["limitations"]=["Previously inspected annual outcomes: descriptive exploratory testing only.",
      "This is a BAS 2022-24 blind candidate research subset, not a full historical structural validation.",
      "Civic associations and support payments are not experimentally assigned; associations cannot establish causality."]
    (D/"commuting_blind_civic_candidate_test.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
