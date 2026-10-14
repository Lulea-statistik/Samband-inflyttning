#!/usr/bin/env python3
"""Audit all 80 neutral candidates and six special pairs; no model fitting."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
D=Path("docs/data")
inv=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))
cl=json.loads((D/"neutral_correlated_pair_classification.json").read_text(encoding="utf-8"))
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p.kommun_kod=p.kommun_kod.str.zfill(4)
lag=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
lag.kommun_kod=lag.kommun_kod.str.zfill(4)
official=set(lag.loc[lag.target_year==2024,"kommun_kod"])
if len(official)!=290:raise RuntimeError("Expected 290 SCB municipality codes")
p=p[p.kommun_kod.isin(official)&p.year.between(2002,2024)].copy()
if p.duplicated(["year","kommun_kod"]).any():raise RuntimeError("Duplicated panel municipality years")
if lag.duplicated(["target_year","kommun_kod","dimension"]).any():raise RuntimeError("Duplicated employment candidates")
wide=lag.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct").reset_index()
wide=wide.rename(columns={"target_year":"year","residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct","workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"})
p=p.merge(wide,on=["year","kommun_kod"],how="left",validate="one_to_one")
names=[x["feature"] for x in inv["records"]]
if len(names)!=80 or not all(x in p.columns for x in names):raise RuntimeError("Inventory not fully joined")
year_cov={}
for name in names:
    v=pd.to_numeric(p[name],errors="coerce")
    valid=np.isfinite(v)
    year_cov[name]={str(y):int(valid[p.year==y].sum()) for y in range(2002,2025)}
special=[]
for pair in cl["pairs"]:
    if pair["provisional_relationship"]=="empirical_association_only":continue
    a,b=pair["a"],pair["b"]
    z=p.loc[p.year.between(2019,2023),[a,b]].apply(pd.to_numeric,errors="coerce").dropna()
    z=z[np.isfinite(z[a]) & np.isfinite(z[b])]
    entry={"a":a,"b":b,"provisional":pair["provisional_relationship"],"n":len(z),"calculation_definition_verified":False}
    if len(z)>0:
        x,y=z[a].to_numpy(),z[b].to_numpy()
        entry["pearson"]=float(np.corrcoef(x,y)[0,1]) if np.std(x)>0 and np.std(y)>0 else None
        entry["sum_min"]=float(np.min(x+y))
        entry["sum_max"]=float(np.max(x+y))
        entry["sum_range"]=float(np.ptp(x+y))
        entry["linear_fit_max_abs_residual"]=float(np.max(np.abs(y-(np.polyval(np.polyfit(x,y,1),x))))) if np.std(x)>0 else None
        entry["same_numeric_values"]=bool(np.allclose(x,y,rtol=1e-10,atol=1e-10))
    special.append(entry)
out={"status":"neutral_80_candidate_coverage_and_special_pair_data_gate","municipalities":290,"years":[2002,2024],
 "n_panel_rows":len(p),"variables":year_cov,
 "full_coverage_2019_2023":sum(all(v[str(y)]==290 for y in range(2019,2024)) for v in year_cov.values()),
 "full_coverage_2024":sum(v["2024"]==290 for v in year_cov.values()),
 "full_coverage_all_2019_2024":sum(all(v[str(y)]==290 for y in range(2019,2025)) for v in year_cov.values()),
 "historical_employment_missing_2020":{k:year_cov[k]["2020"] for k in names if "rams_bas_historisk" in k},
 "special_pair_numeric_checks":special,
 "source_definitions_verified":False,"publication_asof_verified":False,"production_changed":False,
 "limitations":["Numeric complements/transforms cannot be certified without checking definition code and source denominators.",
 "Historical publication-vintage audit remains incomplete.",
 "No outcome-based correlations, selection or regression.", "No imputation or cross-regime growth constructed."]}
(D/"neutral_80_candidate_data_gate.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({"rows":len(p),"variables":len(names),"full_2019_2023":out["full_coverage_2019_2023"],"checks":len(special)},ensure_ascii=False))
