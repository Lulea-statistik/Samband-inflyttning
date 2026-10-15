#!/usr/bin/env python3
"""Add explicit research-series lineage to previous neutral source code index."""
import json
from pathlib import Path
D=Path("docs/data")
report=json.loads((D/"neutral_source_lineage_code_index.json").read_text(encoding="utf-8"))
aliases={
 "lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct":"residence",
 "lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct":"workplace"}
for row in report["records"]:
    name=row["feature"]
    if name not in aliases:continue
    dim=aliases[name]
    row["research_csv_join"]={
      "data_path":"docs/data/employment_lag1_research_availability.csv",
      "dimension":dim,"value_column":"growth_pct",
      "join_keys":["target_year","kommun_kod","dimension"],
      "upstream_scripts":["scripts/build_employment_regime_history.py",
        "scripts/audit_employment_growth_regime_gate.py",
        "scripts/audit_employment_lag1_availability.py"],
      "source_inputs":["docs/data/commuting_historical_rams.csv",
        "docs/data/commuting_flows_2020_2024.csv"],
      "regime_selection":"research preference; not historical as-of approval",
      "asof_source_release_verified":False}
    row["candidate_definition_located"]=True
    row["lineage_evidence_type"]="upstream_csv_regime_aware_research"
report["status"]="code_index_with_historical_employment_research_aliases"
report["counts"]["resolved_research_aliases"]=2
report["counts"]["remaining_unmapped_names"]=0
report["notes"]=[
 "78 candidate names matched code in initial audit. Two names are analytical aliases joined from separate CSV.",
 "Explicit alias mapping resolves local research-file lineage but does not prove historical publication, methodology equivalence, or genuine forecast availability.",
 "SCB release-vintage evidence remains pending for all 80 candidates." ]
report["historical_asof_verified_count"]=0
(D/"neutral_source_lineage_alias_resolution.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"candidates":len(report["records"]),"aliases":2,"asof":0}))
