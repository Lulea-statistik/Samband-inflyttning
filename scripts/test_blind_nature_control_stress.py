#!/usr/bin/env python3
"""Fixed-window blind nature stress: predeclared control sets, same eligible years.

Historic feature availability is audited within the script; only tests with
at least three years of forecast evaluation will be interpreted.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_squared_error,mean_absolute_error
D=Path("docs/data")
NATURE="lag1_naturpraglad_mark_andel_land_pct"
BASE=["lag1_log_folkmangd","lag1_tatortsgrad_pct"]
EXTENSIONS={"density":["lag1_log_befolkningstathet_land"],
 "built_land":["lag1_bebyggd_anlagd_andel_land_pct"],
 "density_built":["lag1_log_befolkningstathet_land","lag1_bebyggd_anlagd_andel_land_pct"],
 "forest":["lag1_skogsmark_andel_land_pct"]}
def main():
 p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
 p.kommun_kod=p.kommun_kod.str.zfill(4)
 target=json.loads((D/"model.json").read_text())["target"]
 ids=set(p.loc[p.year.eq(2024)&p[target].notna(),"kommun_kod"])
 if len(ids)!=290:raise RuntimeError("Expected 290 municipalities")
 p=p.loc[p.kommun_kod.isin(ids)].copy()
 report={"status":"fixed_five_year_blind_nature_controls","training_years":5,"forecast_horizon":1,"candidate":NATURE,
   "control_designs":{},"production_model_changed":False}
 for name,extra in {"simple":[],**EXTENSIONS}.items():
  controls=BASE+extra;cols=[target,NATURE]+controls
  if any(c not in p for c in cols):
   report["control_designs"][name]={"missing":[c for c in cols if c not in p]};continue
  years=sorted(int(y) for y,t in p.groupby("year") if len(t)==290 and t[cols].notna().all().all())
  tests=[y for y in years if all(v in years for v in range(y-5,y))]
  item={"controls":controls,"complete_years":years,"forecast_years":tests,"forecasts":{}}
  for year in tests:
   tr=p[p.year.between(year-5,year-1)].sort_values(["year","kommun_kod"])
   te=p[p.year.eq(year)].sort_values("kommun_kod")
   if len(tr)!=1450 or len(te)!=290:raise RuntimeError("Invalid fixed sample")
   scores={}
   for key,features in (("reference",controls),("nature",controls+[NATURE])):
    m=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
    m.fit(tr[features],tr[target]);v=m.predict(te[features]);truth=te[target].to_numpy()
    lx=np.flatnonzero(te.kommun_kod.to_numpy()=="2580")[0]
    scores[key]={"rmse":float(np.sqrt(mean_squared_error(truth,v))),
      "mae":float(mean_absolute_error(truth,v)),
      "lulea_absolute_error":float(abs(truth[lx]-v[lx])),
      "coefficient":float(m.named_steps["ridgecv"].coef_[-1]) if key=="nature" else None}
   item["forecasts"][str(year)]={"scores":scores,"gain_rmse":scores["reference"]["rmse"]-scores["nature"]["rmse"]}
  if tests:
   item["summary"]={"n_years":len(tests),"improved_rmse":sum(v["gain_rmse"]>0 for v in item["forecasts"].values()),
      "mean_rmse_gain":float(np.mean([v["gain_rmse"] for v in item["forecasts"].values()])),
      "lulea_improved":sum(v["scores"]["nature"]["lulea_absolute_error"]<v["scores"]["reference"]["lulea_absolute_error"] for v in item["forecasts"].values())}
  report["control_designs"][name]=item
  print(f"{name}: {len(tests)} comparable years",flush=True)
 report["limitations"]=["Control blocks have different eligible forecast years; do not directly rank block RMSE unless matched on overlapping years.",
  "Potential strong collinearity between natural land and forest or developed land shares.",
  "Presence of a value in older periods does not verify historical comparability of its source definition.",
  "Reduced historical benchmark, not published full model."]
 (D/"blind_nature_five_year_control_stress.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
