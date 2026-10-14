#!/usr/bin/env python3
"""Post-hoc diagnostic of nested 1-SE selection, research-only and no refitting."""
import json
from collections import Counter
from pathlib import Path
import numpy as np
D=Path("docs/data")
def main():
    src=json.loads((D/"fair_blind_nested_one_se.json").read_text(encoding="utf-8"))
    caps=src["size_grid"]
    report={"status":"nested_model_size_diagnostic","production_changed":False,"size_grid":caps,
            "pools":{},"cautions":["The test year 2024 was inspected repeatedly; this is diagnostic, not new independent validation.",
            "Inner-fold standard errors from only four folds may understate or overstate uncertainty.",
            "A boundary optimum at the maximum grid size means the test does not identify a true optimum.",
            "Candidate pool source definitions, dates, and thematic grouping still require scientific review."]}
    for pool in ("original","expanded"):
        records=[f["choices"][pool] for f in src["outer_folds"]]
        frequencies=Counter(x["one_se_size"] for x in records)
        best_freq=Counter(x["best_mean_size"] for x in records)
        selected=Counter(f for x in records for f in x["selected"])
        names=[set(x["selected"]) for x in records]
        jaccards=[]
        for i in range(len(names)):
            for j in range(i+1,len(names)):
                jaccards.append(len(names[i]&names[j])/len(names[i]|names[j]))
        report["pools"][pool]={
            "rmse":src["metrics"][pool]["rmse"],
            "mae":src["metrics"][pool]["mae"],
            "size_frequencies":dict(sorted(frequencies.items())),
            "best_size_frequencies":dict(sorted(best_freq.items())),
            "at_upper_boundary_one_se":int(frequencies[max(caps)]),
            "at_upper_boundary_best":int(best_freq[max(caps)]),
            "median_size":float(np.median([x["one_se_size"] for x in records])),
            "average_pairwise_selection_jaccard":float(np.mean(jaccards)),
            "selected_all_folds":[k for k,v in selected.items() if v==len(records)],
            "selected_frequency":dict(selected.most_common()),
            "lulea":src["lulea"][0][pool],
            "lulea_abs_error":abs(src["lulea"][0][pool]-src["lulea"][0]["actual"])
        }
    report["comparison"]={
       "rmse_expanded_minus_original":report["pools"]["expanded"]["rmse"]-report["pools"]["original"]["rmse"],
       "lulea_error_expanded_minus_original":report["pools"]["expanded"]["lulea_abs_error"]-report["pools"]["original"]["lulea_abs_error"],
       "independent_confirmation":False,
       "recommended_next_stage":"Prespecify theme-balanced selection and evaluate changes to complexity using inner train-only validation. Audit source timing before independent confirmation."
    }
    (D/"fair_blind_nested_one_se_diagnostic.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:{"median":v["median_size"],"boundary":v["at_upper_boundary_one_se"],"jaccard":v["average_pairwise_selection_jaccard"]} for k,v in report["pools"].items()},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
