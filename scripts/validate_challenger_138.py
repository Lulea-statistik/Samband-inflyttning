#!/usr/bin/env python3
"""#138: spatially blocked retrospective challenge. NOT an independent temporal holdout.

The 2024 outcomes have already influenced previous research (#131-137).
Held-out municipalities are fixed using deterministic SHA256 partitioning.
Selection is run on training rows only. No production model is changed.
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

OUT = Path("docs/data/validation_138.json")
MODEL = Path("docs/data/model.json")
PANEL = Path("docs/data/panel.csv")
TEST_YEAR = 2024
SEED = "validation-138-fixed-geography-v1"


def geographical_holdout():
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    fair = model.get("fair_reselection_test", {})
    result = {
        "evaluation": "#138 spatially blocked retrospective validation",
        "status": "not_independent_for_production",
        "active_model": "incumbent",
        "test_year": TEST_YEAR,
        "split": "SHA256 municipality identifier, stable 20% holdout",
        "important_limitation": (
            "2024 was previously used in challenger design and comparisons. "
            "Even though municipalities here are held out of model fitting, "
            "this is a retrospective sensitivity test, NOT an independent "
            "confirmatory test. Production promotion is prohibited."
        ),
    }
    if fair.get("status") != "tested":
        result["reason"] = "Fair candidate feature pool unavailable"
        return result
    df = pd.read_csv(PANEL, low_memory=False)
    target = model.get("target")
    incumbent = list(fair.get("incumbent_features", []))
    eligible = list(fair.get("eligible_pool", []))
    cols = ["kommun_kod", "kommun", "year", target] + eligible
    cols = list(dict.fromkeys(cols))
    absent = [col for col in cols if col not in df.columns]
    if absent:
        result["reason"] = "Missing columns: " + ", ".join(absent)
        return result
    data = df.loc[df.year.between(2021, TEST_YEAR), cols].dropna().copy()
    # Exclude ALL observations of the held-out municipalities from training.
    def reserved(code):
        digest = hashlib.sha256((SEED + ":" + str(code)).encode()).hexdigest()
        return int(digest[:12], 16) % 5 == 0
    holdout_ids = {k for k in data.kommun_kod.astype(str).unique() if reserved(k)}
    train = data.loc[(~data.kommun_kod.astype(str).isin(holdout_ids)) &
                     (data.year < TEST_YEAR)].copy()
    test = data.loc[(data.kommun_kod.astype(str).isin(holdout_ids)) &
                    (data.year == TEST_YEAR)].copy()
    result["sample"] = {
        "training_rows": int(len(train)), "test_rows": int(len(test)),
        "training_municipalities": int(train.kommun_kod.nunique()),
        "test_municipalities": int(test.kommun_kod.nunique()),
    }
    if len(train) < 300 or len(test) < 30 or not incumbent or not eligible:
        result["reason"] = "Insufficient paired geographic test sample"
        return result
    selection = _select_features(train, eligible, target)
    selected = selection["selected"]
    if not selected:
        result["reason"] = "No challenger features selected"
        return result

    def predict(columns):
        m = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 25)))
        m.fit(train[columns], train[target])
        return m.predict(test[columns])

    inc_pred = predict(incumbent)
    challenger_pred = predict(selected)
    inc_met = _geographic_error_metrics(test[target], inc_pred)
    ch_met = _geographic_error_metrics(test[target], challenger_pred)
    metrics = ["rmse", "mae", "p90_abs_error", "worst_decile_mae"]
    differences = {m: float(inc_met[m] - ch_met[m]) for m in metrics}
    detail = test[["kommun_kod", "kommun"]].copy()
    detail["actual"] = test[target].to_numpy()
    detail["incumbent_absolute_error"] = np.abs(test[target].to_numpy() - inc_pred)
    detail["challenger_absolute_error"] = np.abs(test[target].to_numpy() - challenger_pred)
    detail["improvement"] = (detail["incumbent_absolute_error"] -
                             detail["challenger_absolute_error"])
    local = detail.loc[detail.kommun_kod.astype(str).str.zfill(4) == "2580"]
    result.update({
        "status": "retrospective_diagnostic_complete",
        "incumbent_features": incumbent,
        "challenger_features_selected_using_training_only": selected,
        "incumbent_metrics": inc_met,
        "challenger_metrics": ch_met,
        "incumbent_minus_challenger": differences,
        "municipalities_improved": int((detail.improvement > 0).sum()),
        "municipalities_worsened": int((detail.improvement < 0).sum()),
        "largest_improvements": detail.nlargest(10, "improvement").to_dict("records"),
        "largest_deteriorations": detail.nsmallest(10, "improvement").to_dict("records"),
        "lulea_if_in_holdout": local.to_dict("records"),
        "next_required_step": (
            "Freeze the full pipeline and validate on a genuinely future "
            "unseen outcome year when comparable SCB data are available."
        ),
    })
    return result



def crossvalidate_all_municipalities():
    """#140: exactly one out-of-municipality 2024 prediction per municipality.

    Five deterministic folds partition the complete common-sample municipalities.
    Feature selection and ridge calibration use only other municipalities'
    data through 2023. The 2024 outcome is never part of fold fitting.
    This remains retrospective; 2024 has been examined in prior iterations.
    """
    from collections import Counter
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    fair = model.get("fair_reselection_test", {})
    output = {
        "evaluation": "#140 five-fold geographic cross-validation",
        "status": "not_tested",
        "production_status": "incumbent_unchanged",
        "temporal_independence": False,
        "warning": "2024 was repeatedly consulted during earlier model development; geographic cross-validation is NOT independent future-year validation.",
        "split_method": "stable sorted municipality codes into five folds using SHA256",
        "test_year": 2024,
    }
    if fair.get("status") != "tested":
        output["reason"] = "fair_reselection_test unavailable"
        return output
    df = pd.read_csv(PANEL, low_memory=False, dtype={"kommun_kod": str})
    target = model["target"]
    eligible = list(fair["eligible_pool"])
    incumbent = [f for f in fair["incumbent_features"] if f in eligible]
    cols = list(dict.fromkeys(["kommun_kod", "kommun", "year", target] + eligible))
    missing = [c for c in cols if c not in df.columns]
    if missing:
        output["reason"] = "Missing panel columns: " + ", ".join(missing)
        return output
    d = df.loc[df.year.between(2021, 2024), cols].dropna().copy()
    d["kommun_kod"] = d["kommun_kod"].str.zfill(4)
    # Only municipalities represented in the target year are in the evaluation universe.
    universe = sorted(d.loc[d.year == 2024, "kommun_kod"].unique())
    folds = {code: int(hashlib.sha256(("validation-140:" + code).encode()).hexdigest()[:12], 16) % 5 for code in universe}
    details, selections, fold_metrics = [], Counter(), []
    for fold in range(5):
        held = {code for code in universe if folds[code] == fold}
        train = d.loc[(~d.kommun_kod.isin(held)) & (d.year < 2024)].copy()
        test = d.loc[(d.kommun_kod.isin(held)) & (d.year == 2024)].copy()
        if len(train) < 300 or len(test) < 25:
            output["reason"] = f"Fold {fold} has insufficient data"
            output["sample"] = {"train": len(train), "test": len(test)}
            return output
        chosen = _select_features(train, eligible, target)["selected"]
        if not chosen or not incumbent:
            output["reason"] = f"Fold {fold} has no selected candidate"
            return output
        selections.update(chosen)
        def predict(features):
            estimator = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 25)))
            estimator.fit(train[features], train[target])
            return estimator.predict(test[features])
        pi, pc = predict(incumbent), predict(chosen)
        actual = test[target].to_numpy(dtype=float)
        sub = test[["kommun_kod", "kommun"]].copy()
        sub["actual"] = actual
        sub["incumbent_prediction"] = pi
        sub["challenger_prediction"] = pc
        sub["incumbent_absolute_error"] = np.abs(actual - pi)
        sub["challenger_absolute_error"] = np.abs(actual - pc)
        sub["improvement"] = sub["incumbent_absolute_error"] - sub["challenger_absolute_error"]
        details.append(sub)
        fold_metrics.append({
            "fold": fold, "municipalities": int(len(test)),
            "selected_features": chosen,
            "incumbent_rmse": _geographic_error_metrics(actual, pi)["rmse"],
            "challenger_rmse": _geographic_error_metrics(actual, pc)["rmse"],
        })
    combined = pd.concat(details, ignore_index=True)
    if len(combined) != len(universe) or combined.kommun_kod.nunique() != len(universe):
        output["reason"] = "Validation coverage invariant failed"
        return output
    old = _geographic_error_metrics(combined.actual, combined.incumbent_prediction)
    new = _geographic_error_metrics(combined.actual, combined.challenger_prediction)
    output.update({
        "status": "retrospective_geographic_cv_complete",
        "coverage": {"tested": int(len(combined)), "available_2024": int(len(universe)), "unique_municipalities": int(combined.kommun_kod.nunique())},
        "folds": fold_metrics,
        "selection_frequency": [{"feature": feature, "selected_folds": n} for feature, n in selections.most_common()],
        "incumbent_metrics": old,
        "challenger_metrics": new,
        "incumbent_minus_challenger": {k: old[k] - new[k] for k in ("rmse", "mae", "p90_abs_error", "worst_decile_mae")},
        "municipalities_improved": int((combined.improvement > 0).sum()),
        "municipalities_worsened": int((combined.improvement < 0).sum()),
        "lulea": combined.loc[combined.kommun_kod == "2580"].to_dict("records"),
        "largest_improvements": combined.nlargest(15, "improvement").to_dict("records"),
        "largest_deteriorations": combined.nsmallest(15, "improvement").to_dict("records"),
        "note": "One held-out 2024 observation per municipality. Results cannot prove causal variable effects or justify deployment without unseen future outcomes.",
    })
    return output

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report = geographical_holdout()
    cv140 = crossvalidate_all_municipalities()
    Path("docs/data/validation_140.json").write_text(json.dumps(cv140, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cv140_status": cv140["status"], "coverage": cv140.get("coverage"), "deltas": cv140.get("incumbent_minus_challenger"), "lulea": cv140.get("lulea")}, ensure_ascii=False))
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({"status": report["status"], "sample": report.get("sample"),
                      "deltas": report.get("incumbent_minus_challenger"),
                      "reason": report.get("reason")}, ensure_ascii=False))
