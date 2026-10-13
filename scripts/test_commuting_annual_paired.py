#!/usr/bin/env python3
"""Paired annual outcommuting diagnostics, same complete-feature sample and train-only selection.
Separate source regimes: RAMS 2021-22 forecast, BAS 2022-24 forecast.
Never combine lagged RAMS and BAS within one estimator. No production changes.
"""
import hashlib,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features,_geographic_error_metrics
D=Path("docs/data")
def source_data():
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    panel.kommun_kod=panel.kommun_kod.str.zfill(4)
    ram=pd.read_csv(D/"commuting_historical_rams.csv",dtype={"kommun_kod":str})
    ram.kommun_kod=ram.kommun_kod.str.zfill(4)
    ram=ram.loc[ram.year.between(2020,2021),["year","kommun_kod","outcommuting_share_pct"]].rename(columns={"outcommuting_share_pct":"commuting"})
    ram.year+=1
    flows=pd.read_csv(D/"commuting_flows_2020_2024.csv",dtype={"home":str,"work":str})
    totals=flows.groupby(["year","home"],as_index=False).employed.sum().rename(columns={"home":"kommun_kod","employed":"total"})
    local=flows.loc[flows.home==flows.work,["year","home","employed"]].rename(columns={"home":"kommun_kod","employed":"local"})
    bas=totals.merge(local,on=["year","kommun_kod"],validate="one_to_one")
    bas["commuting"]=100*(bas.total-bas.local)/bas.total
    bas=bas[["year","kommun_kod","commuting"]]
    bas.year+=1
    model=json.loads((D/"model.json").read_text())
    fair=model["fair_reselection_test"]
    required=list(dict.fromkeys(fair["incumbent_features"]+fair["eligible_pool"]+[model["target"],"commuting"]))
    out={}
    for source,raw,years in [("RAMS",ram,[2021,2022]),("BAS",bas,[2022,2023,2024])]:
        joined=panel.merge(raw,on=["year","kommun_kod"],how="inner",validate="one_to_one")
        joined=joined.loc[joined.year.isin(years)].dropna(subset=required).copy()
        count=joined.groupby("year").kommun_kod.nunique().to_dict()
        if any(count.get(y,0)!=290 for y in years):raise RuntimeError(f"{source} incomplete fair sample: {count}")
        out[source]=joined
    return out,fair,model["target"]

def run():
    data,fair,target=source_data()
    baseline=list(fair["incumbent_features"])
    pool=list(fair["eligible_pool"])
    result={"status":"annual_paired_comparison","features":len(baseline),
            "train_only_selection":True,"method_regimes_separate":True,
            "warning":"Earlier years have already been inspected; results are exploratory. A minimum of one preceding annual training cohort is needed; no 2021 forecast test.",
            "production_model_changed":False,"results":{}}
    for source,d in data.items():
        year_results={}
        for year in (sorted(d.year.unique())[1:]):
            train=d.loc[d.year<year]; test=d.loc[d.year==year]
            if len(train)<280 or len(test)!=290:raise RuntimeError(f"{source} {year} sample mismatch")
            selected=_select_features(train,pool,target)["selected"]
            preds={}
            features={"incumbent":baseline,"incumbent_plus":baseline+["commuting"],
                      "dynamic":selected,"dynamic_plus":list(dict.fromkeys(selected+["commuting"]))}
            for name,cols in features.items():
                est=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
                est.fit(train[cols],train[target])
                preds[name]=est.predict(test[cols])
            metrics={name:_geographic_error_metrics(test[target],p) for name,p in preds.items()}
            lulea=test.reset_index(drop=True).index[test.reset_index(drop=True).kommun_kod=="2580"].tolist()
            year_results[str(year)]={"training_years":sorted(int(y) for y in train.year.unique()),"n_train":len(train),
              "n_test":len(test),"selected_dynamic":selected,"metrics":metrics,
              "lulea":[{"actual":float(test.iloc[i][target]),**{name:float(p[i]) for name,p in preds.items()}} for i in lulea]}
            print(json.dumps({"source":source,"year":int(year),"rmse":{k:round(v["rmse"],3) for k,v in metrics.items()}},ensure_ascii=False),flush=True)
        result["results"][source]=year_results
    (D/"commuting_annual_paired_test.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":run()
