#!/usr/bin/env python3
"""Inspect already completed nested CV without tuning or rerunning it."""
import json,statistics
from pathlib import Path
D=Path("docs/data")
x=json.loads((D/"neutral_geographic_nested_selection_results.json").read_text(encoding="utf-8"))
out={"status":"diagnostic_only","source":"neutral_geographic_nested_selection_results.json",
"production_changed":False,"branches":{},"alerts":[]}
alphas=x["hyperparameter_grid"]["alpha"]
min_alpha=min(alphas)
for branch,r in x["results"].items():
    baseline=r["models"]["incumbent_retrain"]
    neutral=r["models"]["neutral_from_zero"]
    nf=neutral["folds"]; bf=baseline["folds"]
    wins=sum(n["rmse"]<b["rmse"] for n,b in zip(nf,bf))
    counts=[f["nonzero_features"] for f in nf]
    at_edge=sum(f["alpha"]==min_alpha for f in nf)
    out["branches"][branch]={
       "neutral_candidates":neutral["n_candidates"],"incumbent_candidates":baseline["n_candidates"],
       "neutral_rmse":neutral["rmse"],"incumbent_rmse":baseline["rmse"],
       "percent_change_rmse":100*(neutral["rmse"]/baseline["rmse"]-1),
       "neutral_winning_outer_folds":wins,"outer_fold_count":len(nf),
       "neutral_nonzero_range":[min(counts),max(counts)],
       "neutral_nonzero_mean":statistics.mean(counts),
       "neutral_nonzero_fraction_mean":statistics.mean(counts)/neutral["n_candidates"],
       "alpha_lower_bound_count":at_edge,
       "selection_5_of_5_count":sum(v==5 for v in neutral["selection_frequency_outer_folds"].values()),
       "caution":"Outer CV score is not an unbiased tuning target; freeze next model design before new analysis."}
    if at_edge>=4:out["alerts"].append(branch+": most alpha values are at the weakest regularization boundary")
    if statistics.mean(counts)/neutral["n_candidates"]>.65:out["alerts"].append(branch+": many available features remain active")
out["interpretation"]=[
 "Geographic grouped CV estimates generalization to unseen municipalities, not unseen future years.",
 "Incumbent_retrain is not an exact reconstruction of the production model.",
 "Five-year and three-year arms use different candidate sets and cannot isolate window-length effects.",
 "The historical 2024 outcome was not used in this nested CV.",
 "The next hyperparameter/complexity redesign must be precommitted and tested on a separate evidence base; rerunning many grids to maximize this same observed outer-CV score invites overfitting the evaluation.",
 "No new feature choices or production changes are made by this audit."]
(D/"neutral_nested_cv_overfitting_audit.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"branches":out["branches"],"alerts":out["alerts"]},ensure_ascii=False))
