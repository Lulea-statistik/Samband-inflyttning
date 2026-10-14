#!/usr/bin/env python3
"""Research-only paired blind geographic stress test of unemployment and employment growth."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features, _geographic_error_metrics
from test_commuting_annual_paired import source_data

D = Path("docs/data")
LONG = "lag1_kolada_langtidsarbetslosa_pct"
GROWTH = "lag1_sysselsatta_bostad_forandring_pct"
CIVIC = "lag1_kolada_utbetalt_lok_stod_kr_per_inv"
CONTROLS = ["lag1_log_folkmangd", "lag1_tatortsgrad_pct", "lag1_regional_centre_distance_km"]
ADDITIONS = {"reference": [], "long_term_unemployment": [LONG],
             "employment_growth": [GROWTH], "both_labour": [LONG, GROWTH],
             "civic_and_long_term": [CIVIC, LONG],
             "civic_and_both_labour": [CIVIC, LONG, GROWTH]}
BLOCKED = ("inflytt", "utflytt", "befolkningstillvaxt", "inflyttare_medelalder", "andel_20_34")
def main():
    sources, fair, target = source_data()
    frame = sources["BAS"].copy()
    ids = sorted(frame.loc[frame.year.eq(2024), "kommun_kod"].unique())
    if len(ids) != 290:
        raise RuntimeError("Expected 290 municipalities")
    candidates = [LONG, GROWTH, CIVIC]
    for field in candidates + CONTROLS:
        if field not in frame.columns or frame[field].isna().any():
            raise RuntimeError(f"Missing fair full-coverage field {field}")
    # Ensure candidates cannot have been selected in the reference model.
    pool = [field for field in fair["eligible_pool"] if field not in candidates and
            not any(term in field for term in BLOCKED)]
    if any(any(term in field for term in BLOCKED) for field in pool):
        raise RuntimeError("Forbidden demographic predictors")
    rows, folds = [], []
    for fold in range(5):
        held = {code for code in ids if int(hashlib.sha256(("validation-140:" + code).encode()).hexdigest()[:12], 16) % 5 == fold}
        train = frame[(frame.year < 2024) & (~frame.kommun_kod.isin(held))].copy()
        test = frame[(frame.year == 2024) & frame.kommun_kod.isin(held)].copy()
        if len(train) < 350 or len(test) < 25:
            raise RuntimeError("Insufficient fold observations")
        eligible = [f for f in pool if f in train and train[f].notna().all() and test[f].notna().all()]
        selected = _select_features(train, eligible, target)["selected"]
        baseline = list(dict.fromkeys(selected + CONTROLS))
        if any(v in baseline for v in candidates):
            raise RuntimeError("Candidate leaked into baseline")
        preds = {}
        for name, added in ADDITIONS.items():
            cols = list(dict.fromkeys(baseline + added))
            if train[cols].isna().any().any() or test[cols].isna().any().any():
                raise RuntimeError(f"Incomplete identical sample: {name}")
            model = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 25)))
            model.fit(train[cols], train[target])
            preds[name] = model.predict(test[cols])
        for i, (_, record) in enumerate(test.iterrows()):
            rows.append({"kommun_kod": record.kommun_kod, "actual": float(record[target]), "fold": fold,
                         **{k: float(p[i]) for k,p in preds.items()}})
        folds.append({"fold": fold, "n_train": len(train), "n_test": len(test),
                      "selected_features": selected})
        print(f"fold {fold} evaluated", flush=True)
    result = pd.DataFrame(rows).sort_values("kommun_kod")
    if len(result) != 290 or result.kommun_kod.nunique() != 290:
        raise RuntimeError("Incomplete holdout coverage")
    actual = result.actual.to_numpy()
    report = {"research_only": True, "model": "blind structural BAS geographic validation",
              "evaluation_year": 2024, "training_years": [2022, 2023],
              "n_municipalities": 290, "candidate_fields": {"long_term_unemployment": LONG,
              "employment_growth": GROWTH, "civic_support": CIVIC},
              "candidate_excluded_from_baseline_selection": True,
              "structural_controls": CONTROLS, "geographic_folds": folds,
              "metrics": {key: _geographic_error_metrics(result.actual, result[key]) for key in ADDITIONS},
              "lulea": result[result.kommun_kod.eq("2580")].to_dict("records"),
              "bootstrap": {}, "production_model_changed": False}
    rng = np.random.default_rng(20261014)
    base = result.reference.to_numpy()
    for key in list(ADDITIONS)[1:]:
        alternative = result[key].to_numpy()
        gains = []
        for _ in range(2000):
            idx = rng.integers(0, len(actual), len(actual))
            gains.append(float(np.sqrt(np.mean((actual[idx]-base[idx])**2))-
                               np.sqrt(np.mean((actual[idx]-alternative[idx])**2))))
        report["bootstrap"][key] = {
            "rmse_gain": float(report["metrics"]["reference"]["rmse"]-report["metrics"][key]["rmse"]),
            "exploratory_ci95": [float(np.quantile(gains, 0.025)), float(np.quantile(gains, 0.975))],
            "municipalities_improved": int((np.abs(actual-alternative)<np.abs(actual-base)).sum())}
    report["limitations"] = [
        "2024 and these geographic folds have been explored before; this is not prospective confirmation.",
        "Municipal relationships cannot establish causality.",
        "One evaluation year and only two years of training.",
        "Candidate variables excluded from reference selection for valid additive test.",
        "Blind BAS research subset, not frozen production model."]
    (D/"blind_labour_joint_geographic.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
if __name__ == "__main__":
    main()
