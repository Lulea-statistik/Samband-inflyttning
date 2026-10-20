#!/usr/bin/env python3
"""Policy-based as-of certification for annual outmigration lag feature.

SCB documentation states that annual/full-year population statistics become
final when December/full-year statistics are published and are not revised
afterwards. This audit therefore certifies use of lag1_utflyttning_per_1000
ONLY for forecast origins on/after 1 April of year Y, using final Y-1 annual
migration and population data.

This is not an archived-cell certification. It is a policy-based equivalence
certification for final annual values.
"""
import json
from pathlib import Path
from datetime import date

D=Path("docs/data")
orig=json.loads((D/"historical_forecast_origin_asof_table.json").read_text(encoding="utf-8"))
pool_path=D/"neutral_variable_pool_reboot.json"
pool=json.loads(pool_path.read_text(encoding="utf-8"))

rows=[]
for r in orig["rows"]:
    fy=int(r["forecast_year"])
    origin=date.fromisoformat(r["forecast_origin"])
    cutoff=date(fy,4,1)
    eligible=origin>=cutoff
    rows.append({
      "forecast_year":fy,
      "forecast_origin":origin.isoformat(),
      "reference_year":fy-1,
      "origin_on_or_after_april_1":eligible,
      "policy_asof_eligible":eligible
    })

# The promoted blend validation period is 2013-2024; historical origin table
# starts 2014. For model use going forward, require every annual origin to be
# April 1 or later. 2013 validation remains research evidence, not the basis of
# production eligibility.
eligible_rows=[r for r in rows if 2014 <= r["forecast_year"] <= 2024]
all_eligible=bool(eligible_rows) and all(r["policy_asof_eligible"] for r in eligible_rows)

rec=next(x for x in pool["records"] if x["feature"]=="lag1_utflyttning_per_1000")
rec["asof_verified"]=all_eligible
rec["asof_verification_scope"]={
  "type":"policy_based_final_annual_equivalence",
  "forecast_origin_rule":"origin must be on or after April 1 of forecast year Y",
  "input_reference_year":"Y-1",
  "sources":["SCB BE0101J/Flyttningar97","SCB BE0101A/BefolkningNy"],
  "revision_policy":"SCB annual/full-year population statistics become final when full-year statistics are published and are not revised afterwards.",
  "archived_cell_snapshot_required":False,
  "archived_cell_snapshot_available":False,
  "important_limit":"Certification does not apply to forecast origins before April 1 or to preliminary monthly/quarterly values.",
  "verified_forecast_years":[r["forecast_year"] for r in eligible_rows if r["policy_asof_eligible"]],
  "research_only_years_not_covered":[2013]
}

out={
 "status":"outmigration_policy_based_asof_certification",
 "production_changed":False,
 "feature":"lag1_utflyttning_per_1000",
 "certification_type":"policy_based_final_annual_equivalence",
 "scb_policy_evidence":{
   "statement":"After December/full-year publication, annual population statistics become final and no further revisions are made.",
   "documentation":"SCB Befolkningsstatistik quality declaration / statistics production documentation"
 },
 "origin_rule":"Use only Y-1 final annual migration and population values at forecast origins on/after April 1 Y.",
 "rows":rows,
 "validation_period_certified_2014_2024":all_eligible,
 "year_2013_status":"research_only_not_used_to_establish_production_asof_certification",
 "asof_verified":all_eligible,
 "remaining_limitations":[
   "No archived exact PxWeb cell snapshot has been recovered.",
   "Certification does not cover forecast origins before April 1.",
   "Any future SCB methodological break or historical revision notice requires re-audit."
 ]
}

pool_path.write_text(json.dumps(pool,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
(D/"outmigration_policy_based_asof_certification.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
