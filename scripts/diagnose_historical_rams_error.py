#!/usr/bin/env python3
"""Decompose historical 2015-2018 RAMS-era forecast errors (research only)."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from audit_rams_bas_historical import CORE
D=Path("docs/data")
def desc(s):
    a=np.asarray(s,float)
    return {"mean":float(a.mean()),"sd":float(a.std()),"p05":float(np.quantile(a,.05)),
            "median":float(np.median(a)),"p95":float(np.quantile(a,.95))}
def main():
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    panel.kommun_kod=panel.kommun_kod.str.zfill(4)
    target=json.loads((D/"model.json").read_text())["target"]
    p=panel.loc[panel.year.between(2013,2018)].dropna(subset=CORE+[target]).copy()
    output={"status":"historical_error_decomposition","source":"historical common-feature panel",
        "model":"six-variable core RidgeCV; rolling-origin",
        "production_model_changed":False,"years":{}}
    for year in range(2015,2019):
        train=p.loc[p.year.between(2013,year-1)].copy()
        test=p.loc[p.year.eq(year)].copy()
        if len(train)!=(year-2013)*290 or len(test)!=290:
            raise RuntimeError(f"Incomplete comparable panel {year}: {len(train)}/{len(test)}")
        fit=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
        fit.fit(train[CORE],train[target])
        test["pred"]=fit.predict(test[CORE])
        test["error"]=test["pred"]-test[target]
        test["abs_error"]=test.error.abs()
        test["sq_error"]=test.error**2
        records=[]
        for _,row in test.nlargest(12,"abs_error").iterrows():
            records.append({"kommun_kod":str(row.kommun_kod),"actual":float(row[target]),
                "pred":float(row.pred),"signed_error":float(row.error),
                "squared_error_share_pct":float(row.sq_error/test.sq_error.sum()*100)})
        output["years"][str(year)]={
            "n":len(test),"rmse":float(np.sqrt(test.sq_error.mean())),
            "mae":float(test.abs_error.mean()),"bias_pred_minus_actual":float(test.error.mean()),
            "actual_distribution":desc(test[target]),"prediction_distribution":desc(test.pred),
            "error_distribution":desc(test.error),"error_sd":float(test.error.std(ddof=0)),
            "top_10_squared_error_share_pct":float(test.nlargest(10,"sq_error").sq_error.sum()/test.sq_error.sum()*100),
            "rmse_excluding_largest_5pct_errors":float(np.sqrt(test.nsmallest(275,"abs_error").sq_error.mean())),
            "largest_errors":records,"alpha":float(fit.named_steps["ridgecv"].alpha_)}
        print(json.dumps({"year":year,"rmse":output["years"][str(year)]["rmse"],
          "bias":output["years"][str(year)]["bias_pred_minus_actual"]}),flush=True)
    output["limitations"]="Retrospective diagnostic; cannot establish causal source of temporal deterioration."
    (D/"commuting_historical_error_decomposition.json").write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
