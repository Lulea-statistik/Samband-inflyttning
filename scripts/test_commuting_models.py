#!/usr/bin/env python3
"""Retrospective commuter-variable challenger test, paired geographic 2024 CV.
No changes to production. All feature selection is confined to training folds.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features, _geographic_error_metrics

D=Path("docs/data")
COMM=["lag1_outcommuting_share","lag1_incommuting_share","lag1_commuting_balance_per_1000_workers","lag1_outcommuting_share_change_pp"]

def main():
    flows=pd.read_csv(D/"commuting_flows_2020_2024.csv",dtype={"home":str,"work":str})
    if len(flows)!=420500 or flows.duplicated(["year","home","work"]).any():
        raise RuntimeError("Commuting matrix integrity failed")
    totals=flows.groupby(["year","home"],as_index=False).employed.sum().rename(columns={"home":"kommun_kod","employed":"residents_employed"})
    inside=flows.loc[flows.home==flows.work,["year","home","employed"]].rename(columns={"home":"kommun_kod","employed":"local_workers"})
    workplaces=flows.groupby(["year","work"],as_index=False).employed.sum().rename(columns={"work":"kommun_kod","employed":"workplace_employed"})
    c=totals.merge(inside,on=["year","kommun_kod"]).merge(workplaces,on=["year","kommun_kod"])
    if len(c)!=1450: raise RuntimeError("Missing municipality-year in derived commuters")
    c["outcommuting_share"]=100*(c.residents_employed-c.local_workers)/c.residents_employed.replace(0,np.nan)
    c["incommuting_share"]=100*(c.workplace_employed-c.local_workers)/c.workplace_employed.replace(0,np.nan)
    c["commuting_balance_per_1000_workers"]=1000*(c.workplace_employed-c.residents_employed)/c.residents_employed.replace(0,np.nan)
    c=c.sort_values(["kommun_kod","year"])
    c["outcommuting_share_change_pp"]=c.groupby("kommun_kod").outcommuting_share.diff()
    for base in ("outcommuting_share","incommuting_share","commuting_balance_per_1000_workers","outcommuting_share_change_pp"):
        c["lag1_"+base]=c.groupby("kommun_kod")[base].shift(1)
    # The lead shifts are intentional: panel[year] receives latest prior year values.
    # Existing year t commuter aggregate is appended onto panel t+1.
    derived=c[["kommun_kod","year"]+COMM].copy()
    derived["year"]+=1
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    panel["kommun_kod"]=panel.kommun_kod.str.zfill(4)
    d=panel.merge(derived,on=["kommun_kod","year"],how="left",validate="many_to_one")
    model=json.loads((D/"model.json").read_text())
    fair=model["fair_reselection_test"]
    baseline=list(fair["incumbent_features"])
    pool=list(fair["eligible_pool"])
    target=model["target"]
    d=d.loc[d.year.between(2022,2024)].copy()
    # Use only commuters with at least two available time observations.
    # Because commuting was already lagged within original years before merging
    # to forecast years, the actual predictor date is TWO years before forecast.
    # This is conservative and explicitly recorded.
    required=list(dict.fromkeys(baseline+pool+COMM+[target]))
    d=d.dropna(subset=required)
    rows=[]
    for year in (2023,2024):
        test=d.loc[d.year==year]
        train=d.loc[d.year<year]
        if len(train)<280 or len(test)<250:
            rows.append({"year":year,"status":"insufficient_training","n_train":len(train),"n_test":len(test)})
            continue
        selected=_select_features(train,pool,target)["selected"]
        selected_comm=_select_features(train,pool+COMM,target)["selected"]
        specs={"incumbent":baseline,"incumbent_plus_commuting":baseline+COMM,"dynamic":selected,"dynamic_plus_commuting":selected_comm}
        def pred(fs):
            m=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            m.fit(train[fs],train[target])
            return m.predict(test[fs])
        ps={k:pred(fs) for k,fs in specs.items()}
        vals={k:_geographic_error_metrics(test[target],v) for k,v in ps.items()}
        rows.append({"year":year,"status":"tested","n_train":len(train),"n_test":len(test),"metrics":vals,"selected_dynamic":selected,"selected_dynamic_with_commuting":selected_comm,
                     "commuting_selected":[x for x in selected_comm if x in COMM],
                     "lulea": [{**{"actual":float(test.iloc[i][target])},**{k:float(p[i]) for k,p in ps.items()}} for i in range(len(test)) if test.iloc[i].kommun_kod=="2580"]})
    # Municipality-separated 2024 folds, train 2022-23 on other municipality codes.
    allrows=[]
    universe=sorted(d.loc[d.year==2024].kommun_kod.unique())
    for fold in range(5):
        held=[v for v in universe if int(hashlib.sha256(("validation-140:"+v).encode()).hexdigest()[:12],16)%5==fold]
        train=d.loc[d.year.lt(2024)&~d.kommun_kod.isin(held)]
        test=d.loc[d.year.eq(2024)&d.kommun_kod.isin(held)]
        if len(train)<300 or len(test)<25: raise RuntimeError("Inadequate CV fold coverage")
        chosen=_select_features(train,pool,target)["selected"]
        chosen_comm=_select_features(train,pool+COMM,target)["selected"]
        specs={"incumbent":baseline,"incumbent_plus_commuting":baseline+COMM,"dynamic":chosen,"dynamic_plus_commuting":chosen_comm}
        predictions={}
        for name,fs in specs.items():
            m=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            m.fit(train[fs],train[target])
            predictions[name]=m.predict(test[fs])
        for i,(_,row) in enumerate(test.iterrows()):
            allrows.append({"year":2024,"kommun_kod":row.kommun_kod,"actual":float(row[target]),**{name:float(pr[i]) for name,pr in predictions.items()}})
    ev=pd.DataFrame(allrows)
    if ev.kommun_kod.nunique()!=len(universe):raise RuntimeError("Fold predictions incomplete")
    country={k:_geographic_error_metrics(ev.actual,ev[k]) for k in ("incumbent","incumbent_plus_commuting","dynamic","dynamic_plus_commuting")}
    report={"status":"retrospective_commuting_challenger_complete","years_raw":[2020,2021,2022,2023,2024],"candidate_predictors":COMM,
            "predictor_timing":"Commuting predictor for forecast t currently originates from t-2, due to sequential shift and year alignment; first variation predictor needs 2020 and 2021 observations.",
            "note":"Exploratory: 2024 repeatedly used in research; no production promotion. Monthly commuting/trips are not observed.",
            "coverage":{str(y):int(v) for y,v in d.groupby("year").kommun_kod.nunique().items()},
            "temporal":rows,"geographic_cv_2024":country,"lulea_cv_2024":ev.loc[ev.kommun_kod=="2580"].to_dict("records"),"production_model_changed":False}
    (D/"commuting_model_test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":report["status"],"temporal":[{"year":r["year"],"status":r["status"]} for r in rows],"geographic_cv_rmse":{k:v["rmse"] for k,v in country.items()}},ensure_ascii=False))

if __name__=="__main__":
    main()
