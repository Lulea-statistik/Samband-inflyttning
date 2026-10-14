#!/usr/bin/env python3
"""Diagnose changes around RAMS 2011 and 2019 methodology boundaries."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
D=Path("docs/data")
def main():
    d=pd.read_csv(D/"commuting_historical_rams.csv",dtype={"kommun_kod":str})
    d.kommun_kod=d.kommun_kod.str.zfill(4)
    if len(d)!=5220 or d.duplicated(["kommun_kod","year"]).any():raise RuntimeError("RAMS integrity failed")
    d=d.sort_values(["kommun_kod","year"]).copy()
    d["residence"]=d.local+d.outgoing
    d["workplace"]=d.local+d.incoming
    for metric in ["residence","workplace"]:
        if (d[metric]<=0).any():raise RuntimeError("Invalid count "+metric)
        d["growth_"+metric]=100*(d[metric]/d.groupby("kommun_kod")[metric].shift(1)-1)
    result={"status":"exploratory_rams_method_break_diagnostic",
     "source":"commuting_historical_rams.csv","source_years":[2004,2021],
     "boundaries":[2011,2019],"production_changed":False,"metrics":{}}
    for metric in ["residence","workplace"]:
        col="growth_"+metric
        summaries={}
        for y,rows in d.groupby("year"):
            vals=rows[col].dropna()
            if len(vals)!=290:continue
            summaries[str(y)]={"municipalities":len(vals),"median_pct":float(vals.median()),
              "mean_pct":float(vals.mean()),"p10_pct":float(vals.quantile(.1)),
              "p90_pct":float(vals.quantile(.9)),"p95_abs_pct":float(vals.abs().quantile(.95))}
        boundaries={}
        for y in (2011,2019):
            current=d.loc[d.year==y,["kommun_kod",col]].rename(columns={col:"observed_growth"})
            preceding=d.loc[d.year.isin([y-3,y-2,y-1]),["kommun_kod",col]]
            baseline=preceding.groupby("kommun_kod")[col].median().rename("pre_break_median")
            m=current.merge(baseline,left_on="kommun_kod",right_index=True,validate="one_to_one")
            m["deviation_pp"]=m.observed_growth-m.pre_break_median
            boundaries[str(y)]={"national_median_growth_pct":summaries[str(y)]["median_pct"],
             "municipal_median_deviation_pp":float(m.deviation_pp.median()),
             "municipal_p90_abs_deviation_pp":float(m.deviation_pp.abs().quantile(.9)),
             "n_abs_deviation_gt_5pp":int(m.deviation_pp.abs().gt(5).sum()),
             "top_abs_deviations":m.reindex(m.deviation_pp.abs().sort_values(ascending=False).index).head(15).to_dict("records"),
             "lulea":m.loc[m.kommun_kod=="2580"].to_dict("records")}
        result["metrics"][metric]={"annual_summaries":summaries,"boundaries":boundaries}
    result["limitations"]=[
      "2011 and 2019 changes mix actual labour-market movement with measurement breaks: deviations do not identify a correction factor.",
      "2019 has no duplicate measurement under both methods; do not blindly smooth it.",
      "Older RAMS 2004-2018 imported from PendlingK summary; AM0207PendlKomA04 municipality-pair table not independently reconciled yet.",
      "The 2020/2021 BAS-RAMS bridge was separately diagnosed; neither overlap establishes publication-time availability.",
      "No regression or production features modified."]
    (D/"rams_2011_2019_break_diagnostic.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:{y:{b:round(z["municipal_median_deviation_pp"],3) for b,z in v["boundaries"].items()} for y in ["2011","2019"]} for k,v in result["metrics"].items()},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
