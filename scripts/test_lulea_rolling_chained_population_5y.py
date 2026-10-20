#!/usr/bin/env python3
"""Rolling chained 5-year Lulea population-level validation across multiple start years.

Windows:
- 2017-2021, starting from actual 2016 population
- 2018-2022, starting from actual 2017 population
- 2019-2023, starting from actual 2018 population
- 2020-2024, starting from actual 2019 population

Candidates:
- baseline separate inflow/outflow
- direct net 10y
- 75% direct-net / 25% baseline

Each year's component rates are historical rolling-origin forecasts for that year.
Population level/exposure is chained recursively within each 5-year window.
Research only; no production change.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
base=json.loads((D/"lulea_full_component_historical_backtest.json").read_text(encoding="utf-8"))
rob=json.loads((D/"lulea_direct_net_full_balance_robustness.json").read_text(encoding="utf-8"))

p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
lu=p[p.kommun_kod.eq("2580")][["year","folkmangd"]].copy()
actual_pop={int(r.year):float(r.folkmangd) for r in lu.itertuples(index=False)}

b={int(r["year"]):r for r in base["years"]}
rr={int(r["year"]):r for r in rob["years"]}

windows=[
 {"start_year":2016,"forecast_years":[2017,2018,2019,2020,2021]},
 {"start_year":2017,"forecast_years":[2018,2019,2020,2021,2022]},
 {"start_year":2018,"forecast_years":[2019,2020,2021,2022,2023]},
 {"start_year":2019,"forecast_years":[2020,2021,2022,2023,2024]},
]
candidates=["baseline","direct_10y","blend_75pct_direct"]

def migration_rate(candidate,y):
    x=b[y]; r=rr[y]
    sep=float(x["inflow_rate_pred"])-float(x["outflow_rate_pred"])
    direct=float(r["direct_10y_rate"])
    if candidate=="baseline": return sep
    if candidate=="direct_10y": return direct
    if candidate=="blend_75pct_direct": return 0.25*sep+0.75*direct
    raise ValueError(candidate)

def run_window(start_year,years,candidate):
    pred_prev=actual_pop[start_year]
    rows=[]
    for y in years:
        x=b[y]
        birth_rate=float(x["birth_rate_pred"])
        death_rate=float(x["death_rate_pred"])
        residual=float(x["residual_pred"])
        mig_rate=migration_rate(candidate,y)

        births=birth_rate*pred_prev/100.0
        deaths=death_rate*pred_prev/1000.0
        migration=mig_rate*pred_prev/1000.0
        change=births-deaths+migration+residual
        pred_end=pred_prev+change
        actual=actual_pop[y]
        rows.append({
          "year":y,
          "predicted_population_start":pred_prev,
          "predicted_change":change,
          "predicted_population_end":pred_end,
          "actual_population_end":actual,
          "level_error_actual_minus_prediction":actual-pred_end,
          "absolute_level_error":abs(actual-pred_end),
          "relative_level_error_pct":100.0*(actual-pred_end)/actual
        })
        pred_prev=pred_end
    errs=np.array([r["level_error_actual_minus_prediction"] for r in rows],float)
    final=rows[-1]
    return {
      "level_rmse_persons":float(np.sqrt(np.mean(errs*errs))),
      "level_mae_persons":float(np.mean(np.abs(errs))),
      "max_abs_level_error_persons":float(np.max(np.abs(errs))),
      "final_error_persons":float(final["level_error_actual_minus_prediction"]),
      "final_error_pct":float(final["relative_level_error_pct"]),
      "rows":rows
    }

out={
 "status":"lulea_rolling_chained_population_validation_5y",
 "production_changed":False,
 "validation_type":"multiple chained rolling-origin population-level windows",
 "strict_single_origin_multiyear_forecast":False,
 "windows":[],
 "aggregate":{}
}

for w in windows:
    wr={
      "start_year":w["start_year"],
      "start_population_actual":actual_pop[w["start_year"]],
      "forecast_years":w["forecast_years"],
      "candidates":{}
    }
    for c in candidates:
        wr["candidates"][c]=run_window(w["start_year"],w["forecast_years"],c)
    wr["ranking_level_rmse"]=sorted(
      [{"candidate":c,
        "level_rmse_persons":wr["candidates"][c]["level_rmse_persons"],
        "level_mae_persons":wr["candidates"][c]["level_mae_persons"],
        "max_abs_level_error_persons":wr["candidates"][c]["max_abs_level_error_persons"],
        "final_error_persons":wr["candidates"][c]["final_error_persons"]}
       for c in candidates],
      key=lambda z:(z["level_rmse_persons"],z["level_mae_persons"],z["max_abs_level_error_persons"])
    )
    out["windows"].append(wr)

for c in candidates:
    rmses=[w["candidates"][c]["level_rmse_persons"] for w in out["windows"]]
    maes=[w["candidates"][c]["level_mae_persons"] for w in out["windows"]]
    finals=[abs(w["candidates"][c]["final_error_persons"]) for w in out["windows"]]
    wins=sum(1 for w in out["windows"] if w["ranking_level_rmse"][0]["candidate"]==c)
    out["aggregate"][c]={
      "windows":len(rmses),
      "mean_window_rmse":float(np.mean(rmses)),
      "median_window_rmse":float(np.median(rmses)),
      "mean_window_mae":float(np.mean(maes)),
      "mean_abs_final_error":float(np.mean(finals)),
      "max_window_rmse":float(np.max(rmses)),
      "window_wins":int(wins)
    }

out["aggregate_ranking"]=sorted(
 [{"candidate":c,**v} for c,v in out["aggregate"].items()],
 key=lambda z:(z["mean_window_rmse"],z["mean_window_mae"],z["mean_abs_final_error"])
)

(D/"lulea_rolling_chained_population_validation_5y.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
