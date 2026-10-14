#!/usr/bin/env python3
"""Audit RAMS/BAS outcommuting comparability; independent historical RAMS-only benchmark.

This is outcommuting, NOT a validation of RAMS/BAS employment-growth measures.
Do not join or rescale methodological regimes for production.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV
from build_analysis import _geographic_error_metrics
D=Path("docs/data")
CORE=["lag1_inflyttning_per_1000","lag1_utflyttning_per_1000","lag1_log_folkmangd","lag1_befolkningstillvaxt_pct","lag1_andel_20_34","lag1_inflyttare_medelalder"]
def stats(a):
    return {"n":int(len(a)),"mean":float(np.mean(a)),"median":float(np.median(a)),
        "sd":float(np.std(a)),"p10":float(np.quantile(a,.1)),"p90":float(np.quantile(a,.9))}
def main():
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    panel.kommun_kod=panel.kommun_kod.str.zfill(4)
    model=json.loads((D/"model.json").read_text());target=model["target"]
    r=pd.read_csv(D/"commuting_historical_rams.csv",dtype={"kommun_kod":str})
    r.kommun_kod=r.kommun_kod.str.zfill(4)
    flows=pd.read_csv(D/"commuting_flows_2020_2024.csv",dtype={"home":str,"work":str})
    denom=flows.groupby(["year","home"],as_index=False).employed.sum().rename(columns={"home":"kommun_kod","employed":"total"})
    local=flows.loc[flows.home==flows.work,["year","home","employed"]].rename(columns={"home":"kommun_kod","employed":"local"})
    bas=denom.merge(local,on=["year","kommun_kod"],validate="one_to_one")
    bas["bas_share"]=100*(bas.total-bas.local)/bas.total
    compare=r.loc[r.year.isin([2020,2021]),["year","kommun_kod","outcommuting_share_pct"]].merge(
        bas[["year","kommun_kod","bas_share"]],on=["year","kommun_kod"],validate="one_to_one")
    if len(compare)!=580:raise RuntimeError(f"Missing overlaps: {len(compare)}")
    overlaps={}
    for yr,g in compare.groupby("year"):
        delta=(g.outcommuting_share_pct-g.bas_share).to_numpy()
        overlaps[str(yr)]={"n":len(g),"rams":stats(g.outcommuting_share_pct.to_numpy()),
            "bas":stats(g.bas_share.to_numpy()),"mean_signed_difference_rams_minus_bas":float(np.mean(delta)),
            "mean_absolute_difference":float(np.mean(np.abs(delta))),
            "p95_absolute_difference":float(np.quantile(np.abs(delta),.95)),
            "correlation":float(g[["outcommuting_share_pct","bas_share"]].corr().iloc[0,1]),
            "n_over_2pp":int((np.abs(delta)>2).sum())}
    # Evaluate RAMS on 2014-2018 only: no 2019 methodology change, same six lagged controls.
    hist=r.loc[r.year.between(2012,2017),["year","kommun_kod","outcommuting_share_pct"]].rename(
        columns={"outcommuting_share_pct":"rams_share"})
    hist.year+=1
    d=panel.merge(hist,on=["year","kommun_kod"],how="inner",validate="one_to_one")
    series={}
    for yr in (2015,2016,2017,2018):
        train=d.loc[d.year.between(2013,yr-1)].dropna(subset=CORE+[target,"rams_share"]).copy()
        test=d.loc[d.year.eq(yr)].dropna(subset=CORE+[target,"rams_share"]).copy()
        if len(test)!=290 or len(train)<580:raise RuntimeError(f"Historical fair sample incomplete {yr}: {len(train)}/{len(test)}")
        scores={}
        for name,cols in {"historical_core":CORE,"historical_core_plus_RAMS":CORE+["rams_share"]}.items():
            fit=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            fit.fit(train[cols],train[target])
            yhat=fit.predict(test[cols])
            m=_geographic_error_metrics(test[target],yhat)
            scores[name]={"rmse":float(m["rmse"]),"mae":float(m["mae"])}
        series[str(yr)]={"train_years":sorted(int(x) for x in train.year.unique()),"n_test":len(test),"scores":scores}
        print(json.dumps({"year":yr,"scores":scores},ensure_ascii=False),flush=True)
    out={"status":"rams_bas_outcommuting_overlap_and_historical_rams_test",
        "overlap_source_years":[2020,2021],"overlap":overlaps,
        "historical_rams_forecast_years":[2015,2016,2017,2018],
        "historical_baseline_features":CORE,"historical_model_is_not_current_dynamic_model":True,
        "historical_results":series,
        "limitations":["Overlap tests outcommuting SHARE, not BAS versus RAMS employment-growth measures.",
         "Six-variable historical core cannot be compared directly to 27-variable modern incumbent.",
         "RAMS 2019 method break and 2011 age change explicitly excluded from historical forecast test.",
         "2020-2021 overlap is insufficient to prove cross-regime comparability.",
         "Observational historical test is retrospective, not unseen future-year validation."],
        "production_model_changed":False}
    (D/"commuting_rams_bas_historical_audit.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
