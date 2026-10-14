#!/usr/bin/env python3
"""RAMS/BAS employed totals by residence/work: overlap calibration diagnostics only."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
D=Path("docs/data")
def totals(df,prefix):
    return df.assign(
        **{prefix+"_residence":df["local"]+df["outgoing"],
           prefix+"_workplace":df["local"]+df["incoming"]})
def main():
    r=pd.read_csv(D/"commuting_historical_rams.csv",dtype={"kommun_kod":str})
    r.kommun_kod=r.kommun_kod.str.zfill(4)
    r=totals(r,"rams")
    b=pd.read_csv(D/"commuting_flows_2020_2024.csv",dtype={"home":str,"work":str})
    b.home=b.home.str.zfill(4);b.work=b.work.str.zfill(4)
    status=json.loads((D/"commuting_import_status.json").read_text(encoding="utf-8"))
    if not status.get("aggregation_approved",False):raise RuntimeError("BAS OD aggregation not approved: missing/suppressed cells")
    if b.duplicated(["year","home","work"]).any():raise RuntimeError("Duplicate BAS origin-destination cell")
    resident=b.groupby(["year","home"],as_index=False).employed.sum().rename(columns={"home":"kommun_kod","employed":"bas_residence"})
    workplace=b.groupby(["year","work"],as_index=False).employed.sum().rename(columns={"work":"kommun_kod","employed":"bas_workplace"})
    bas=resident.merge(workplace,on=["year","kommun_kod"],validate="one_to_one")
    overlap=r.loc[r.year.isin([2020,2021]),["year","kommun_kod","rams_residence","rams_workplace"]].merge(
        bas.loc[bas.year.isin([2020,2021])],on=["year","kommun_kod"],validate="one_to_one")
    if len(overlap)!=580:raise RuntimeError("Expected 580 overlap observations: "+str(len(overlap)))
    report={"status":"exploratory_rams_bas_level_bridge","overlap_years":[2020,2021],
     "historical_rams_regimes":["RAMS_2004_2018","RAMS_2019_2021"],
     "series":{"residence":{},"workplace":{}},"production_changed":False,
     "cautions":["RAMS 2018/19 AGI break; do not smooth mechanically across it.",
       "BAS versus RAMS has definition and age-coverage differences; 2020-21 overlap is only two years.",
       "This report calibrates counts, not seasonal variation nor causality, and does not alter production features.",
       "Full historical as-of source availability still needs separate audit."]}
    for type_ in ["residence","workplace"]:
        old=overlap["rams_"+type_];new=overlap["bas_"+type_]
        if (old<=0).any() or (new<=0).any():raise RuntimeError("Invalid level for log bridge")
        compare=overlap.assign(log_ratio=np.log(new/old),relative_gap_pct=100*(new/old-1))
        by_year={}
        for year,g in compare.groupby("year"):
            by_year[str(year)]={"median_gap_pct":float(g.relative_gap_pct.median()),
             "mean_gap_pct":float(g.relative_gap_pct.mean()),
             "p10_gap_pct":float(g.relative_gap_pct.quantile(.10)),
             "p90_gap_pct":float(g.relative_gap_pct.quantile(.90)),
             "n_gt_5pct":int(g.relative_gap_pct.abs().gt(5).sum()),
             "n_gt_10pct":int(g.relative_gap_pct.abs().gt(10).sum())}
        pivot=compare.pivot(index="kommun_kod",columns="year",values="log_ratio")
        drift=pivot[2021]-pivot[2020]
        national_anchor=float(compare.log_ratio.median())
        # Exploratory pooled 2020/2021 municipality factor, shrunk toward common anchor.
        shrink=(pivot.mean(axis=1)*2+national_anchor*3)/5
        annual_regime=r.assign(year=r.year.astype(int)).copy()
        anchor=annual_regime[["kommun_kod","year","regime","rams_"+type_]].rename(columns={"rams_"+type_":"unadjusted"})
        anchor=anchor.merge(shrink.rename("log_factor"),left_on="kommun_kod",right_index=True,validate="many_to_one")
        anchor["bridge_diagnostic"]=anchor.unadjusted*np.exp(anchor.log_factor)
        anchor["regime_boundary"]="RAMS_2004_2018_not_calibrated" 
        anchor.loc[anchor.year>=2019,"regime_boundary"]="RAMS_2019_2021_AGI"
        # Save calibration as diagnostic, not an approved or continuous series.
        report["series"][type_]={"by_year":by_year,
          "municipality_factor_drift_log_median_abs":float(drift.abs().median()),
          "municipality_factor_drift_log_p90_abs":float(drift.abs().quantile(.9)),
          "pooled_log_ratio_median":national_anchor,
          "calibration_status":"diagnostic_only",
          "municipal_factors":[{"kommun_kod":str(code),"log_factor":float(val),
             "ratio_2020":float(np.exp(pivot.loc[code,2020])),
             "ratio_2021":float(np.exp(pivot.loc[code,2021]))}
              for code,val in shrink.items()]}
        print(type_,by_year,flush=True)
    (D/"rams_bas_employment_level_bridge.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
