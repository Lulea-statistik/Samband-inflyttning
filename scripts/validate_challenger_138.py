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


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report = geographical_holdout()
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({"status": report["status"], "sample": report.get("sample"),
                      "deltas": report.get("incumbent_minus_challenger"),
                      "reason": report.get("reason")}, ensure_ascii=False))
