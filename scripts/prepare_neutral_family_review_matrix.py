#!/usr/bin/env python3
"""Prepare neutral variable-family review decisions from descriptive correlations."""
import json
from collections import defaultdict,Counter
from pathlib import Path
D=Path("docs/data")
inventory=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))
audit=json.loads((D/"neutral_variable_family_correlation_audit.json").read_text(encoding="utf-8"))
entries={r["feature"]:r for r in inventory["records"]}
if len(entries)!=80:raise RuntimeError("Expected 80 unique inventory variables")
pairs=audit["high_correlation_pairs"]
parent={n:n for n in entries}
def root(v):
    while parent[v]!=v:
        parent[v]=parent[parent[v]]
        v=parent[v]
    return v
def union(a,b):
    aa,bb=root(a),root(b)
    if aa!=bb:parent[bb]=aa
for p in pairs:union(p["a"],p["b"])
components=defaultdict(list)
for name in entries:components[root(name)].append(name)
groups=[]
for names in components.values():
    if len(names)<2:continue
    names.sort()
    edges=[{"a":p["a"],"b":p["b"],"rho":p["spearman"],
            "n":p["n_complete_pairs"]} for p in pairs if p["a"] in names and p["b"] in names]
    groups.append({"members":names,"edge_count":len(edges),"edges":edges,
        "review_status":"correlation_network_not_exclusion",
        "action":"inspect definitions, transformations and incremental train-only value"})
groups.sort(key=lambda g:(-len(g["members"]),g["members"][0]))
# Named family definitions from the prior audit are review tags; these may overlap network groups.
families=[]
for f in audit["predefined_families"]:
    members=f["variables"]
    families.append({"family":f["family"],"members":members,
       "presence":{"in_panel":sum(x not in audit["not_in_panel"] for x in members),
                   "total":len(members)},
       "review":"do_not_select_prior_to_common_window_testing"})
blind=[n for n,x in entries.items() if x["blind_model_eligible_subject_to_audit"]]
forecast=list(entries)
nonblind=sorted(set(forecast)-set(blind))
high_yearly=audit["within_year_checks"]
report={"status":"neutral_family_review_matrix","inventory_count":len(entries),
 "blind_universe_preliminary":len(blind),"forecast_universe_preliminary":len(forecast),
 "forecast_only_demographic":nonblind,"correlation_network_components":groups,
 "connected_groups_count":len(groups),"strong_pairs_count":len(pairs),
 "named_candidate_families":families,
 "separate_research_sources":audit["not_in_panel"],
 "within_year_high_pair_counts":{yr:x["high_full_window_pairs_still_ge_0_85"] for yr,x in high_yearly.items()},
 "next_gates":[
  "Verify pairwise relationships at equal common rows, including yearwise stability and exact algebraic identity versus monotonic transformation.",
  "Classify source definition and same-outcome risk for each candidate; forecast-only demographics never enter blind branch.",
  "Compare alternate representations only in nested train-only tests with the same observations and evaluation years.",
  "Resolve source-vintage availability separately from panel coverage; recent RAMS/BAS histories are not automatically approved.",
  "Reserve repeatedly inspected 2024 as exploratory; no incumbent feature receives a selection advantage."],
 "production_changed":False,"no_variable_eliminated":True}
(D/"neutral_family_review_matrix.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"variables":len(entries),"strong_pairs":len(pairs),"connected_groups":len(groups),
"blind_candidates":len(blind),"forecast_only":len(nonblind)},ensure_ascii=False))
