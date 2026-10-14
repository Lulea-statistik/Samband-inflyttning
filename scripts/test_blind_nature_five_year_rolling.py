#!/usr/bin/env python3
"""Nine annual one-year-ahead evaluations with fixed five-year training history.

Research only. Compare a fixed demographically blind geographic/population
baseline to the exact same baseline plus natural land share.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error,mean_squared_error
D=Path("docs/data")
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct"]
NATURE="lag1_naturpraglad_mark_andel_land_pct"
YEARS=list(range(2016,2025))
WINDOW=5
def main():
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    panel["kommun_kod"]=panel.kommun_kod.str.zfill(4)
    meta=json.loads((D/"model.json").read_text())
    target=meta["target"]
    valid=panel.loc[panel.year.eq(2024)&panel[target].notna(),"kommun_kod"].unique()
    if len(valid)!=290:raise RuntimeError(f"Expected 290 municipalities, got {len(valid)}")
    panel=panel[panel.kommun_kod.isin(valid)].copy()
    cols=[target]+CONTROLS+[NATURE]
    result={"status":"blind_nature_fixed_five_year_history",
      "target":target,"training_window_years":WINDOW,"forecast_horizon_years":1,
      "model_scope":"reduced historical structural control set, not full published blind model",
      "controls":CONTROLS,"candidate":NATURE,"forecast_years":YEARS,
      "production_model_changed":False,"years":{}}
    for year in YEARS:
        tr=panel[panel.year.between(year-WINDOW,year-1)].copy()
        te=panel[panel.year.eq(year)].copy()
        if len(tr)!=290*WINDOW or len(te)!=290:raise RuntimeError(f"Not a full panel {year}")
        if tr[cols].isna().any().any() or te[cols].isna().any().any():
            raise RuntimeError(f"Missing common sample for year {year}")
        tr=tr.sort_values(["year","kommun_kod"])
        te=te.sort_values("kommun_kod")
        truth=te[target].to_numpy()
        tests={}
        for name,predictors in {"reference":CONTROLS,"nature":CONTROLS+[NATURE]}.items():
            est=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            est.fit(tr[predictors],tr[target]);pred=est.predict(te[predictors])
            li=np.flatnonzero(te.kommun_kod.to_numpy()=="2580")
            tests[name]={"rmse":float(np.sqrt(mean_squared_error(truth,pred))),
              "mae":float(mean_absolute_error(truth,pred)),
              "lulea_pred":float(pred[li[0]]),"lulea_actual":float(truth[li[0]]),
              "nature_standardized_coefficient":float(est.named_steps["ridgecv"].coef_[-1]) if name=="nature" else None}
        result["years"][str(year)]={"n_train":len(tr),"n_test":len(te),
          "train_years":list(range(year-WINDOW,year)),"scores":tests,
          "rmse_gain":tests["reference"]["rmse"]-tests["nature"]["rmse"],
          "mae_gain":tests["reference"]["mae"]-tests["nature"]["mae"]}
        print(f"{year}: baseline {tests['reference']['rmse']:.3f}, nature {tests['nature']['rmse']:.3f}",flush=True)
    gains=[v["rmse_gain"] for v in result["years"].values()]
    result["summary"]={"n_forecast_years":len(YEARS),"years_improved":int(sum(v>0 for v in gains)),
      "mean_annual_rmse_gain":float(np.mean(gains)),
      "median_annual_rmse_gain":float(np.median(gains)),
      "lulea_years_improved":int(sum(
        abs(v["scores"]["nature"]["lulea_actual"]-v["scores"]["nature"]["lulea_pred"]) <
        abs(v["scores"]["reference"]["lulea_actual"]-v["scores"]["reference"]["lulea_pred"])
        for v in result["years"].values()))}
    result["limitations"]=["Natural land share historical definition and values must be independently checked for method continuity.",
      "Two-control model is deliberately simplified and cannot warrant production promotion.",
      "All years were historically available; results are retrospective research, not unseen future validation."]
    (D/"blind_nature_five_year_rolling.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
