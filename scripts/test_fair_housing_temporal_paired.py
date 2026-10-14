#!/usr/bin/env python3
"""Exploratory temporal paired comparison of housing proxies, never production."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from build_analysis import _geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"]
HOUSING={
    "finished_housing":"lag1_fardigstallda_bostader_per_1000",
    "housing_stock_change":"lag1_bostadsbestandsforandring_pct",
    "house_sales":"lag1_smahusforsaljningar_per_1000_smahus",
    "holiday_homes":"lag1_log_fritidshus_per_1000_inv",
}
def main():
    data,fair,target=source_data()
    df=data["BAS"].copy()
    chosen=["lag1_ekonomisk_standard_gap_pp","lag1_andel_studerande","lag1_kolada_utbetalt_lok_stod_kr_per_inv"]
    common=CONTROLS+chosen
    models={"structural_controls":CONTROLS,"common_base":common}
    for label,col in HOUSING.items():models[label]=common+[col]
    result={"status":"exploratory_paired_temporal_housing_comparison",
      "models":models,"data_years":[2022,2023,2024],"results":{},
      "production_changed":False,
      "limitations":[
       "Core variables were informed by prior inspected 2024 research; 2023 and 2024 are not independent, untouched tests.",
       "Two to three annual cohorts are inadequate to confirm temporal transportability.",
       "Housing data release timing has not been verified for historical forecast origins.",
       "A fixed common base and fixed ridge alpha are diagnostic choices, not an optimized forecasting model."]}
    for year in (2023,2024):
        train=df.loc[df.year<year].copy()
        test=df.loc[df.year.eq(year)].copy()
        if train.kommun_kod.nunique()!=290 or len(test)!=290:raise RuntimeError("Municipality coverage mismatch")
        results={}
        for name,features in models.items():
            if not train[features+[target]].notna().all().all() or not test[features+[target]].notna().all().all():
                raise RuntimeError(f"Incomplete feature data: {name}, {year}")
            estimator=make_pipeline(StandardScaler(),Ridge(alpha=50.0))
            estimator.fit(train[features],train[target])
            pred=estimator.predict(test[features])
            score=_geographic_error_metrics(test[target],pred)
            l=test.reset_index(drop=True).index[test.reset_index(drop=True).kommun_kod=="2580"]
            results[name]={"metrics":score,"lulea":[{"actual":float(test.iloc[i][target]),
                 "predicted":float(pred[i])} for i in l]}
        ref=results["common_base"]["metrics"]["rmse"]
        result["results"][str(year)]={"n_train":len(train),"n_test":len(test),
          "models":results,"delta_rmse_vs_common_base":{
              name:float(x["metrics"]["rmse"]-ref) for name,x in results.items()}}
        print(year,{k:round(v["metrics"]["rmse"],3) for k,v in results.items()},flush=True)
    (D/"fair_blind_housing_temporal_paired.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
