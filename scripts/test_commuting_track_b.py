#!/usr/bin/env python3
"""Track B: compare complete incumbent (27 features) + RAMS vs BAS outcommuting.

Paired overlap observations: source years 2020-2021 -> forecast 2021-2022.
Historical methodology sensitivity only; production models stay untouched.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _geographic_error_metrics

D=Path("docs/data")
def load():
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    panel["kommun_kod"]=panel.kommun_kod.str.zfill(4)
    ram=pd.read_csv(D/"commuting_historical_rams.csv",dtype={"kommun_kod":str})
    ram["kommun_kod"]=ram.kommun_kod.str.zfill(4)
    ram=ram.loc[ram.year.isin([2020,2021]),["year","kommun_kod","outcommuting_share_pct"]].rename(columns={"outcommuting_share_pct":"rams_share"})
    flows=pd.read_csv(D/"commuting_flows_2020_2024.csv",dtype={"home":str,"work":str})
    flows=flows.loc[flows.year.isin([2020,2021])]
    base=flows.groupby(["year","home"],as_index=False).employed.sum().rename(columns={"home":"kommun_kod","employed":"total"})
    local=flows.loc[flows.home==flows.work,["year","home","employed"]].rename(columns={"home":"kommun_kod","employed":"local"})
    bas=base.merge(local,on=["year","kommun_kod"],validate="one_to_one")
    bas["bas_share"]=100*(bas.total-bas.local)/bas.total
    bas=bas[["year","kommun_kod","bas_share"]]
    both=ram.merge(bas,on=["year","kommun_kod"],validate="one_to_one")
    if len(both)!=580 or both.duplicated(["year","kommun_kod"]).any():raise RuntimeError("RAMS/BAS overlap must be 580 municipality years")
    both["source_year"]=both.year
    both["year"]+=1
    merged=panel.merge(both,on=["year","kommun_kod"],validate="one_to_one")
    m=json.loads((D/"model.json").read_text())
    features=m["fair_reselection_test"]["incumbent_features"]
    target=m["target"]
    if len(features)!=27:raise RuntimeError(f"Expected complete 27-feature incumbent: {len(features)}")
    subset=merged.loc[merged.year.isin([2021,2022])].copy()
    subset=subset.dropna(subset=features+[target,"rams_share","bas_share"])
    if len(subset)!=580:raise RuntimeError(f"Expected 580 fully matched complete model rows, got {len(subset)}")
    return subset,features,target

def metrics(y,p):
    return _geographic_error_metrics(pd.Series(y),pd.Series(p))

def main():
    data,base,target=load()
    rows=[]
    # Geographic holdouts exclude the same municipalities in both years from fitting;
    # compare the identical held-out records, separate from temporal 2022 test.
    for variant, held_year in [("geo_2021",2021),("geo_2022",2022),("temporal_2022",2022)]:
        t=data.loc[data.year==held_year]
        universe=sorted(t.kommun_kod.unique())
        folds=range(5) if variant.startswith("geo") else [None]
        for fold in folds:
            if fold is None:
                train=data.loc[data.year<2022]
                test=t
            else:
                held={v for v in universe if int(hashlib.sha256(("validation-140:"+v).encode()).hexdigest()[:12],16)%5==fold}
                train=data.loc[~data.kommun_kod.isin(held)]
                test=t.loc[t.kommun_kod.isin(held)]
            if len(train)<280 or len(test)<25:raise RuntimeError(f"Inadequate {variant} fold {fold}: train={len(train)}, test={len(test)}")
            pred={}
            for name,extra in (("base",[]),("RAMS",["rams_share"]),("BAS",["bas_share"])):
                columns=base+extra
                estimator=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
                estimator.fit(train[columns],train[target])
                pred[name]=estimator.predict(test[columns])
            for idx,(_,record) in enumerate(test.iterrows()):
                rows.append({"split":variant,"fold":fold,"year":int(record.year),
                             "kommun_kod":record.kommun_kod,"actual":float(record[target]),
                             "rams_share":float(record.rams_share),"bas_share":float(record.bas_share),
                             **{name:float(values[idx]) for name,values in pred.items()}})
    result=pd.DataFrame(rows)
    summary={}
    for split,group in result.groupby("split"):
        if len(group)!=290:raise RuntimeError(f"Expected 290 test observations for {split}, got {len(group)}")
        summary[split]={"n":len(group),"scores":{key:metrics(group.actual,group[key]) for key in ("base","RAMS","BAS")},
                         "lulea":group.loc[group.kommun_kod=="2580"].to_dict("records"),
                         "mean_abs_rams_bas_share_gap_pp":float((group.rams_share-group.bas_share).abs().mean()),
                         "median_abs_rams_bas_share_gap_pp":float((group.rams_share-group.bas_share).abs().median())}
    report={"status":"track_b_comparison_complete",
            "overlap_source_years":[2020,2021],"forecast_years":[2021,2022],
            "full_model_features":len(base),"summary":summary,
            "training":"Geographic CV excludes test municipalities both years; temporal holdout trains on 2021 and tests 2022.",
            "caution":"Only 2 overlapping source years; 2022 temporal evaluation has only one earlier training year. Results are retrospective and cannot establish which methodology is universally better. 2023/24 have BAS but no paired RAMS.",
            "production_model_changed":False}
    (D/"commuting_track_b_comparison.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:{"rmse":{model:round(v["rmse"],3) for model,v in result["scores"].items()}} for k,result in summary.items()},ensure_ascii=False))

if __name__=="__main__":main()
