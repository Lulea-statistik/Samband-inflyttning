#!/usr/bin/env python3
"""Neutral, non-predictive correlation and variable-family audit. No feature selection."""
import json
from collections import Counter
from pathlib import Path
import pandas as pd
D=Path("docs/data")
inventory=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))
r=inventory["records"]
families={
 "sysselsatta_bostad_tillvaxt":["lag1_sysselsatta_bostad_forandring_pct","lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct"],
 "sysselsatta_arbetsstalle_tillvaxt":["lag1_sysselsatta_arbetsstalle_forandring_pct","lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"],
 "smahuspris":["lag1_smahuspris_medel_tkr","lag1_log_smahuspris_medel"],
 "fritidshus":["lag1_fritidshus_per_1000_inv","lag1_log_fritidshus_per_1000_inv"],
 "avstand_regionalt_centrum":["lag1_regional_centre_distance_km","lag1_log_regional_centre_distance_km"],
 "arbetskraft_utanfor":["lag1_utanf_arbetkraften_andel_pct","lag1_utanf_arbetkraften_andel_fran_komponenter_pct"],
 "snoskoterandel":["lag1_snoskoterandel_alla_fordon_pct","lag1_snoskoterandel_exkl_dragfordon_pct"],
 "gymnasieinriktning":["lag1_gymnasium_hogskoleforberedande_pct","lag1_gymnasium_yrkesprogram_pct"],
 "arbetsloshet":["lag1_arbetsloshet","lag1_kolada_arbetslosa_18_65_pct","lag1_kolada_arbetslosa_18_24_pct","lag1_kolada_langtidsarbetslosa_pct"],
 "bostadsstorlekar":["lag1_andel_bostader_111_plus","lag1_andel_bostader_141_plus","lag1_andel_bostader_151_plus",
 "lag1_andel_smahus_111_plus","lag1_andel_smahus_151_plus"]
}
names={x["feature"] for x in r}
for fam,values in families.items():
    unknown=set(values)-names
    if unknown:raise RuntimeError(f"Unknown variable in family {fam}: {unknown}")
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p.kommun_kod=p.kommun_kod.str.zfill(4)
# A stable common reference group: 290 municipality codes already validated in the lagged audit.
lag=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str},usecols=["target_year","kommun_kod"])
communities=set(lag.loc[lag.target_year==2024,"kommun_kod"].str.zfill(4))
if len(communities)!=290:raise RuntimeError("Bad municipality reference")
p=p[p.year.between(2019,2023)&p.kommun_kod.isin(communities)].copy()
if len(p)!=1450 or p.duplicated(["year","kommun_kod"]).any():raise RuntimeError("Bad reference sample")
existing=[x for x in sorted(names) if x in p]
numeric=p[existing].apply(pd.to_numeric,errors="coerce")
corr=numeric.corr(method="spearman",min_periods=800)
pairs=[]
for i,a in enumerate(existing):
    for b in existing[i+1:]:
        joined=numeric[[a,b]].dropna()
        value=corr.loc[a,b]
        if len(joined)<800 or pd.isna(value):continue
        if abs(value)>=.85:
            pairs.append({"a":a,"b":b,"spearman":round(float(value),5),
            "n_complete_pairs":int(len(joined)),
            "same_theme":next(x["theme"] for x in r if x["feature"]==a)==next(x["theme"] for x in r if x["feature"]==b)})
pairs.sort(key=lambda x:-abs(x["spearman"]))
byyear={}
for y,part in p.groupby("year"):
    frame=part[existing].apply(pd.to_numeric,errors="coerce")
    cc=frame.corr(method="spearman",min_periods=200)
    yearpairs=[]
    for item in pairs:
        v=cc.loc[item["a"],item["b"]]
        if pd.notna(v):yearpairs.append({"a":item["a"],"b":item["b"],"rho":round(float(v),5)})
    byyear[str(y)]={"n_communities":len(part),"high_full_window_pairs_available":len(yearpairs),
        "high_full_window_pairs_still_ge_0_85":sum(abs(x["rho"])>=.85 for x in yearpairs)}
family_report=[]
for f,values in families.items():
    family_report.append({"family":f,"variables":values,"all_present_in_panel":all(v in p for v in values),
      "status":"candidate_alternatives_not_independent","decision":"no_preference_assigned"})
reported=set(v for x in families.values() for v in x)
result={"status":"non_predictive_correlation_audit","years":[2019,2020,2021,2022,2023],
 "municipalities":290,"rows":1450,"inventory_variables":len(r),"in_panel":len(existing),
 "not_in_panel":sorted(names-set(existing)),
 "high_absolute_spearman_threshold":0.85,"high_correlation_pairs":pairs,
 "high_correlation_pair_count":len(pairs),"within_year_checks":byyear,
 "predefined_families":family_report,"family_covered_variable_count":len(reported),
 "five_out_of_pool_demographic_features":[x["feature"] for x in r if x["origin"]=="prior_inventory_only"],
 "production_changed":False,
 "limitations":["Correlations are descriptive, not causal, and do not rank predictors by usefulness.",
 "Pooled municipality-year correlations can be driven by municipality size and common time patterns.",
 "Correlations in single years, alternative transformations and residualized effects require separate interpretation.",
 "Features missing from the current panel are reported rather than silently excluded from inventory.",
 "New historical RAMS/BAS features live in a separate research file and must not be treated as missing from the inventory.",
 "No automatic feature selection, no outcome-based ranking and no modification of production panel."]}
(D/"neutral_variable_family_correlation_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"inventory":len(r),"in_panel":len(existing),"strong_pairs":len(pairs),"families":len(families)},ensure_ascii=False))
