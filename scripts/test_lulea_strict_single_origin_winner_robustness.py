#!/usr/bin/env python3
"""Robustness audit for the winning strict single-origin fading rule.

Winner from focused grid:
- birth fade 0.0
- death fade 0.0
- migration fade 1.0
- residual fade 1.0

Compare against nearby challengers by origin and horizon:
A winner 0/0/1/1
B residual slower 0/0/1/0.5
C migration slower 0/0/0.7/1
D birth mild fade 0.3/0/1/1
E death mild fade 0/0.3/1/1

No future observed component values are used within paths.
Research only; no production change.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
grid=json.loads((D/"lulea_strict_single_origin_focused_fading_grid.json").read_text(encoding="utf-8"))

specs={
 "winner_0_0_1_1":(0.0,0.0,1.0,1.0),
 "residual_0_5":(0.0,0.0,1.0,0.5),
 "migration_0_7":(0.0,0.0,0.7,1.0),
 "birth_0_3":(0.3,0.0,1.0,1.0),
 "death_0_3":(0.0,0.3,1.0,1.0),
}
rows=pd.DataFrame(grid["rows"])
def match_tuple(r,t):
    return (
      abs(float(r.fade_birth)-t[0])<1e-12 and
      abs(float(r.fade_death)-t[1])<1e-12 and
      abs(float(r.fade_migration)-t[2])<1e-12 and
      abs(float(r.fade_residual)-t[3])<1e-12
    )

out={
 "status":"lulea_strict_single_origin_winner_robustness",
 "production_changed":False,
 "strict_single_origin_multiyear_forecast":True,
 "specs":{},
 "pairwise_vs_winner":{}
}
for name,t in specs.items():
    g=rows[rows.apply(lambda r: match_tuple(r,t),axis=1)].copy()
    x=g.error_actual_minus_prediction.to_numpy(float)
    out["specs"][name]={
      "params":{
        "fade_birth":t[0],"fade_death":t[1],
        "fade_migration":t[2],"fade_residual":t[3]
      },
      "n":int(len(g)),
      "rmse":float(np.sqrt(np.mean(x*x))),
      "mae":float(np.mean(np.abs(x))),
      "bias":float(np.mean(x)),
      "max_abs":float(np.max(np.abs(x))),
      "by_origin":{},
      "by_horizon":{}
    }
    for o,gg in g.groupby("origin_year"):
        e=gg.error_actual_minus_prediction.to_numpy(float)
        out["specs"][name]["by_origin"][str(int(o))]={
          "rmse":float(np.sqrt(np.mean(e*e))),
          "mae":float(np.mean(np.abs(e))),
          "bias":float(np.mean(e)),
          "max_abs":float(np.max(np.abs(e)))
        }
    for h,gg in g.groupby("horizon_years"):
        e=gg.error_actual_minus_prediction.to_numpy(float)
        out["specs"][name]["by_horizon"][str(int(h))]={
          "rmse":float(np.sqrt(np.mean(e*e))),
          "mae":float(np.mean(np.abs(e))),
          "bias":float(np.mean(e)),
          "max_abs":float(np.max(np.abs(e)))
        }

w=rows[rows.apply(lambda r: match_tuple(r,specs["winner_0_0_1_1"]),axis=1)].copy()
for name,t in specs.items():
    if name=="winner_0_0_1_1": continue
    c=rows[rows.apply(lambda r: match_tuple(r,t),axis=1)].copy()
    m=w.merge(c,on=["origin_year","horizon_years","target_year"],suffixes=("_w","_c"))
    aw=np.abs(m.error_actual_minus_prediction_w.to_numpy(float))
    ac=np.abs(m.error_actual_minus_prediction_c.to_numpy(float))
    out["pairwise_vs_winner"][name]={
      "n":int(len(m)),
      "winner_lower_abs_error_count":int(np.sum(aw<ac)),
      "challenger_lower_abs_error_count":int(np.sum(ac<aw)),
      "ties":int(np.sum(np.isclose(aw,ac))),
      "mean_abs_error_advantage_persons":float(np.mean(ac-aw)),
      "winner_better_origins":int(sum(
          out["specs"]["winner_0_0_1_1"]["by_origin"][o]["rmse"] <
          out["specs"][name]["by_origin"][o]["rmse"]
          for o in out["specs"]["winner_0_0_1_1"]["by_origin"]
      )),
      "winner_better_horizons":int(sum(
          out["specs"]["winner_0_0_1_1"]["by_horizon"][h]["rmse"] <
          out["specs"][name]["by_horizon"][h]["rmse"]
          for h in out["specs"]["winner_0_0_1_1"]["by_horizon"]
      ))
    }

(D/"lulea_strict_single_origin_winner_robustness.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
