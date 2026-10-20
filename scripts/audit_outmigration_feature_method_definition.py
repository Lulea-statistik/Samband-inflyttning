#!/usr/bin/env python3
"""Certify the construction method of lag1_utflyttning_per_1000.

This audit does NOT certify historical as-of availability. It only certifies
that the repository's production panel code defines the feature unambiguously.
"""
import json
from pathlib import Path

D=Path("docs/data")
pool_path=D/"neutral_variable_pool_reboot.json"
pool=json.loads(pool_path.read_text(encoding="utf-8"))

records=pool["records"]
rec=next(r for r in records if r["feature"]=="lag1_utflyttning_per_1000")

rec["method_definition_verified"]=True
rec["method_definition_audit"]={
  "source_script":"scripts/build_analysis.py",
  "migration_table":"BE0101J/Flyttningar97",
  "population_table":"BE0101A/BefolkningNy",
  "formula":"utflyttning_per_1000 = 1000 * utflyttade / folkmangd",
  "lag_formula":"lag1_utflyttning_per_1000 = municipality_group(utflyttning_per_1000).shift(1)",
  "verified_scope":"construction_method_only",
  "asof_verified":False,
  "note":"This certifies how the feature is built, not that historical source values were available unchanged at each forecast origin."
}
rec["asof_verified"]=False

audit={
  "status":"lag1_utflyttning_per_1000_method_definition_certified",
  "production_changed":False,
  "feature":"lag1_utflyttning_per_1000",
  "method_definition_verified":True,
  "asof_verified":False,
  "evidence":{
    "source_script":"scripts/build_analysis.py",
    "migration_source":"SCB BE0101J/Flyttningar97, content Utflyttningar",
    "population_source":"SCB BE0101A/BefolkningNy, content Folkmängd",
    "rate_formula":"1000 * utflyttade / folkmangd",
    "lagging":"one-year shift within kommun_kod after sorting by kommun_kod and year"
  },
  "remaining_blocker":"Exact historical value-vintage/revision evidence for Flyttningar97 and BefolkningNy."
}

pool_path.write_text(json.dumps(pool,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
(D/"outmigration_feature_method_definition_audit.json").write_text(
  json.dumps(audit,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(audit,ensure_ascii=False,indent=2))
