#!/usr/bin/env python3
"""Identify new structural candidates with identical historical fixed-window requirements.

Audit only; no modeling, no publication of a model decision. Remove nonmunicipal
extra rows by requiring each year to contain the exact 290 valid municipality IDs
from the latest complete target year. Evaluate 3/5/10-year equal training windows.
"""
import json
from pathlib import Path
import pandas as pd
from audit_commuting_theme_candidates import THEMES
D=Path("docs/data")
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_inkomst_tkr",
 "lag1_andel_eftergymnasial","lag1_andel_fa_arbetsplatser_i_egen_kommun"]
EXCLUDED={"unemployment","housing_market","housing_sizes","shore_nature"}
def main():
    df=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    df["kommun_kod"]=df.kommun_kod.str.zfill(4)
    target=json.loads((D/"model.json").read_text())["target"]
    reference=df.loc[df.year.eq(2024)&df[target].notna(),"kommun_kod"].unique()
    if len(reference)!=290:raise RuntimeError(f"Expected 290 municipal IDs, found {len(reference)}")
    ids=set(reference);df=df.loc[df.kommun_kod.isin(ids)].copy()
    candidates={"labor_dynamics":THEMES["labor_dynamics"],
                "civic_associations":THEMES["civic_associations"]}
    # No model reuse of 2023/24 BAS commuting restrictions.
    report={"status":"fresh_structural_candidate_historical_coverage","years":sorted(int(z) for z in df.year.unique()),
      "municipalities":290,"target":target,"control_features":CONTROLS,
      "note":"Coverage screen only. A usable five-year window requires 5 training years plus the held-out forecast year.","candidate_results":{},
      "production_model_changed":False}
    for theme,features in candidates.items():
        for feature in features:
            cols=[target]+CONTROLS+[feature]
            absent=[c for c in cols if c not in df]
            coverage={}
            if not absent:
                for year,t in df.groupby("year"):
                    coverage[str(int(year))]=int(t.dropna(subset=cols).kommun_kod.nunique())
            complete=sorted(int(y) for y,n in coverage.items() if n==290)
            valid={}
            for length in (3,5,10):
                valid[str(length)]=[y for y in complete if all(z in complete for z in range(y-length,y))]
            report["candidate_results"][feature]={"theme":theme,"missing_columns":absent,
             "complete_years":complete,"forecast_years_fixed_window":valid,
             "coverage_2010_onward":{y:n for y,n in coverage.items() if int(y)>=2010}}
    (D/"fresh_structural_historical_coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v["forecast_years_fixed_window"] for k,v in report["candidate_results"].items()},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
