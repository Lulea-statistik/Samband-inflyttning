#!/usr/bin/env python3
"""Five-year chained Lulea population-level validation, 2020-2024.

Starts from actual population at end-2019, then recursively carries forward the
predicted population level. This tests cumulative drift in total population,
not only one-step annual change.

Important: component *rates* remain the historical rolling-origin forecasts for
each year. Thus this is a chained population-exposure validation, not a strict
single-origin 5-year forecast where every future predictor is itself forecast.

Candidates:
- current separate inflow/outflow baseline
- direct net migration 10y
- 75% direct-net / 25% separate blend

No production change.
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
years=[2020,2021,2022,2023,2024]

start_year=2019
start_pop=actual_pop[start_year]

def run(candidate):
    pred_prev=start_pop
    rows=[]
    for y in years:
        x=b[y]
        r=rr[y]
        birth_rate=float(x["birth_rate_pred"])
        death_rate=float(x["death_rate_pred"])
        residual=float(x["residual_pred"])
        if candidate=="baseline":
            migration_rate=float(x["inflow_rate_pred"])-float(x["outflow_rate_pred"])
        elif candidate=="direct_10y":
            migration_rate=float(r["direct_10y_rate"])
        elif candidate=="blend_75pct_direct":
            sep=float(x["inflow_rate_pred"])-float(x["outflow_rate_pred"])
            direct=float(r["direct_10y_rate"])
            migration_rate=0.25*sep+0.75*direct
        else:
            raise ValueError(candidate)

        births=birth_rate*pred_prev/100.0
        deaths=death_rate*pred_prev/1000.0
        migration=migration_rate*pred_prev/1000.0
        change=births-deaths+migration+residual
        pred_end=pred_prev+change
        actual=actual_pop[y]
        rows.append({
          "year":y,
          "predicted_population_start":pred_prev,
          "predicted_births":births,
          "predicted_deaths":deaths,
          "predicted_net_migration":migration,
          "predicted_residual":residual,
          "predicted_change":change,
          "predicted_population_end":pred_end,
          "actual_population_end":actual,
          "level_error_actual_minus_prediction":actual-pred_end,
          "absolute_level_error":abs(actual-pred_end),
          "relative_level_error_pct":100.0*(actual-pred_end)/actual
        })
        pred_prev=pred_end
    return rows

out={
 "status":"lulea_chained_population_level_validation_2020_2024",
 "production_changed":False,
 "validation_type":"chained rolling-origin population exposure",
 "strict_single_origin_5y_forecast":False,
 "important_limitation":"Each year's component rates come from that year's historical rolling-origin forecast; only the population level/exposure is recursively forecast from 2019 onward.",
 "start_year":start_year,
 "start_population_actual":start_pop,
 "years":years,
 "candidates":{}
}
for c in ["baseline","direct_10y","blend_75pct_direct"]:
    rows=run(c)
    errs=np.array([r["level_error_actual_minus_prediction"] for r in rows],float)
    final=rows[-1]
    out["candidates"][c]={
      "level_rmse_persons":float(np.sqrt(np.mean(errs*errs))),
      "level_mae_persons":float(np.mean(np.abs(errs))),
      "final_2024_actual_population":float(final["actual_population_end"]),
      "final_2024_predicted_population":float(final["predicted_population_end"]),
      "final_2024_error_persons":float(final["level_error_actual_minus_prediction"]),
      "final_2024_error_pct":float(final["relative_level_error_pct"]),
      "max_abs_level_error_persons":float(np.max(np.abs(errs))),
      "rows":rows
    }

out["ranking_level_rmse"]=sorted(
 [{"candidate":k,
   "level_rmse_persons":v["level_rmse_persons"],
   "level_mae_persons":v["level_mae_persons"],
   "final_2024_error_persons":v["final_2024_error_persons"],
   "max_abs_level_error_persons":v["max_abs_level_error_persons"]}
  for k,v in out["candidates"].items()],
 key=lambda z:(z["level_rmse_persons"],z["level_mae_persons"],abs(z["final_2024_error_persons"]))
)

(D/"lulea_chained_population_level_validation_2020_2024.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
