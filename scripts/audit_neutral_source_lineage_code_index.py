#!/usr/bin/env python3
"""Map candidate feature names to source-code references; NOT publication-vintage verification."""
import json,re
from pathlib import Path
D=Path("docs/data")
records=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))["records"]
sourcepaths=[Path("scripts/build_analysis.py")]
sourcepaths += [p for p in Path("scripts").glob("*.py") if "employment" in p.name or "scb" in p.name]
sourcepaths=list(dict.fromkeys(p for p in sourcepaths if p.is_file()))
files={str(p):p.read_text(encoding="utf-8",errors="replace").splitlines() for p in sourcepaths}
out=[]
for rec in records:
    name=rec["feature"];hits=[]
    for path,lines in files.items():
        for i,line in enumerate(lines):
            if name in line:
                hits.append({"path":path,"line":i+1,"excerpt":line.strip()[:200],
                 "context_lines":[max(1,i-4),min(len(lines),i+5)]})
    out.append({"feature":name,"theme":rec.get("theme"),"incumbent":rec.get("incumbent"),
     "source_code_mentions":hits[:40],"source_code_mention_count":len(hits),
     "candidate_definition_located":bool(hits),
     "source_url_confirmed_for_feature":False,
     "historical_publication_verified":False,
     "caveat":"Mention in code is not a verified definition, SCB source lineage or archived publication date."})
counts={"candidates":len(out),"with_source_code_mentions":sum(bool(x["source_code_mentions"]) for x in out),
        "missing_code_mentions":[x["feature"] for x in out if not x["source_code_mentions"]]}
result={"status":"source_code_lineage_discovery_not_vintage_verified",
 "source_files_scanned":list(files),"counts":counts,"records":out,
 "historical_asof_verified_count":0,"production_changed":False,
 "next_step":"Review relevant code contexts and source metadata manually, then document archived publication timestamp for each candidate."}
(D/"neutral_source_lineage_code_index.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(counts,ensure_ascii=False))
