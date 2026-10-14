#!/usr/bin/env python3
"""Fair same-sample tests of lagged employment level versus annual growth.

BAS 2023/24 rolling tests. Train-only dynamic selection; level formed from
previous calendar year, no outcome leakage. Not prospective confirmation.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
GROWTH="lag1_sysselsatta_bostad_forandring_pct"
CONTROL="lag1_andel_fa_arbetsplatser_i_egen_kommun"
FORMS={"reference":[],"level":["log_employment_level"],"growth":[GROWTH],
       "level_and_growth":["log_employment_level",GROWTH]}
def main():
    sources,fair,target=source_data()
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    panel.kommun_kod=panel.kommun_kod.str.zfill(4)
    level=panel[["year","kommun_kod","sysselsatta_bostad_medel"]].copy()
    level.year+=1
    level=level.rename(columns={"sysselsatta_bostad_medel":"employment_level"})
    d=sources["BAS"].merge(level,on=["year","kommun_kod"],how="left",validate="one_to_one")
    if (d.employment_level.isna().any() or (d.employment_level<=0).any()):
        raise RuntimeError("Missing or invalid lagged employment level")
    d["log_employment_level"]=np.log(d.employment_level)
    pool=list(fair["eligible_pool"])
    out={"status":"exploratory_employment_level_growth_comparison",
         "level_definition":"log(previous calendar year's mean employment by place of residence)",
         "source":"BAS","test_years":[2023,2024],"production_model_changed":False,
         "models":FORMS,"results":{}}
    for yr in (2023,2024):
        train=d.loc[d.year<yr].copy();test=d.loc[d.year==yr].copy()
        cm=float(train.commuting.mean());jm=float(train[CONTROL].mean())
        for fr in (train,test):
            fr["commute_c"]=fr.commuting-cm
            fr["commute_jobs"]=fr.commute_c*(fr[CONTROL]-jm)
        eligible=[x for x in pool if x in train and train[x].notna().all() and test[x].notna().all()]
        selected=_select_features(train,eligible,target)["selected"]
        baseline=list(dict.fromkeys(selected+["commute_c","commute_jobs"]))
        report={}
        for name,added in FORMS.items():
            cols=list(dict.fromkeys(baseline+added))
            model=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            model.fit(train[cols],train[target])
            pred=model.predict(test[cols])
            stats=_geographic_error_metrics(test[target],pred)
            lidx=np.flatnonzero(test.kommun_kod.to_numpy()=="2580")
            report[name]={"rmse":float(stats["rmse"]),"mae":float(stats["mae"]),
                          "lulea_pred":float(pred[lidx[0]]),"lulea_actual":float(test.iloc[lidx[0]][target]),
                          "growth_coefficient":float(model.named_steps["ridgecv"].coef_[cols.index(GROWTH)]) if GROWTH in cols else None,
                          "level_coefficient":float(model.named_steps["ridgecv"].coef_[cols.index("log_employment_level")]) if "log_employment_level" in cols else None}
        out["results"][str(yr)]={"n_train":len(train),"n_test":len(test),"selected_features":len(selected),"comparisons":report}
        print(json.dumps({"year":yr,"rmse":{k:round(v["rmse"],3) for k,v in report.items()}},ensure_ascii=False),flush=True)
    out["caution"]="Level is a structural population-size proxy. 2023 and 2024 previously repeatedly inspected; no independent evaluation."
    (D/"commuting_employment_level_growth_test.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
