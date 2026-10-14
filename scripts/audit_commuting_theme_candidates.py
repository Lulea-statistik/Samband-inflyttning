#!/usr/bin/env python3
"""Audit underrepresented preplanned themes against existing dynamic pool and BAS panel.
No model fitting; intended to guard subsequent fair feature trials.
"""
import json
from pathlib import Path
import pandas as pd
from test_commuting_annual_paired import source_data

D=Path("docs/data")
THEMES={
 "civic_associations":["lag1_kolada_lok_foreningar_per_10000","lag1_kolada_flickdominerade_idrottsforeningar_andel","lag1_kolada_utbetalt_lok_stod_kr_per_inv"],
 "labor_dynamics":["lag1_sysselsatta_arbetsstalle_forandring_pct","lag1_sysselsatta_bostad_forandring_pct","lag1_sysselsatta_arbetsstalle_sasongsvariation_pct","lag1_sysselsatta_bostad_sasongsvariation_pct"],
 "unemployment":["lag1_kolada_langtidsarbetslosa_pct","lag1_kolada_arbetslosa_18_24_pct"],
 "housing_market":["lag1_smahuspris_medel_tkr","lag1_smahuspris_inkomstkvot_median","lag1_lediga_allmannytta_pct","lag1_smahusforsaljningar_per_1000_smahus"],
 "housing_sizes":["lag1_andel_bostader_70_max","lag1_andel_bostader_151_plus","lag1_andel_smahus_151_plus"],
 "shore_nature":["lag1_skogsmark_andel_land_pct","lag1_naturpraglad_mark_andel_land_pct","lag1_strand_hav_bostader_per_1000","lag1_strand_hav_bostader_tatort_per_1000"]
}
def main():
    sources,fair,target=source_data()
    d=sources["BAS"]
    pool=set(fair["eligible_pool"])
    base=set(fair["incumbent_features"])
    report={"status":"candidate_theme_coverage_audit","test_regime":"BAS lagged 2022-2024","years":[2022,2023,2024],"n_per_year":290,
            "themes":{},"production_model_changed":False}
    for theme,features in THEMES.items():
        rows=[]
        for feature in features:
            coverage={str(y):int(d.loc[d.year==y,feature].notna().sum()) if feature in d.columns else 0 for y in (2022,2023,2024)}
            rows.append({"feature":feature,"in_existing_pool":feature in pool,
                         "in_incumbent":feature in base,"present_in_panel":feature in d.columns,
                         "coverage":coverage,"complete_2022_2024":all(v==290 for v in coverage.values())})
        report["themes"][theme]=rows
    (D/"commuting_theme_candidate_coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"complete":{t:[x["feature"] for x in items if x["complete_2022_2024"]] for t,items in report["themes"].items()}},ensure_ascii=False))
if __name__=="__main__":main()
