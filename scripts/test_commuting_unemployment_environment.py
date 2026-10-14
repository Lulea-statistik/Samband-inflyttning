#!/usr/bin/env python3
"""Fair exploratory tests of unemployment and environment candidate indicators.

Unemployment variables already in eligible pool: force-inclusion versus selected
baseline, not duplicate addition. Baseline is dynamic with commuting interaction.
Research only; no production modification.
"""
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
CONTROL="lag1_andel_fa_arbetsplatser_i_egen_kommun"
CANDIDATES={t:THEMES[t] for t in ("unemployment","shore_nature")}
def main():
    sources,fair,target=source_data();d=sources["BAS"];pool=list(fair["eligible_pool"])
    report={"status":"unemployment_environment_single_candidate","source":"BAS",
            "years":[2023,2024],"candidate_themes":CANDIDATES,
            "same_sample":True,"production_model_changed":False,"results":{}}
    for year in [2023,2024]:
        tr=d.loc[d.year<year].copy();te=d.loc[d.year==year].copy()
        cm=float(tr.commuting.mean());jm=float(tr[CONTROL].mean())
        for frame in (tr,te):
            frame["commute_c"]=frame.commuting-cm
            frame["commute_jobs"]=frame.commute_c*(frame[CONTROL]-jm)
        eligible=[c for c in pool if c in tr and tr[c].notna().all() and te[c].notna().all()]
        selected=_select_features(tr,eligible,target)["selected"]
        base=list(dict.fromkeys(selected+["commute_c","commute_jobs"]))
        comparisons={}
        for theme,candidates in [("reference",[None]),*CANDIDATES.items()]:
            for feature in candidates:
                cols=list(dict.fromkeys(base+([feature] if feature else [])))
                if tr[cols].isna().any().any() or te[cols].isna().any().any():
                    raise RuntimeError(f"Missing values {feature}")
                fit=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
                fit.fit(tr[cols],tr[target]);pred=fit.predict(te[cols])
                m=_geographic_error_metrics(te[target],pred)
                ix=np.flatnonzero(te.kommun_kod.to_numpy()=="2580")
                comparisons[feature or "reference"]={
                    "theme":theme,"already_in_selected":bool(feature in base) if feature else False,
                    "added_feature":bool(feature and feature not in base),
                    "rmse":float(m["rmse"]),"mae":float(m["mae"]),
                    "lulea_prediction":float(pred[ix[0]]),"lulea_actual":float(te.iloc[ix[0]][target]),
                    "standardized_coefficient":float(fit.named_steps["ridgecv"].coef_[cols.index(feature)]) if feature else None}
        report["results"][str(year)]={"n_train":len(tr),"n_test":len(te),"selected":selected,"comparisons":comparisons}
        print(json.dumps({"year":year,"rmse":{k:round(v["rmse"],3) for k,v in comparisons.items()}},ensure_ascii=False),flush=True)
    report["limitations"]=["The modern dynamically selected baseline includes lagged migration outcomes (not a demographically blind structural model).",
       "For unemployment variables already eligible, this tests forced inclusion if not selected, not independent new candidate discovery.",
       "2023/24 have been repeatedly inspected: exploratory, no independent validation."]
    (D/"commuting_unemployment_environment_screen.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
