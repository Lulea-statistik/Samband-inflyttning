#!/usr/bin/env python3
"""One predeclared historical calibration test; then return to other variable themes.

For each forecast year t, obtain prior-year (t-1) out-of-sample bias from a
model fit on years strictly before t-1. Refit baseline through t-1, then
subtract prior OOS bias. No current-year outcomes in calibration.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from audit_rams_bas_historical import CORE
D=Path("docs/data")
def model():
    return make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
def metrics(y,p):
    e=np.asarray(p)-np.asarray(y)
    return {"rmse":float(np.sqrt(np.mean(e*e))),"mae":float(np.mean(np.abs(e))),
            "bias_pred_minus_actual":float(np.mean(e))}
def main():
    p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    p.kommun_kod=p.kommun_kod.str.zfill(4)
    target=json.loads((D/"model.json").read_text())["target"]
    p=p.loc[p.year.between(2013,2018)].dropna(subset=CORE+[target]).copy()
    out={"status":"last_historical_calibration_experiment","method":"Previous-year rolling-origin OOS bias correction",
         "models":["baseline","previous_oos_bias_correction"],
         "production_model_changed":False,"results":{}}
    for year in (2015,2016,2017,2018):
        old_train=p.loc[p.year.between(2013,year-2)]
        old_test=p.loc[p.year.eq(year-1)]
        train=p.loc[p.year.between(2013,year-1)]
        test=p.loc[p.year.eq(year)]
        if len(old_train)<290 or len(old_test)!=290 or len(test)!=290:raise RuntimeError("Incomplete annual sample")
        m=model().fit(old_train[CORE],old_train[target])
        old_pred=m.predict(old_test[CORE])
        old_bias=float(np.mean(old_pred-old_test[target].to_numpy()))
        current=model().fit(train[CORE],train[target])
        pred=current.predict(test[CORE])
        calibrated=pred-old_bias
        out["results"][str(year)]={"n_test":len(test),"prior_forecast_year":year-1,
          "prior_year_out_of_sample_bias":old_bias,
          "baseline":metrics(test[target],pred),
          "previous_oos_bias_correction":metrics(test[target],calibrated),
          "lulea":{}}
        lx=np.flatnonzero(test.kommun_kod.to_numpy()=="2580")
        if len(lx)==1:
            k=int(lx[0]);out["results"][str(year)]["lulea"]={
               "actual":float(test.iloc[k][target]),"baseline":float(pred[k]),
               "calibrated":float(calibrated[k])}
        print(json.dumps({"year":year,"previous_bias":round(old_bias,3),
          "baseline_rmse":round(out["results"][str(year)]["baseline"]["rmse"],3),
          "calibrated_rmse":round(out["results"][str(year)]["previous_oos_bias_correction"]["rmse"],3)}),flush=True)
    out["limitations"]=["Six common historical features only; not a prospective test of the modern model.",
      "Calibration is deliberately fixed at 100% previous-year OOS bias, not tuned on test outcomes.",
      "Historical years already inspected; results exploratory."]
    (D/"commuting_historical_last_calibration_test.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
