#!/usr/bin/env python3
"""#142 final retrospective parsimony check. No further model search or deployment."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV

from build_analysis import _select_features, _geographic_error_metrics

ROOT = Path("docs/data")
METRICS = ("rmse", "mae", "p90_abs_error", "worst_decile_mae")


def metrics(y, p):
    return _geographic_error_metrics(y, p)


def final_check():
    cv = json.loads((ROOT / "validation_140.json").read_text(encoding="utf-8"))
    panel = pd.read_csv(ROOT / "panel.csv", dtype={"kommun_kod": str}, low_memory=False)
    model = json.loads((ROOT / "model.json").read_text(encoding="utf-8"))
    fair = model["fair_reselection_test"]
    features = cv["six_core_features"]
    eligible = fair["eligible_pool"]
    incumbent = fair["incumbent_features"]
    target = model["target"]
    result = {
        "evaluation": "#142 final retrospective test and candidate freeze",
        "status": "not_run",
        "active_production_model": "incumbent",
        "frozen_candidate": "six_feature_core",
        "features": features,
        "independent_validation": False,
        "warning": "Features and methods were developed using 2022-2024 results. This test is diagnostic, not independently confirmatory. No further model search is planned.",
    }
    paired = pd.DataFrame(cv.get("paired_predictions_2024", []))
    needed = ["actual", "six_core_prediction", "challenger_prediction", "incumbent_prediction", "kommun_kod"]
    if paired.empty or not set(needed).issubset(paired):
        result["reason"] = "Missing paired municipality holdout predictions"
        return result
    rng = np.random.default_rng(142)
    rows = paired.reset_index(drop=True)
    n = len(rows)
    sample_deltas = {key: [] for key in METRICS}
    for _ in range(1200):
        selection = rng.integers(0, n, size=n)
        subset = rows.iloc[selection]
        six = metrics(subset.actual, subset.six_core_prediction)
        dynamic = metrics(subset.actual, subset.challenger_prediction)
        for key in METRICS:
            sample_deltas[key].append(dynamic[key] - six[key])
    result["paired_bootstrap_2024_dynamic_minus_six"] = {
        key: {
            "estimate": metrics(rows.actual, rows.challenger_prediction)[key] - metrics(rows.actual, rows.six_core_prediction)[key],
            "ci95_low": float(np.quantile(values, 0.025)),
            "ci95_high": float(np.quantile(values, 0.975)),
        }
        for key, values in sample_deltas.items()
    }
    # Fixed feature sets vs dynamic selection from scratch at each origin.
    # A holdout year is not used in fitting/selection for its own fold.
    years = sorted(int(y) for y in panel.year.unique())
    yearly = []
    cols = list(dict.fromkeys(["kommun_kod", "year", target] + eligible))
    data = panel.loc[panel.year.between(2019, 2024), cols].dropna().copy()
    for year in (2022, 2023, 2024):
        train = data.loc[data.year.between(2019, year - 1)]
        test = data.loc[data.year == year]
        if len(train) < 300 or len(test) < 200:
            yearly.append({"year": year, "status": "insufficient_sample", "n_train": len(train), "n_test": len(test)})
            continue
        selected = _select_features(train, eligible, target)["selected"]
        def fit_predict(fs):
            m = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 25)))
            m.fit(train[fs], train[target])
            return m.predict(test[fs])
        models = {"incumbent": incumbent, "six": features, "dynamic": selected}
        m = {name: metrics(test[target], fit_predict(fs)) for name, fs in models.items()}
        yearly.append({"year": year, "status": "tested", "n_train": len(train), "n_test": len(test), "dynamic_selected": selected, "metrics": {name: {k: val[k] for k in METRICS} for name,val in m.items()}})
    result["retrospective_temporal_rolling_origins"] = yearly
    result["geographic_metrics_2024"] = {name: metrics(rows.actual, rows[pred]) for name,pred in (("incumbent","incumbent_prediction"),("six","six_core_prediction"),("dynamic","challenger_prediction"))}
    result["lulea_2024"] = rows.loc[rows.kommun_kod.astype(str).str.zfill(4) == "2580"].to_dict("records")
    result["decision"] = "Freeze six-feature core as a candidate only; retain the incumbent in production until genuinely new outcome-year testing. Tiny apparent gains versus dynamic are not sufficient proof of superiority."
    result["status"] = "retrospective_final_diagnostic_complete" if all(r["status"] == "tested" for r in yearly) else "incomplete_temporal_diagnostic"
    return result


if __name__ == "__main__":
    report = final_check()
    (ROOT / "validation_142.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status":report["status"],"yearly":[{"year":v["year"],"status":v["status"]} for v in report.get("retrospective_temporal_rolling_origins",[])],"decision":report.get("decision"),"reason":report.get("reason")}, ensure_ascii=False))
