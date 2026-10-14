#!/usr/bin/env python3
"""Exploratory train-only thematic ablation and paired incumbent substitution."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"]
def fit(tr,te,target,features):
    m=make_pipeline(StandardScaler(),Ridge(alpha=50))
    m.fit(tr[features],tr[target])
    return m.predict(te[features])
def main():
    sources,fair,target=source_data()
    data=sources["BAS"]
    previous=json.loads((D/"fair_blind_theme_balanced_test.json").read_text(encoding="utf-8"))
    themes=json.loads((D/"fair_variable_thematic_register.json").read_text(encoding="utf-8"))
    assignment={r["feature"]:r["theme"] for r in themes["records"]}
    rows=[];fold_reports=[]
    ids=sorted(data.loc[data.year.eq(2024),"kommun_kod"].unique())
    for record in previous["folds"]:
        fold=record["fold"]
        held={c for c in ids if int(hashlib.sha256(("validation-140:"+c).encode()).hexdigest()[:12],16)%5==fold}
        train=data.loc[(data.year<2024)&(~data.kommun_kod.isin(held))].copy()
        test=data.loc[(data.year==2024)&data.kommun_kod.isin(held)].copy()
        if len(test)!=record["n_test"]:raise RuntimeError("Held municipality mismatch")
        selection=record["models"]["expanded"]["selected"]
        if not set(CONTROLS).issubset(selection):raise RuntimeError("Missing fixed controls")
        ref=fit(train,test,target,selection)
        actions={}
        for col in selection:
            if col in CONTROLS:continue
            group=assignment[col]
            without=[f for f in selection if f!=col]
            alt=fit(train,test,target,without)
            actions["drop_"+group]=alt
            # Fair within-theme replacement: choose the old incumbent with strongest
            # absolute training-only partial fit, not the best held-out outcome.
            incumbents=[c for c in fair["incumbent_features"] if c in assignment and assignment[c]==group
                        and c not in selection]
            if incumbents:
                base_model=make_pipeline(StandardScaler(),Ridge(alpha=50))
                base_model.fit(train[without],train[target])
                residual=train[target].to_numpy()-base_model.predict(train[without])
                scored=[]
                for c in incumbents:
                    z=train[c].to_numpy(dtype=float);std=float(z.std())
                    if std>1e-12:
                        score=abs(float(np.corrcoef(z,residual)[0,1]))
                        if np.isfinite(score):scored.append((score,c))
                if scored:
                    substitute=sorted(scored,key=lambda x:(-x[0],x[1]))[0][1]
                    actions["replace_"+group]=fit(train,test,target,without+[substitute])
        fold_reports.append({"fold":fold,"n_test":len(test),"selected":selection,
            "ablation_groups":[k.removeprefix("drop_") for k in actions if k.startswith("drop_")],
            "replacement_groups":[k.removeprefix("replace_") for k in actions if k.startswith("replace_")]})
        for i,(_,r) in enumerate(test.iterrows()):
            item={"code":r.kommun_kod,"fold":fold,"actual":float(r[target]),"reference":float(ref[i])}
            item.update({key:float(p[i]) for key,p in actions.items()})
            rows.append(item)
        print("fold",fold,"done",flush=True)
    predictions=pd.DataFrame(rows)
    if len(predictions)!=290 or predictions.code.nunique()!=290:raise RuntimeError("Sample mismatch")
    diagnostics={}
    for kind in ("drop_","replace_"):
        groups=sorted({c[len(kind):] for c in predictions if c.startswith(kind)})
        for group in groups:
            col=kind+group
            subset=predictions.loc[predictions[col].notna()]
            if subset.empty:continue
            ref=_geographic_error_metrics(subset.actual,subset.reference)
            candidate=_geographic_error_metrics(subset.actual,subset[col])
            diagnostics[col]={"n_municipalities":len(subset),
                "rmse_reference_same_rows":ref["rmse"],"rmse_alternative":candidate["rmse"],
                "rmse_change_alternative_minus_reference":candidate["rmse"]-ref["rmse"],
                "n_folds":int(subset.fold.nunique())}
    report={"status":"exploratory_theme_ablations_replacements","production_changed":False,
        "reference":_geographic_error_metrics(predictions.actual,predictions.reference),
        "comparisons":diagnostics,"folds":fold_reports,
        "limitations":[
        "No re-selection after ablation; comparisons evaluate contributions conditional on selected features.",
        "The selected model and 2024 folds come from earlier exploratory research, not an independent confirmation.",
        "Subset sample sizes differ because a theme can be absent in some folds: compare only matching-row errors.",
        "Replacement choices are ranked using training-only residual association and not a full nested refit.",
        "Source publication timing and thematic assignments need scientific audit before production."]}
    (D/"fair_blind_theme_ablation_replacement.json").write_text(
      json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"reference_rmse":report["reference"]["rmse"],"comparisons":len(diagnostics)},ensure_ascii=False))
if __name__=="__main__":main()
