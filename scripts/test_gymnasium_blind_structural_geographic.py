#!/usr/bin/env python3
"""Research only: paired geographic holdout test of gymnasium outcomes in blind BAS structure."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features, _geographic_error_metrics, _kolada_year_rows, _kolada_total_value
from test_commuting_annual_paired import source_data

D = Path("docs/data")
CONTROLS = ["lag1_log_folkmangd", "lag1_tatortsgrad_pct", "lag1_regional_centre_distance_km"]
KPI = {"graduation": "N17445", "grade_points": "N17701"}
FORBIDDEN = ("inflytt", "utflytt", "befolkningstillvaxt", "inflyttare_medelalder", "andel_20_34")
MODELS = {"reference": [], "graduation": ["graduation"], "grade_points": ["grade_points"], "both": ["graduation", "grade_points"]}

def main():
    data, fair, target = source_data()
    panel = data["BAS"].copy()
    years = sorted(int(x) for x in panel.year.unique())
    if years != [2022, 2023, 2024]:
        raise RuntimeError(f"Unexpected BAS years: {years}")
    ids = set(panel.kommun_kod.unique())
    for name, kpi in KPI.items():
        records = []
        for source_year in [2021, 2022, 2023]:
            for rec in _kolada_year_rows(kpi, source_year):
                municipality = str(rec.get("municipality", "")).strip().zfill(4)
                value = _kolada_total_value(rec.get("values", []))
                if municipality in ids and np.isfinite(value):
                    records.append({"kommun_kod": municipality, "year": source_year + 1, name: float(value)})
        values = pd.DataFrame(records)
        if values.empty:
            raise RuntimeError(f"No source values for {name}")
        values = values.drop_duplicates(["kommun_kod", "year"])
        panel = panel.merge(values, on=["kommun_kod", "year"], how="left", validate="one_to_one")
    if panel[["graduation", "grade_points"]].isna().any().any():
        counts = panel.groupby("year")[["graduation", "grade_points"]].count().to_dict()
        raise RuntimeError(f"Cannot do fair complete-case comparison: {counts}")
    pool = [f for f in fair["eligible_pool"] if not any(term in f for term in FORBIDDEN)]
    if any(any(term in f for term in FORBIDDEN) for f in pool):
        raise RuntimeError("Demographic leakage")
    if any(c not in panel for c in CONTROLS):
        raise RuntimeError("Missing structural controls")
    ids = sorted(panel.loc[panel.year.eq(2024), "kommun_kod"].unique())
    if len(ids) != 290:
        raise RuntimeError("Expected 290 municipalities")
    rows, folds = [], []
    for fold in range(5):
        held = {code for code in ids if int(hashlib.sha256(("validation-140:" + code).encode()).hexdigest()[:12], 16) % 5 == fold}
        train = panel[(panel.year < 2024) & (~panel.kommun_kod.isin(held))].copy()
        test = panel[(panel.year == 2024) & panel.kommun_kod.isin(held)].copy()
        eligible = [f for f in pool if f in train and train[f].notna().all() and test[f].notna().all()]
        selected = _select_features(train, eligible, target)["selected"]
        baseline = list(dict.fromkeys(selected + CONTROLS))
        predictions = {}
        for name, addition in MODELS.items():
            features = baseline + addition
            if train[features].isna().any().any() or test[features].isna().any().any():
                raise RuntimeError(f"Missing fair comparison variables: {name}")
            estimator = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 25)))
            estimator.fit(train[features], train[target])
            predictions[name] = estimator.predict(test[features])
        for i, (_, record) in enumerate(test.iterrows()):
            rows.append({"kommun_kod": record.kommun_kod, "actual": float(record[target]), "fold": fold,
                         **{k: float(v[i]) for k, v in predictions.items()}})
        folds.append({"fold": fold, "n_test": len(test), "selected": selected})
        print(f"Geographic fold {fold} complete", flush=True)
    out = pd.DataFrame(rows)
    if len(out) != 290 or out.kommun_kod.nunique() != 290:
        raise RuntimeError("Incomplete geographic holdouts")
    actual = out.actual.to_numpy()
    report = {"research_only": True, "demographically_blind": True,
              "year": 2024, "n_municipalities": 290, "training_years": [2022, 2023],
              "kpi": KPI, "candidate_lag_years": 1, "fixed_controls": CONTROLS,
              "split": "Geographic SHA256 validation-140 five folds; same held municipalities for all models",
              "train_only_selection": True, "folds": folds,
              "metrics": {k: _geographic_error_metrics(out.actual, out[k]) for k in MODELS},
              "lulea": out.loc[out.kommun_kod == "2580"].to_dict("records"),
              "bootstrap": {}, "production_model_changed": False,
              "limitations": [
                  "Only 2024 independent municipality predictions; earlier work inspected this same year.",
                  "Kolada grade-point definition and publication-date availability require independent audit.",
                  "These are municipal ecological associations and do not identify causal effects.",
                  "This is a blind BAS research subset, not the complete frozen production model.",
                  "All compared variants share identical observations, folds and reference features."]}
    rng = np.random.default_rng(20261014)
    baseline = out.reference.to_numpy()
    for name in ("graduation", "grade_points", "both"):
        alternative = out[name].to_numpy()
        delta = []
        for _ in range(2000):
            idx = rng.integers(0, len(actual), len(actual))
            delta.append(float(np.sqrt(np.mean((actual[idx] - baseline[idx])**2)) -
                               np.sqrt(np.mean((actual[idx] - alternative[idx])**2))))
        report["bootstrap"][name] = {"rmse_gain": float(report["metrics"]["reference"]["rmse"] - report["metrics"][name]["rmse"]),
                                     "exploratory_ci95": [float(np.quantile(delta, .025)), float(np.quantile(delta, .975))],
                                     "municipalities_improved": int((abs(actual - alternative) < abs(actual - baseline)).sum())}
    (D / "gymnasium_blind_structural_geographic.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
if __name__ == "__main__":
    main()
