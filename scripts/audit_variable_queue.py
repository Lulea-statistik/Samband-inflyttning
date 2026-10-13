#!/usr/bin/env python3
"""Coverage and source inventory for prospective migration candidates.

Diagnostic only. No new variables or production promotion from this script.
"""
import json
from pathlib import Path
import pandas as pd

OUT = Path("docs/data/variable_queue_status.json")
PANEL = Path("docs/data/panel.csv")
CANDIDATES = {
    "regional_jobs": ["lag1_log_externa_fa_jobb_per_1000", "lag1_andel_fa_arbetsplatser_i_egen_kommun"],
    "employment_dynamics": ["lag1_sysselsatta_arbetsstalle_forandring_pct", "lag1_sysselsatta_bostad_forandring_pct",
                            "lag1_sysselsatta_arbetsstalle_sasongsvariation_pct", "lag1_sysselsatta_bostad_sasongsvariation_pct"],
    "housing_turnover": ["lag1_smahusforsaljningar_per_1000_smahus", "lag1_lediga_allmannytta_pct"],
}
NEW_SOURCES = {
    "commuting_flows": "SCB kommunala pendlingsmatriser; no verified ingested panel series",
    "travel_time_access": "Route-network / GTFS transport data; no verified ingested panel series",
    "parent_education": "SCB/other municipality data; availability and comparability unverified",
}

def main():
    p = pd.read_csv(PANEL, low_memory=False)
    years = sorted(int(v) for v in p.year.dropna().unique())
    output = {"status":"coverage_inventory_only", "years":years,
              "note":"Coverage is not evidence of predictive value. Existing model's candidate tests are separate.",
              "existing":{}, "requires_source":NEW_SOURCES, "production_model_modified":False}
    for group, names in CANDIDATES.items():
        output["existing"][group] = {}
        for name in names:
            if name not in p:
                output["existing"][group][name] = {"in_panel":False}
                continue
            rows=[]
            for year, d in p.groupby("year"):
                coverage = int(d[name].notna().sum())
                rows.append({"year":int(year), "n_nonmissing":coverage, "n_total":int(len(d)), "coverage":round(coverage / len(d), 4)})
            output["existing"][group][name] = {"in_panel":True,"yearly_coverage":rows}
    OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":output["status"],"groups":list(output["existing"])},ensure_ascii=False))
if __name__ == "__main__":
    main()
