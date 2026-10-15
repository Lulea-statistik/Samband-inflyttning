#!/usr/bin/env python3
"""Discover auditable SCB candidate source constants and feature assignments.
This is a code-lineage aid, never a source-publication-vintage certification.
"""
import ast,json,re
from pathlib import Path
D=Path("docs/data")
src=Path("scripts/build_analysis.py")
lines=src.read_text(encoding="utf-8").splitlines()
inventory=json.loads((D/"neutral_source_lineage_alias_resolution.json").read_text(encoding="utf-8"))
# Constant URLs are drawn from executable assignments, not guessed feature names.
urls=[]
rx=re.compile(r'^([A-Z][A-Z0-9_]+)\s*=\s*["\'](https?://[^"\']+)["\']')
for no,line in enumerate(lines,1):
    m=rx.match(line)
    if m and ("scb.se" in m.group(2) or "kolada.se" in m.group(2)):
        urls.append({"constant":m.group(1),"url":m.group(2),"line":no})
out=[]
for r in inventory["records"]:
    name=r["feature"]
    assignments=[]
    for i,line in enumerate(lines):
        if ('["'+name+'"]' in line or "['"+name+"']" in line) and "=" in line:
            assignments.append({"line":i+1,"expression":line.strip()[:350],"preceding_context":" ".join(x.strip() for x in lines[max(0,i-2):i])[:220]})
    out.append({"feature":name,"local_derived_assignments":assignments[:20],
        "research_alias":r.get("research_csv_join"),
        "scb_table_match_status":"not_yet_proven",
        "source_publication_date_verified":False,
        "asof_eligible":False,
        "next_review":"Trace non-lagged base column through loader and exact SCB table or Kolada indicator."})
report={"status":"scb_constants_and_variable_derivations_extracted",
 "source_file":str(src),"source_constants":urls,"n_scb_or_kolada_constants":len(urls),
 "feature_count":len(out),"n_with_local_assignment":sum(bool(x["local_derived_assignments"]) for x in out),
 "features":out,"caveats":[
 "Constants are real links referenced in repository code, not verified public historical releases.",
 "Candidate feature derivations such as shift(1) do not establish upstream source column lineage.",
 "Historical availability and source publication dates remain blocked.",
 "No historical test and no production change."],"production_changed":False}
(D/"neutral_source_tables_derivation_index.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"constants":len(urls),"features":len(out),"assignment_matches":report["n_with_local_assignment"]}))
