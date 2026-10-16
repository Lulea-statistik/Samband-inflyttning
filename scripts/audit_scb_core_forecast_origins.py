#!/usr/bin/env python3
"""Non-predictive SCB source-origin gate for corrected 3-year forecast core.

Records official publication anchors and distinguishes them from exact historical
PxWeb table-vintage certification. No model is fitted.
"""
import json
from pathlib import Path

D=Path("docs/data")

sources={
 "migration":{
   "feature":["lag1_inflyttning_per_1000","lag1_utflyttning_per_1000"],
   "table_id":"BE0101J/Flyttningar97",
   "reference_year":2023,
   "official_anchor_date":"2024-03-22",
   "anchor_type":"SCB statistics-news release with additional 2023 population/migration statistics",
   "exact_historical_table_vintage_certified":False,
   "notes":"Current Statistics Database table identity is confirmed, but the first exact municipal Flyttningar97 vintage containing 2023 values has not been independently archived/certified."
 },
 "population_denominator":{
   "feature":["lag1_inflyttning_per_1000","lag1_utflyttning_per_1000"],
   "table_id":"BE0101A/BefolkningNy",
   "reference_year":2023,
   "official_anchor_date":"2024-02-22",
   "anchor_type":"SCB full-year 2023 population release",
   "exact_historical_table_vintage_certified":False,
   "notes":"Full-year 2023 population was officially released 2024-02-22. Exact table-vintage/revision state remains uncertified."
 },
 "housing":{
   "feature":["lag1_bostadsbestandsforandring_pct"],
   "table_id":"BO0104D/BO0104T04",
   "reference_year":2023,
   "official_anchor_date":"2024-04-18",
   "anchor_type":"SCB housing-stock release for 31 Dec 2023",
   "exact_historical_table_vintage_certified":False,
   "notes":"Official housing-stock product release is dated 2024-04-18; exact archived PxWeb table values/revision state remain uncertified."
 }
}

origins={
 "2024-01-01":{
   "migration":"ineligible_anchor_after_origin",
   "population_denominator":"ineligible_anchor_after_origin",
   "housing":"ineligible_anchor_after_origin",
   "strict_core_use_allowed":False
 },
 "2024-05-01":{
   "migration":"official_product_anchor_before_origin_but_exact_table_vintage_unverified",
   "population_denominator":"official_product_anchor_before_origin_but_exact_table_vintage_unverified",
   "housing":"official_product_anchor_before_origin_but_exact_table_vintage_unverified",
   "strict_core_use_allowed":False
 }
}

out={
 "status":"scb_core_origin_gate",
 "production_changed":False,
 "sources":sources,
 "forecast_origins":origins,
 "decision":{
   "2024_01_01":"blocked",
   "2024_05_01":"research_only_pending_exact_vintage",
   "asof_verified_features":[],
   "next_required_evidence":[
      "archived or version-specific evidence for municipal Flyttningar97 2023 values",
      "archived/version-specific BefolkningNy 2023 denominator values and revision state",
      "archived/version-specific BO0104T04 2023 values and revision state"
   ],
   "no_model_run":True,
   "temporal_module_deferred":True
 }
}
(D/"neutral_scb_core_forecast_origin_gate.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
