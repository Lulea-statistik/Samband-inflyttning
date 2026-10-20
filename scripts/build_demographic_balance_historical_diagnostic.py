#!/usr/bin/env python3
"""Build historical demographic balance diagnostic from frozen/preliminary component cores.

This is a diagnostic integration test only. It does not change production models.

Uses:
- birth compact 3y core: lag1_fodelsetal_per_100 + lag1_andel_20_34
- death compact 3y core: lag1_dodstal_per_1000 + lag1_bas_pensionarer_andel_pct
- observed migration counts from panel.csv for accounting validation where available

Purpose:
1. quantify accounting residual in historical data
2. check rate-to-count conversion consistency
3. prepare later integration with frozen inflow/outflow forecast models
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
t=pd.read_csv(D/"demographic_birth_death_targets.csv",dtype={"kommun_kod":str})
t["kommun_kod"]=t["kommun_kod"].astype(str).str.zfill(4)

q=p.merge(t,on=["kommun_kod","year"],how="inner",validate="one_to_one")
q=q.sort_values(["kommun_kod","year"])
q["pop_prev"]=q.groupby("kommun_kod")["folkmangd"].shift(1)
q["delta_population"]=q["folkmangd"]-q["pop_prev"]

# Resolve observed migration counts from known candidate column names.
def first_existing(cols):
    for c in cols:
        if c in q.columns:return c
    return None

in_col=first_existing(["inflyttade","inflyttning_antal","inflyttning","inmigrations"])
out_col=first_existing(["utflyttade","utflyttning_antal","utflyttning","outmigrations"])

if in_col is None or out_col is None:
    # fall back to rate * annual population if explicit counts are absent
    if "inflyttning_per_1000" in q.columns and "utflyttning_per_1000" in q.columns:
        q["observed_inflow_count_proxy"]=q["inflyttning_per_1000"]*q["folkmangd"]/1000.0
        q["observed_outflow_count_proxy"]=q["utflyttning_per_1000"]*q["folkmangd"]/1000.0
        in_col="observed_inflow_count_proxy"; out_col="observed_outflow_count_proxy"
        migration_method="rate_times_annual_population_proxy"
    else:
        raise RuntimeError("No migration count or rate columns found")
else:
    migration_method=f"direct_counts:{in_col},{out_col}"

q["births_from_rate"]=q["fodelsetal_per_100"]*q["mean_population"]/100.0
q["deaths_from_rate"]=q["dodstal_per_1000"]*q["mean_population"]/1000.0
q["natural_change"]=q["births_from_rate"]-q["deaths_from_rate"]
q["net_migration"]=q[in_col]-q[out_col]
q["component_change"]=q["natural_change"]+q["net_migration"]
q["accounting_residual"]=q["delta_population"]-q["component_change"]

z=q[q["year"].between(2014,2024)].copy()
z=z[np.isfinite(z["accounting_residual"])]

def metrics(df):
    r=df["accounting_residual"].to_numpy(float)
    return {
      "n_rows":int(len(df)),
      "mae_persons":float(np.mean(np.abs(r))),
      "rmse_persons":float(np.sqrt(np.mean(r*r))),
      "bias_persons":float(np.mean(r)),
      "median_abs_persons":float(np.median(np.abs(r))),
      "p95_abs_persons":float(np.quantile(np.abs(r),0.95))
    }

out={
 "status":"demographic_balance_historical_diagnostic",
 "production_changed":False,
 "birth_core":{"window_years":3,"features":["lag1_fodelsetal_per_100","lag1_andel_20_34"]},
 "death_core":{"window_years":3,"features":["lag1_dodstal_per_1000","lag1_bas_pensionarer_andel_pct"]},
 "migration_observed_method":migration_method,
 "rate_to_count_method":{
   "births":"fodelsetal_per_100 * mean_population / 100",
   "deaths":"dodstal_per_1000 * mean_population / 1000"
 },
 "all_municipalities":metrics(z),
 "lulea":metrics(z[z.kommun_kod.eq("2580")]),
 "lulea_years":[
   {
    "year":int(r.year),
    "delta_population":float(r.delta_population),
    "births":float(r.births_from_rate),
    "deaths":float(r.deaths_from_rate),
    "inflow":float(r._asdict()[in_col]),
    "outflow":float(r._asdict()[out_col]),
    "component_change":float(r.component_change),
    "accounting_residual":float(r.accounting_residual)
   } for r in z[z.kommun_kod.eq("2580")].itertuples(index=False)
 ],
 "interpretation_note":"Residual captures SCB revisions, late registrations, boundary/correction effects and any denominator/count mismatch. It must be quantified before forecast integration."
}
(D/"demographic_balance_historical_diagnostic.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
