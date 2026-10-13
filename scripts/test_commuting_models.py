#!/usr/bin/env python3
"""Retrospective commuter-variable challenger test, paired geographic 2024 CV.
No changes to production. All feature selection is confined to training folds.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features, _geographic_error_metrics

D=Path("docs/data")
COMM=["lag1_outcommuting_share","lag1_incommuting_share","lag1_commuting_balance_per_1000_workers","lag1_outcommuting_share_change_pp"]


def isolated_commuting_diagnostic(d, baseline, pool, target):
    """Paired checks: individual candidate effects at identical training/test splits.

    Dynamic candidate selection is repeated inside training data for each
    candidate. Fixed dynamic+candidate is reported separately to distinguish
    coefficient contribution from selection effects.
    """
    variants = {"none": [], "out_share": [COMM[0]], "in_share": [COMM[1]],
                "net_balance": [COMM[2]], "out_share_change": [COMM[3]],
                "level_pair": COMM[:2], "change_and_out": [COMM[0], COMM[3]],
                "all_four": COMM}
    parts = []
    tests = []
    for year in (2023, 2024):
        train = d.loc[d.year < year]
        test = d.loc[d.year == year]
        if len(train) >= 280 and len(test) >= 250:
            tests.append((f"rolling_{year}", train, test))
    universe = sorted(d.loc[d.year == 2024].kommun_kod.unique())
    for fold in range(5):
        held = {v for v in universe if int(hashlib.sha256(("validation-140:" + v).encode()).hexdigest()[:12], 16) % 5 == fold}
        train = d.loc[d.year.lt(2024) & ~d.kommun_kod.isin(held)]
        test = d.loc[d.year.eq(2024) & d.kommun_kod.isin(held)]
        if len(train) < 300 or len(test) < 25:
            raise RuntimeError("Insufficient isolated CV fold")
        tests.append((f"geo_{fold}", train, test))

    for split, train, test in tests:
        original_selected = _select_features(train, pool, target)["selected"]
        for variant, additions in variants.items():
            if variant == "none":
                selected = original_selected
            else:
                selected = _select_features(train, list(dict.fromkeys(pool + additions)), target)["selected"]
            specs = {
                "incumbent": baseline + additions,
                "dynamic_selected": selected,
                "dynamic_fixed_plus": list(dict.fromkeys(original_selected + additions)),
            }
            metrics = {}
            predictions = {}
            for name, feature_set in specs.items():
                estimator = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 25)))
                estimator.fit(train[feature_set], train[target])
                predictions[name] = estimator.predict(test[feature_set])
                metrics[name] = _geographic_error_metrics(test[target], predictions[name])
            for i, (idx, row) in enumerate(test.iterrows()):
                parts.append({"split": split, "variant": variant, "kommun_kod": row.kommun_kod,
                              "actual": float(row[target]),
                              **{name: float(pred[i]) for name, pred in predictions.items()}})
            if split.startswith("rolling"):
                tests_year = int(split.split("_")[1])
                print(json.dumps({"year": tests_year, "variant": variant,
                                  "rmse": {name: round(m["rmse"], 4) for name, m in metrics.items()},
                                  "selected_commuters": [x for x in selected if x in COMM]}, ensure_ascii=False), flush=True)

    predictions = pd.DataFrame(parts)
    report = {"status": "isolated_retrospective_complete", "models": ["incumbent", "dynamic_selected", "dynamic_fixed_plus"],
              "candidate_groups": variants, "holdout_years": [2023, 2024],
              "geographic_test_year": 2024, "training_selection_isolated": True,
              "production_model_changed": False,
              "caution": "Repeated 2022-2024 exploratory analysis; 2024 job classification break. Correlated candidate variables. Do not promote automatically.",
              "rolling": {}, "geographic_cv_2024": {}, "lulea_2024": {}}
    for yr in (2023, 2024):
        report["rolling"][str(yr)] = {}
        data = predictions.loc[predictions.split == f"rolling_{yr}"]
        for variant in variants:
            rows = data.loc[data.variant == variant]
            report["rolling"][str(yr)][variant] = {
                name: _geographic_error_metrics(rows.actual, rows[name])
                for name in ("incumbent", "dynamic_selected", "dynamic_fixed_plus")
            }
    geographic = predictions.loc[predictions.split.str.startswith("geo_")]
    for variant in variants:
        rows = geographic.loc[geographic.variant == variant]
        if rows.kommun_kod.nunique() != len(universe):
            raise RuntimeError("Incomplete isolated geographic validation")
        report["geographic_cv_2024"][variant] = {
            name: _geographic_error_metrics(rows.actual, rows[name])
            for name in ("incumbent", "dynamic_selected", "dynamic_fixed_plus")
        }
        report["lulea_2024"][variant] = rows.loc[rows.kommun_kod == "2580"].to_dict("records")
    # Paired municipal bootstrap and descriptive geography/size stratification.
    # Reuse the same 290 held-out municipal predictions; don't reinterpret
    # subgroup comparisons as independent tests of causal mechanisms.
    subset = geographic.loc[geographic.variant.isin(["none", "out_share"])]
    base = subset.loc[subset.variant == "none"].set_index("kommun_kod")
    extra = subset.loc[subset.variant == "out_share"].set_index("kommun_kod")
    ids = sorted(set(base.index) & set(extra.index))
    y = base.loc[ids, "actual"].to_numpy(float)
    p0 = base.loc[ids, "dynamic_fixed_plus"].to_numpy(float)
    p1 = extra.loc[ids, "dynamic_fixed_plus"].to_numpy(float)
    rng = np.random.default_rng(20261013)
    boot = []
    for _ in range(2000):
        idx = rng.integers(0, len(ids), len(ids))
        boot.append(_geographic_error_metrics(y[idx], p0[idx])["rmse"] -
                    _geographic_error_metrics(y[idx], p1[idx])["rmse"])
    report["outcommuting_paired_bootstrap"] = {
        "n_municipalities": len(ids),
        "rmse_baseline": _geographic_error_metrics(y, p0)["rmse"],
        "rmse_plus_outcommuting": _geographic_error_metrics(y, p1)["rmse"],
        "rmse_improvement": float(_geographic_error_metrics(y, p0)["rmse"] - _geographic_error_metrics(y, p1)["rmse"]),
        "ci95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
        "resamples": len(boot),
        "municipalities_improved": int((np.abs(y-p1) < np.abs(y-p0)).sum()),
        "municipalities_worsened": int((np.abs(y-p1) > np.abs(y-p0)).sum()),
    }
    # Descriptive municipal quartiles based on prior-year outcommuting level.
    descriptor = d.loc[d.year == 2024, ["kommun_kod", COMM[0]]].drop_duplicates("kommun_kod").set_index("kommun_kod")
    lev = descriptor.reindex(ids)[COMM[0]]
    if lev.notna().all():
        quantile = pd.qcut(lev.rank(method="first"), 4, labels=["Q1 low","Q2","Q3","Q4 high"])
        report["outcommuting_quartiles"] = []
        for group in quantile.cat.categories:
            mask = (quantile == group).to_numpy()
            before = _geographic_error_metrics(y[mask], p0[mask])
            after = _geographic_error_metrics(y[mask], p1[mask])
            report["outcommuting_quartiles"].append({
                "group": str(group), "n": int(mask.sum()),
                "mean_outcommuting_share_pct": float(lev.to_numpy()[mask].mean()),
                "rmse_before": before["rmse"], "rmse_after": after["rmse"],
                "rmse_improvement": before["rmse"]-after["rmse"],
                "mae_improvement": before["mae"]-after["mae"],
            })
    report["outcommuting_paired_bootstrap"]["warning"] = "Exploratory repeated 2024 holdout. CI describes sampling variation, not selection bias or validation on an unseen year."
    (D / "commuting_isolated_test.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report



def controlled_outcommuting_test(d, baseline, pool, target):
    """#5: Outcommuting incremental value above pre-specified regional controls."""
    controls = ["lag1_log_folkmangd", "lag1_tatortsgrad_pct",
                "lag1_log_externa_fa_jobb_per_1000",
                "lag1_andel_fa_arbetsplatser_i_egen_kommun",
                "lag1_regional_centre_distance_km"]
    available = [c for c in controls if c in d.columns and d.loc[d.year == 2024,c].notna().sum() >= 250]
    missing = sorted(set(controls)-set(available))
    if missing:
        raise RuntimeError("Missing required control data: "+", ".join(missing))
    candidate = COMM[0]
    used = list(dict.fromkeys(baseline + available + [candidate, target]))
    dataset = d.dropna(subset=used).copy()
    models = {"incumbent": baseline, "controlled":list(dict.fromkeys(baseline+available)),
              "controlled_plus_outcommuting":list(dict.fromkeys(baseline+available+[candidate]))}
    predictions=[]
    tests=[]
    for yr in (2023,2024):
        train=dataset.loc[dataset.year<yr]
        test=dataset.loc[dataset.year==yr]
        if len(train)<280 or len(test)<250: raise RuntimeError("Insufficient controlled temporal sample")
        tests.append((f"rolling_{yr}",train,test))
    universe=sorted(dataset.loc[dataset.year==2024].kommun_kod.unique())
    for fold in range(5):
        held={v for v in universe if int(hashlib.sha256(("validation-140:"+v).encode()).hexdigest()[:12],16)%5==fold}
        train=dataset.loc[dataset.year.lt(2024)&~dataset.kommun_kod.isin(held)]
        test=dataset.loc[dataset.year.eq(2024)&dataset.kommun_kod.isin(held)]
        if len(train)<300 or len(test)<25: raise RuntimeError("Insufficient controlled geographic fold")
        tests.append((f"geo_{fold}",train,test))
    for split,train,test in tests:
        result={}
        for name,columns in models.items():
            pipe=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            pipe.fit(train[columns],train[target])
            result[name]=pipe.predict(test[columns])
        for i,(_,r) in enumerate(test.iterrows()):
            predictions.append({"split":split,"kommun_kod":r.kommun_kod,"actual":float(r[target]),
                                "outcommuting_share":float(r[candidate]),
                                **{name:float(value[i]) for name,value in result.items()}})
    p=pd.DataFrame(predictions)
    out={"status":"retrospective_controlled_diagnostic_complete",
         "controls":available,"sample_years":[2023,2024],
         "models":models,"production_changed":False,
         "note":"Same historical years previously used in development. Descriptive not causal. Controls may be correlated; no claims of independent future-year performance.",
         "metrics":{},"lulea_2024":[]}
    for split in ["rolling_2023","rolling_2024","geographic_2024"]:
        rows=p.loc[p.split.str.startswith("geo_")] if split=="geographic_2024" else p.loc[p.split==split]
        out["metrics"][split]={name:_geographic_error_metrics(rows.actual,rows[name]) for name in models}
        if split=="geographic_2024":
            out["lulea_2024"]=rows.loc[rows.kommun_kod=="2580"].to_dict("records")
            out["geographic_sample"]=int(rows.kommun_kod.nunique())
    (D/"commuting_controlled_test.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return out


def main():
    flows=pd.read_csv(D/"commuting_flows_2020_2024.csv",dtype={"home":str,"work":str})
    if len(flows)!=420500 or flows.duplicated(["year","home","work"]).any():
        raise RuntimeError("Commuting matrix integrity failed")
    totals=flows.groupby(["year","home"],as_index=False).employed.sum().rename(columns={"home":"kommun_kod","employed":"residents_employed"})
    inside=flows.loc[flows.home==flows.work,["year","home","employed"]].rename(columns={"home":"kommun_kod","employed":"local_workers"})
    workplaces=flows.groupby(["year","work"],as_index=False).employed.sum().rename(columns={"work":"kommun_kod","employed":"workplace_employed"})
    c=totals.merge(inside,on=["year","kommun_kod"]).merge(workplaces,on=["year","kommun_kod"])
    if len(c)!=1450: raise RuntimeError("Missing municipality-year in derived commuters")
    c["outcommuting_share"]=100*(c.residents_employed-c.local_workers)/c.residents_employed.replace(0,np.nan)
    c["incommuting_share"]=100*(c.workplace_employed-c.local_workers)/c.workplace_employed.replace(0,np.nan)
    c["commuting_balance_per_1000_workers"]=1000*(c.workplace_employed-c.residents_employed)/c.residents_employed.replace(0,np.nan)
    c=c.sort_values(["kommun_kod","year"])
    c["outcommuting_share_change_pp"]=c.groupby("kommun_kod").outcommuting_share.diff()
    # Source-year t flows are available for forecast year t+1 only.
    # No additional shift: use 2021 flows and 2020->2021 change for forecast 2022.
    bases=("outcommuting_share","incommuting_share","commuting_balance_per_1000_workers","outcommuting_share_change_pp")
    derived=c[["kommun_kod","year"]+list(bases)].copy()
    derived=derived.rename(columns={x:"lag1_"+x for x in bases})
    derived["year"]+=1
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    panel["kommun_kod"]=panel.kommun_kod.str.zfill(4)
    d=panel.merge(derived,on=["kommun_kod","year"],how="left",validate="many_to_one")
    model=json.loads((D/"model.json").read_text())
    fair=model["fair_reselection_test"]
    baseline=list(fair["incumbent_features"])
    pool=list(fair["eligible_pool"])
    target=model["target"]
    d=d.loc[d.year.between(2022,2024)].copy()
    # Use only commuters with at least two available time observations.
    # Predictors are sourced from the previous year; change uses the two preceding years.
    required=list(dict.fromkeys(baseline+pool+COMM+[target]))
    d=d.dropna(subset=required)
    rows=[]
    for year in (2023,2024):
        test=d.loc[d.year==year]
        train=d.loc[d.year<year]
        if len(train)<280 or len(test)<250:
            rows.append({"year":year,"status":"insufficient_training","n_train":len(train),"n_test":len(test)})
            continue
        selected=_select_features(train,pool,target)["selected"]
        selected_comm=_select_features(train,pool+COMM,target)["selected"]
        specs={"incumbent":baseline,"incumbent_plus_commuting":baseline+COMM,"dynamic":selected,"dynamic_plus_commuting":selected_comm}
        def pred(fs):
            m=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            m.fit(train[fs],train[target])
            return m.predict(test[fs])
        ps={k:pred(fs) for k,fs in specs.items()}
        vals={k:_geographic_error_metrics(test[target],v) for k,v in ps.items()}
        rows.append({"year":year,"status":"tested","n_train":len(train),"n_test":len(test),"metrics":vals,"selected_dynamic":selected,"selected_dynamic_with_commuting":selected_comm,
                     "commuting_selected":[x for x in selected_comm if x in COMM],
                     "lulea": [{**{"actual":float(test.iloc[i][target])},**{k:float(p[i]) for k,p in ps.items()}} for i in range(len(test)) if test.iloc[i].kommun_kod=="2580"]})
    # Municipality-separated 2024 folds, train 2022-23 on other municipality codes.
    allrows=[]
    universe=sorted(d.loc[d.year==2024].kommun_kod.unique())
    for fold in range(5):
        held=[v for v in universe if int(hashlib.sha256(("validation-140:"+v).encode()).hexdigest()[:12],16)%5==fold]
        train=d.loc[d.year.lt(2024)&~d.kommun_kod.isin(held)]
        test=d.loc[d.year.eq(2024)&d.kommun_kod.isin(held)]
        if len(train)<300 or len(test)<25: raise RuntimeError("Inadequate CV fold coverage")
        chosen=_select_features(train,pool,target)["selected"]
        chosen_comm=_select_features(train,pool+COMM,target)["selected"]
        specs={"incumbent":baseline,"incumbent_plus_commuting":baseline+COMM,"dynamic":chosen,"dynamic_plus_commuting":chosen_comm}
        predictions={}
        for name,fs in specs.items():
            m=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            m.fit(train[fs],train[target])
            predictions[name]=m.predict(test[fs])
        for i,(_,row) in enumerate(test.iterrows()):
            allrows.append({"year":2024,"kommun_kod":row.kommun_kod,"actual":float(row[target]),**{name:float(pr[i]) for name,pr in predictions.items()}})
    ev=pd.DataFrame(allrows)
    if ev.kommun_kod.nunique()!=len(universe):raise RuntimeError("Fold predictions incomplete")
    country={k:_geographic_error_metrics(ev.actual,ev[k]) for k in ("incumbent","incumbent_plus_commuting","dynamic","dynamic_plus_commuting")}
    report={"status":"retrospective_commuting_challenger_complete","years_raw":[2020,2021,2022,2023,2024],"candidate_predictors":COMM,
            "predictor_timing":"Commuting level for forecast t originates from t-1; change predictor uses t-2 to t-1. All information is historically lagged.",
            "note":"Exploratory: 2024 repeatedly used in research; no production promotion. Monthly commuting/trips are not observed.",
            "coverage":{str(y):int(v) for y,v in d.groupby("year").kommun_kod.nunique().items()},
            "temporal":rows,"geographic_cv_2024":country,"lulea_cv_2024":ev.loc[ev.kommun_kod=="2580"].to_dict("records"),"production_model_changed":False}
    (D/"commuting_model_test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    isolated_commuting_diagnostic(d, baseline, pool, target)
    controlled_outcommuting_test(d, baseline, pool, target)
    print(json.dumps({"status":report["status"],"temporal":[{"year":r["year"],"status":r["status"]} for r in rows],"geographic_cv_rmse":{k:v["rmse"] for k,v in country.items()}},ensure_ascii=False))

if __name__=="__main__":
    main()
