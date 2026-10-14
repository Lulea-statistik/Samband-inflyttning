#!/usr/bin/env python3
"""Retrospective 3-year fixed-window diagnostic; NOT an as-of forecast or production test."""
import csv,json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
D=Path("docs/data")
MODEL=json.loads((D/"model.json").read_text(encoding="utf-8"))
TARGET=MODEL["target"]
BASE=["lag1_log_folkmangd","lag1_tatortsgrad_pct"]
FORMS={"base":BASE,"residence":BASE+["growth_residence"],"workplace":BASE+["growth_workplace"],
       "both":BASE+["growth_residence","growth_workplace"]}
TEST_YEARS=[2009,2010,2011,2016,2017,2018,2019,2024]
def main():
    p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    p.kommun_kod=p.kommun_kod.str.zfill(4)
    a=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
    a.kommun_kod=a.kommun_kod.str.zfill(4)
    a=a.rename(columns={"target_year":"year"})
    if a.duplicated(["year","kommun_kod","dimension"]).any():raise RuntimeError("Duplicated lag observations")
    wide=a.pivot(index=["year","kommun_kod"],columns="dimension",values="growth_pct").reset_index()
    wide=wide.rename(columns={"residence":"growth_residence","workplace":"growth_workplace"})
    data=p.merge(wide,on=["year","kommun_kod"],how="inner",validate="one_to_one")
    for col in BASE+[TARGET,"growth_residence","growth_workplace"]:
        data[col]=pd.to_numeric(data[col],errors="coerce")
    results={"status":"retrospective_three_year_fixed_model_exploratory","target":TARGET,
       "base_features":BASE,"models":FORMS,"ridge_alpha":10.,
       "test_years":TEST_YEARS,"production_changed":False,"results":{},"limitations":[
       "Historical panel and BAS-calibration provenance are retrospective, not genuine publication-vintage-safe forecasting.",
       "2024 has been repeatedly inspected; do not use it for model choice.",
       "No tuning or feature selection on the test year. Fixed alpha and fixed controls.",
       "Within-regime percent growth is invariant to time-constant BAS/RAMS level factors.",
       "Tests share historical observations and are not independent confirmation." ]}
    for yr in TEST_YEARS:
        yrs=list(range(yr-3,yr))
        train=data.loc[data.year.isin(yrs)].dropna(subset=BASE+[TARGET,"growth_residence","growth_workplace"])
        test=data.loc[data.year==yr].dropna(subset=BASE+[TARGET,"growth_residence","growth_workplace"])
        if sorted(train.year.unique().tolist())!=yrs or len(train)!=870 or len(test)!=290:
            raise RuntimeError(f"Coverage mismatch {yr}: {train.year.unique()} {len(train)} {len(test)}")
        report={}
        for name,cols in FORMS.items():
            fit=make_pipeline(StandardScaler(),Ridge(alpha=10.0))
            fit.fit(train[cols],train[TARGET])
            pred=fit.predict(test[cols])
            error=test[TARGET].to_numpy()-pred
            loc=np.flatnonzero(test.kommun_kod.to_numpy()=="2580")
            report[name]={"rmse":float(np.sqrt(np.mean(error**2))),"mae":float(np.mean(np.abs(error))),
              "lulea_actual":float(test.iloc[loc[0]][TARGET]),"lulea_pred":float(pred[loc[0]])}
        results["results"][str(yr)]={"n_train":len(train),"n_test":len(test),"models":report,
          "previously_inspected_holdout":yr==2024}
        print(yr,{k:round(v["rmse"],3) for k,v in report.items()},flush=True)
    (D/"employment_historical_fixed_regression_test.json").write_text(
        json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
