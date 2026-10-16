#!/usr/bin/env python3
"""Verify completeness and integrity of the latest forecast-core source snapshot."""
import hashlib, json
from pathlib import Path

ROOT=Path("docs/data/source_snapshots")
dirs=sorted(p for p in ROOT.iterdir() if p.is_dir())
assert dirs, "No source snapshots found"
snap=dirs[-1]
manifest=json.loads((snap/"manifest.json").read_text(encoding="utf-8"))

required=[
 "scb_migration_metadata.json","scb_migration_query.json","scb_migration_values.json",
 "scb_population_metadata.json","scb_population_query.json","scb_population_values.json",
 "scb_housing_metadata.json","scb_housing_query.json","scb_housing_values.json",
 "kolada_N03937_metadata.json","manifest.json"
]
for fn in required:
    p=snap/fn
    assert p.exists() and p.stat().st_size>0, f"Missing/empty {fn}"

for year in range(2019,2027):
    p=snap/f"kolada_N03937_{year}.json"
    assert p.exists() and p.stat().st_size>0, f"Missing {p.name}"

assert manifest["snapshot_protocol_version"]==2
vr=manifest["validation_requirements"]
assert vr["future_scoring_must_use_snapshot_values"] is True
assert vr["refit_before_scoring"] is False
assert vr["reselect_before_scoring"] is False
assert vr["retune_before_scoring"] is False

hashes={}
for p in sorted(snap.iterdir()):
    if p.is_file():
        hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()

out={
 "status":"forecast_core_snapshot_verified",
 "snapshot":snap.name,
 "captured_at_utc":manifest["captured_at_utc"],
 "protocol_version":manifest["snapshot_protocol_version"],
 "all_required_files_present":True,
 "future_scoring_rules_verified":True,
 "sha256":hashes,
 "production_changed":False
}
Path("docs/data/forecast_core_snapshot_verification.json").write_text(
    json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
