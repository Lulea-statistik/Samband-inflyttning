#!/usr/bin/env python3
"""Audit regression eligibility of employment growth observations across RAMS/BAS breaks.

Strict gate: 2011 (old RAMS), 2019 (between RAMS definitions), 2020 (BAS start),
and 2024 (BAS method caveat). No changes to model inputs.
"""
import csv,json
from collections import defaultdict
from pathlib import Path
D=Path("docs/data")
with (D/"employment_historical_regime_research.csv").open(newline="",encoding="utf-8") as f:
    records=list(csv.DictReader(f))
by=defaultdict(dict)
for x in records:
    key=(x["regime"],x["kommun_kod"])
    yr=int(x["year"])
    if yr in by[key]:raise RuntimeError("Duplicate year in "+str(key))
    by[key][yr]=x
regimes={"RAMS_2004_2018":(2004,2018),"RAMS_2019_2021":(2019,2021),"BAS_2020_2024":(2020,2024)}
flag_years={"RAMS_2004_2018":{2011},"RAMS_2019_2021":set(),"BAS_2020_2024":{2024}}
# 2019 transition is not calculable within a single regime. It must not be imputed.
out=[]
summary={}
for regime,(first,last) in regimes.items():
    n=0;blocked=0;usable=0
    for c in sorted({x["kommun_kod"] for x in records if x["regime"]==regime}):
        group=by[(regime,c)]
        if set(group)!=set(range(first,last+1)):raise RuntimeError("Incomplete regime "+regime+" "+c)
        for year in range(first+1,last+1):
            current=group[year];prev=group[year-1]
            reason="method_break_year" if year in flag_years[regime] else ""
            for dimension in ("residence","workplace"):
                a=float(prev["employed_"+dimension]);b=float(current["employed_"+dimension])
                if a<=0 or b<=0:raise RuntimeError("Bad employment level")
                out.append({"year":year,"kommun_kod":c,"dimension":dimension,"regime":regime,
                  "raw_within_regime_growth_pct":100*(b/a-1),
                  "method_break_sensitive":int(bool(reason)),
                  "eligible_for_exploratory_predictor":int(not reason),
                  "reason":reason})
                n+=1;blocked+=bool(reason);usable+=not bool(reason)
    summary[regime]={"measure_observations":n,"blocked":blocked,"eligible_for_candidate":usable}
with (D/"employment_growth_regime_gated.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
policy={"status":"method_break_guard_for_research","summary":summary,
 "explicitly_not_calculated":["RAMS transition 2018_to_2019","RAMS_to_BAS_cross_source_growth"],
 "potentially_eligible_not_final":"All unflagged within-regime changes still require source availability and regression fair-window tests.",
 "limitations":["Flagging the 2011 and 2024 calendar changes is conservative; it does not quantify or eliminate method effects.",
 "Only candidate historical changes are produced; lagging for forecast origin must be performed in a separate as-of audited step.",
 "2019-2020 source transition is avoided: no growth is computed by crossing RAMS and BAS regimes.",
 "Constant BAS level calibration does not change within-RAMS percentage growth; raw values are displayed intentionally."],
 "production_changed":False}
(D/"employment_growth_regime_gate_status.json").write_text(json.dumps(policy,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(policy,ensure_ascii=False),flush=True)
