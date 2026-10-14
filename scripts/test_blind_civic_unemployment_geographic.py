#!/usr/bin/env python3
"""Geographic validation of prechosen blind structural civic and unemployment signals.

Never include historic migration or age-profile predictors. Compare same 2024
municipality holdouts, with municipality population, density/urbanization and
regional distance structurally controlled in every model.
"""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
FORBIDDEN={"lag1_inflyttning_per_1000","lag1_utflyttning_per_1000","lag1_befolkningstillvaxt_pct","lag1_andel_20_34","lag1_inflyttare_medelalder"}
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"]
CIVIC="lag1_kolada_utbetalt_lok_stod_kr_per_inv"
LONG="lag1_kolada_langtidsarbetslosa_pct"
ADDITIONS={"reference":[],"civic_support":[CIVIC],"long_term_unemployment":[LONG],"both":[CIVIC,LONG]}
def metrics(y,p):
    return _geographic_error_metrics(pd.Series(y),pd.Series(p))
def main():
    source,fair,target=source_data();d=source["BAS"]
    pool=list(dict.fromkeys([v for v in fair["eligible_pool"] if v not in FORBIDDEN]+CONTROLS))
    if any(any(t in v for t in ("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")) for v in pool):
        raise RuntimeError("Historical demographic predictors in pool")
    ids=sorted(d.loc[d.year.eq(2024)].kommun_kod.unique())
    rows=[];folds=[]
    for fold in range(5):
        held={c for c in ids if int(hashlib.sha256(("validation-140:"+c).encode()).hexdigest()[:12],16)%5==fold}
        tr=d.loc[(d.year<2024)&(~d.kommun_kod.isin(held))].copy()
        te=d.loc[(d.year==2024)&d.kommun_kod.isin(held)].copy()
        if len(te)<25 or len(tr)<350:raise RuntimeError("Geographic fold too small")
        eligible=[v for v in pool if v in tr and tr[v].notna().all() and te[v].notna().all()]
        if any(v not in eligible for v in CONTROLS):raise RuntimeError("Structural controls incomplete")
        selected=_select_features(tr,eligible,target)["selected"]
        baseline=list(dict.fromkeys(selected+CONTROLS))
        pred={};coefs={}
        for name,added in ADDITIONS.items():
            cols=list(dict.fromkeys(baseline+added))
            if tr[cols].isna().any().any() or te[cols].isna().any().any():raise RuntimeError(f"Missing {name}")
            m=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            m.fit(tr[cols],tr[target]);pred[name]=m.predict(te[cols])
            coefs[name]={v:float(m.named_steps["ridgecv"].coef_[cols.index(v)]) for v in added}
        folds.append({"fold":fold,"n_test":len(te),"selected_features":len(selected),"candidate_coefficients":coefs})
        for i,(_,obs) in enumerate(te.iterrows()):
            rows.append({"kommun_kod":obs.kommun_kod,"actual":float(obs[target]),"fold":fold,
                **{k:float(p[i]) for k,p in pred.items()}})
        print(f"fold {fold} {len(te)} complete",flush=True)
    results=pd.DataFrame(rows).sort_values("kommun_kod")
    if len(results)!=290 or results.kommun_kod.nunique()!=290:raise RuntimeError("Incomplete 290 municipality output")
    actual=results.actual.to_numpy()
    report={"status":"blind_civic_unemployment_geographic_stress","year":2024,"n_municipalities":290,
       "design":"Same five geographic splits; held municipality excluded from training for both 2022 and 2023",
       "structural_controls":CONTROLS,"demographic_blind":True,"production_model_changed":False,
       "folds":folds,"metrics":{k:metrics(actual,results[k].to_numpy()) for k in ADDITIONS},
       "lulea":results.loc[results.kommun_kod=="2580"].to_dict("records"),
       "bootstrap":{}}
    rng=np.random.default_rng(20261014);ref=results.reference.to_numpy()
    for name in ("civic_support","long_term_unemployment","both"):
        alt=results[name].to_numpy();delta=[]
        for _ in range(2000):
            ix=rng.integers(0,290,290)
            delta.append(float(np.sqrt(np.mean((actual[ix]-ref[ix])**2))-np.sqrt(np.mean((actual[ix]-alt[ix])**2))))
        report["bootstrap"][name]={"rmse_gain":float(report["metrics"]["reference"]["rmse"]-report["metrics"][name]["rmse"]),
           "exploratory_ci95":[float(np.quantile(delta,.025)),float(np.quantile(delta,.975))],
           "municipalities_improved":int((abs(actual-alt)<abs(actual-ref)).sum())}
    report["limitations"]=["Repeatedly inspected 2024 and reused geographic folds, not independent confirmation.",
       "Population/urbanity/distance are included, but cannot establish whether civic support is a proxy rather than a cause.",
       "Blind BAS subset not the full published historical structural model."]
    (D/"commuting_blind_civic_unemployment_geographic.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
