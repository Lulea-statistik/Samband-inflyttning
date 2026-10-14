#!/usr/bin/env python3
"""Historic RAMS-only interaction diagnostic, 2015-2018 rolling origins.

The modern FA-region workplace share is unavailable historically. Instead use
RAMS workplace-to-resident employment ratio (local+incoming)/(local+outgoing),
a different, explicitly labelled historical local labor-market moderator.
No RAMS/BAS mixing. Historical 6-feature core only. Research, not production.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV
from build_analysis import _geographic_error_metrics
from audit_rams_bas_historical import CORE
D=Path("docs/data")
FORMS={"core":CORE,
       "core_structure":CORE+["job_balance_c"],
       "core_structure_linear":CORE+["job_balance_c","commute_c"],
       "core_structure_interaction":CORE+["job_balance_c","commute_c","commute_x_job_balance"]}
def main():
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    panel.kommun_kod=panel.kommun_kod.str.zfill(4)
    rams=pd.read_csv(D/"commuting_historical_rams.csv",dtype={"kommun_kod":str})
    rams.kommun_kod=rams.kommun_kod.str.zfill(4)
    required=["outcommuting_share_pct","incoming","outgoing","local"]
    if any(v not in rams for v in required):raise RuntimeError("Historical RAMS count columns missing")
    past=rams.loc[rams.year.between(2012,2017),["year","kommun_kod"]+required].copy()
    past["resident_employed"]=past["local"]+past["outgoing"]
    past["workplace_employed"]=past["local"]+past["incoming"]
    if (past.resident_employed<=0).any():raise RuntimeError("Nonpositive employment")
    past["job_balance"]=past.workplace_employed/past.resident_employed
    past["commuting"]=past.outcommuting_share_pct
    past.year+=1
    d=panel.merge(past[["year","kommun_kod","commuting","job_balance"]],
        on=["year","kommun_kod"],validate="one_to_one")
    target=json.loads((D/"model.json").read_text())["target"]
    out={"status":"historic_rams_interaction_exploration","source":"RAMS pre-2019",
        "historical_moderator":"ratio of jobs located in municipality to employed municipality residents, from RAMS local/incoming/outgoing counts",
        "moderator_not_equivalent_to_modern_fa_region_share":True,
        "historical_core_features":CORE,"production_model_changed":False,"results":{}}
    for yr in [2015,2016,2017,2018]:
        tr=d.loc[d.year.between(2013,yr-1)].dropna(subset=CORE+[target,"commuting","job_balance"]).copy()
        te=d.loc[d.year==yr].dropna(subset=CORE+[target,"commuting","job_balance"]).copy()
        if len(te)!=290 or len(tr)<580:raise RuntimeError(f"Incomplete comparable RAMS sample {yr}")
        cm=float(tr.commuting.mean());bm=float(tr.job_balance.mean())
        for frame in [tr,te]:
            frame["commute_c"]=frame.commuting-cm
            frame["job_balance_c"]=frame.job_balance-bm
            frame["commute_x_job_balance"]=frame.commute_c*frame.job_balance_c
        scores={};preds={}
        for name,cols in FORMS.items():
            fit=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            fit.fit(tr[cols],tr[target]);p=fit.predict(te[cols])
            m=_geographic_error_metrics(te[target],p)
            scores[name]={"rmse":float(m["rmse"]),"mae":float(m["mae"])}
            preds[name]=p
        q=pd.qcut(te.commuting.rank(method="first"),4,labels=["Q1","Q2","Q3","Q4"])
        groups=[]
        for v in ("Q1","Q2","Q3","Q4"):
            ix=(q==v).to_numpy()
            groups.append({"group":v,"n":int(ix.sum()),"rmse":{
                name:float(_geographic_error_metrics(te[target].to_numpy()[ix],p[ix])["rmse"]) for name,p in preds.items()}})
        lulea=np.flatnonzero(te.kommun_kod.to_numpy()=="2580")
        out["results"][str(yr)]={"n_train":len(tr),"n_test":len(te),"train_years":sorted(int(x) for x in tr.year.unique()),
            "scores":scores,"quartiles":groups,"lulea":[{
               "actual":float(te.iloc[i][target]),"job_balance":float(te.iloc[i].job_balance),
               **{name:float(p[i]) for name,p in preds.items()}} for i in lulea]}
        print(json.dumps({"year":yr,"rmse":{k:round(v["rmse"],4) for k,v in scores.items()}},ensure_ascii=False),flush=True)
    out["limitations"]=["Historical moderator is job balance, not the modern FA-region workplace proportion. This is a conceptual interaction test, not direct replication.",
        "Historical models have only six common covariates, not current 27-feature incumbent.",
        "Older RAMS source regime only (before 2019 break); no BAS pooling.","Results retrospective and exploratory."]
    (D/"commuting_historical_rams_interaction.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
