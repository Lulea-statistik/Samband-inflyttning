#!/usr/bin/env python3
"""Research-only comparison: full Ridge vs nested 1-SE Elastic Net vs stability-selected Elastic Net.

Rules:
- candidate universe is frozen from neutral_variable_pool_reboot + data gate
- all target-informed tuning happens inside outer training folds
- geographic GroupKFold is used throughout
- Elastic Net complexity is selected by the 1-SE rule
- stability is estimated with complementary half-group pairs
- no production files are changed
"""
import json
import math
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=ConvergenceWarning)

D = Path("docs/data")
read = lambda name: json.loads((D / name).read_text(encoding="utf-8"))
pool = {r["feature"]: r for r in read("neutral_variable_pool_reboot.json")["records"]}
coverage = read("neutral_80_candidate_data_gate.json")["variables"]

panel = pd.read_csv(D / "panel.csv", dtype={"kommun_kod": str}, low_memory=False)
panel["kommun_kod"] = panel["kommun_kod"].str.zfill(4)

emp = pd.read_csv(D / "employment_lag1_research_availability.csv", dtype={"kommun_kod": str})
emp["kommun_kod"] = emp["kommun_kod"].str.zfill(4)
codes = set(emp.loc[emp.target_year == 2024, "kommun_kod"])
assert len(codes) == 290

extra = (
    emp.pivot(index=["target_year", "kommun_kod"], columns="dimension", values="growth_pct")
    .reset_index()
    .rename(
        columns={
            "target_year": "year",
            "residence": "lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
            "workplace": "lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct",
        }
    )
)

p = (
    panel[panel.kommun_kod.isin(codes) & panel.year.between(2019, 2023)]
    .merge(extra, on=["year", "kommun_kod"], how="left", validate="one_to_one")
)
assert len(p) == 1450

RIDGE_ALPHA = 10.0
L1_RATIOS = [0.10, 0.25, 0.50, 0.75, 0.90, 1.00]
EN_ALPHAS = np.logspace(-3, 1.25, 18).tolist()
OUTER_SPLITS = 5
INNER_SPLITS = 3
CPSS_PAIRS = 20
PFER_TARGET = 1.0
SEED = 20261016
ZERO_TOL = 1e-8


def rmse(y, pred):
    return float(np.sqrt(np.mean((y - pred) ** 2)))


def mae(y, pred):
    return float(np.mean(np.abs(y - pred)))


def fit_enet(x, y, alpha, l1_ratio):
    model = make_pipeline(
        StandardScaler(),
        ElasticNet(
            alpha=float(alpha),
            l1_ratio=float(l1_ratio),
            max_iter=20000,
            tol=1e-6,
            selection="cyclic",
        ),
    )
    model.fit(x, y)
    return model


def active_features(model, names):
    coef = model.named_steps["elasticnet"].coef_
    return [name for name, value in zip(names, coef) if abs(float(value)) > ZERO_TOL]


def choose_enet_one_se(x, y, groups, names):
    cv = GroupKFold(INNER_SPLITS)
    rows = []
    for l1_ratio in L1_RATIOS:
        for alpha in EN_ALPHAS:
            losses = []
            active_counts = []
            for tr, va in cv.split(x, y, groups):
                m = fit_enet(x.iloc[tr], y[tr], alpha, l1_ratio)
                pred = m.predict(x.iloc[va])
                losses.append(rmse(y[va], pred))
                active_counts.append(len(active_features(m, names)))
            rows.append(
                {
                    "alpha": float(alpha),
                    "l1_ratio": float(l1_ratio),
                    "mean_rmse": float(np.mean(losses)),
                    "se_rmse": float(np.std(losses, ddof=1) / np.sqrt(len(losses))),
                    "mean_active": float(np.mean(active_counts)),
                }
            )
    best = min(rows, key=lambda r: r["mean_rmse"])
    limit = best["mean_rmse"] + best["se_rmse"]
    acceptable = [r for r in rows if r["mean_rmse"] <= limit]
    # 1-SE: choose simplest acceptable model. Complexity is measured by mean active predictors.
    chosen = min(
        acceptable,
        key=lambda r: (
            r["mean_active"],
            -r["alpha"],
            -r["l1_ratio"],
            r["mean_rmse"],
        ),
    )
    return chosen, best, rows


def cpss_stability(x, y, groups, names, alpha, l1_ratio, theme_by_feature):
    rng = np.random.default_rng(SEED)
    unique_groups = np.array(sorted(set(groups)))
    counts = Counter()
    theme_counts = Counter()
    active_sizes = []
    total_fits = 0

    for _ in range(CPSS_PAIRS):
        perm = rng.permutation(unique_groups)
        cut = len(perm) // 2
        halves = [set(perm[:cut]), set(perm[cut:])]
        for half in halves:
            idx = np.array([g in half for g in groups])
            m = fit_enet(x.loc[idx], y[idx], alpha, l1_ratio)
            active = active_features(m, names)
            active_sizes.append(len(active))
            counts.update(active)
            themes = {theme_by_feature.get(f, "needs_classification") for f in active}
            theme_counts.update(themes)
            total_fits += 1

    freq = {f: counts[f] / total_fits for f in names}
    themes = sorted(set(theme_by_feature.get(f, "needs_classification") for f in names))
    theme_freq = {t: theme_counts[t] / total_fits for t in themes}
    q = float(np.mean(active_sizes))
    p_count = len(names)

    # Meinshausen-Buehlmann conservative PFER bound:
    # E[V] <= q^2 / ((2*pi_thr - 1) * p)
    raw = q * q / (PFER_TARGET * p_count) if p_count else math.inf
    required_pi = 0.5 * (1.0 + raw)
    feasible = bool(required_pi <= 1.0)
    threshold = max(0.5000001, required_pi) if feasible else None
    stable = sorted([f for f, v in freq.items() if threshold is not None and v >= threshold])
    pfer_bound_at_threshold = (
        q * q / ((2.0 * threshold - 1.0) * p_count)
        if threshold is not None and threshold > 0.5
        else None
    )

    return {
        "pairs": CPSS_PAIRS,
        "fits": total_fits,
        "mean_selected_q": q,
        "p": p_count,
        "pfer_target": PFER_TARGET,
        "required_selection_probability": threshold,
        "pfer_target_feasible": feasible,
        "pfer_bound_at_threshold": pfer_bound_at_threshold,
        "selection_frequency": dict(sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))),
        "theme_selection_frequency": dict(sorted(theme_freq.items(), key=lambda kv: (-kv[1], kv[0]))),
        "stable_features": stable,
        "stable_feature_count": len(stable),
    }


def evaluate_case(frame, candidates):
    x = frame[candidates].astype(float).reset_index(drop=True)
    y = frame["inflyttning_per_1000"].to_numpy(float)
    groups = frame["kommun_kod"].to_numpy()
    assert np.isfinite(x.to_numpy()).all()
    assert np.isfinite(y).all()

    outer = GroupKFold(OUTER_SPLITS)
    errors = {"ridge": [], "enet_1se": [], "stable_enet": []}
    folds = []
    enet_selection = Counter()
    stability_sum = defaultdict(float)
    stability_n = Counter()

    theme_by_feature = {f: pool[f].get("theme", "needs_classification") for f in candidates}

    for fold, (tr, te) in enumerate(outer.split(x, y, groups), 1):
        tx, vx = x.iloc[tr], x.iloc[te]
        ty, vy = y[tr], y[te]
        tg = groups[tr]

        ridge = make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
        ridge.fit(tx, ty)
        pred_ridge = ridge.predict(vx)
        errors["ridge"].extend((vy - pred_ridge).tolist())

        chosen, minimum, curve = choose_enet_one_se(tx, ty, tg, candidates)
        enet = fit_enet(tx, ty, chosen["alpha"], chosen["l1_ratio"])
        pred_enet = enet.predict(vx)
        active = active_features(enet, candidates)
        enet_selection.update(active)
        errors["enet_1se"].extend((vy - pred_enet).tolist())

        stability = cpss_stability(
            tx.reset_index(drop=True),
            ty,
            tg,
            candidates,
            chosen["alpha"],
            chosen["l1_ratio"],
            theme_by_feature,
        )
        for f, v in stability["selection_frequency"].items():
            stability_sum[f] += v
            stability_n[f] += 1

        stable_features = stability["stable_features"]
        stable_metrics = None
        if stable_features:
            stable_model = fit_enet(
                tx[stable_features],
                ty,
                chosen["alpha"],
                chosen["l1_ratio"],
            )
            pred_stable = stable_model.predict(vx[stable_features])
            stable_err = vy - pred_stable
            errors["stable_enet"].extend(stable_err.tolist())
            stable_metrics = {
                "rmse": rmse(vy, pred_stable),
                "mae": mae(vy, pred_stable),
                "active_after_refit": active_features(stable_model, stable_features),
            }

        folds.append(
            {
                "fold": fold,
                "ridge": {"rmse": rmse(vy, pred_ridge), "mae": mae(vy, pred_ridge)},
                "enet_1se": {
                    "rmse": rmse(vy, pred_enet),
                    "mae": mae(vy, pred_enet),
                    "alpha": chosen["alpha"],
                    "l1_ratio": chosen["l1_ratio"],
                    "active_count": len(active),
                    "active_features": active,
                    "inner_minimum": minimum,
                    "inner_1se_choice": chosen,
                },
                "stability": stability,
                "stable_enet": stable_metrics,
            }
        )

    summary = {}
    for key in ("ridge", "enet_1se"):
        e = np.asarray(errors[key], float)
        summary[key] = {
            "rmse": float(np.sqrt(np.mean(e * e))),
            "mae": float(np.mean(np.abs(e))),
        }

    if len(errors["stable_enet"]) == len(y):
        e = np.asarray(errors["stable_enet"], float)
        summary["stable_enet"] = {
            "rmse": float(np.sqrt(np.mean(e * e))),
            "mae": float(np.mean(np.abs(e))),
            "all_outer_folds_available": True,
        }
    else:
        summary["stable_enet"] = {
            "rmse": None,
            "mae": None,
            "all_outer_folds_available": False,
            "reason": "PFER=1 stability threshold infeasible or no features passed it in at least one outer fold.",
        }

    avg_stability = {
        f: stability_sum[f] / stability_n[f]
        for f in candidates
        if stability_n[f] > 0
    }

    return {
        "rows": len(frame),
        "candidate_count": len(candidates),
        "summary": summary,
        "outer_folds": folds,
        "enet_outer_selection_frequency": dict(enet_selection.most_common()),
        "mean_cpss_selection_frequency": dict(
            sorted(avg_stability.items(), key=lambda kv: (-kv[1], kv[0]))
        ),
    }


out = {
    "status": "research_only_nested_1se_elastic_net_stability",
    "created_for": "neutral model-size and variable lock-in",
    "production_changed": False,
    "protocol": {
        "outer_cv": f"GroupKFold({OUTER_SPLITS}) by municipality",
        "inner_cv": f"GroupKFold({INNER_SPLITS}) by municipality",
        "ridge_alpha": RIDGE_ALPHA,
        "elastic_net_l1_ratios": L1_RATIOS,
        "elastic_net_alphas": EN_ALPHAS,
        "complexity_rule": "1-SE; among acceptable hyperparameters choose lowest mean active count, then stronger penalty",
        "stability_method": "complementary half-group pairs using fixed outer-fold 1-SE hyperparameters",
        "cpss_pairs": CPSS_PAIRS,
        "pfer_target": PFER_TARGET,
        "stability_error_bound": "Meinshausen-Buehlmann conservative PFER bound",
        "no_prefilter_by_pairwise_correlation": True,
        "candidate_universe_frozen": True,
    },
    "results": {},
    "limitations": [
        "This is research-only geographic validation on already reviewed historical years, not a fresh untouched future-year holdout.",
        "PFER control relies on assumptions behind the conservative stability-selection bound; if the bound is infeasible, no forced arbitrary threshold is substituted.",
        "Theme stability is descriptive and does not force one representative per correlated group.",
        "Elastic Net nonzero coefficients are predictive selections, not causal effects or conventional post-selection inference.",
    ],
}

for window, years in {"five": range(2019, 2024), "three": range(2021, 2024)}.items():
    q = p[p.year.isin(years)].sort_values(["kommun_kod", "year"]).reset_index(drop=True)
    complete = [
        name
        for name in pool
        if name in q and all(coverage[name][str(year)] == 290 for year in years)
    ]
    for branch in ("blind", "forecast"):
        candidates = sorted(
            name
            for name in complete
            if branch == "forecast" or pool[name]["blind_model_eligible_subject_to_audit"]
        )
        key = f"{window}_{branch}"
        print(key, len(candidates), flush=True)
        out["results"][key] = evaluate_case(q, candidates)
        print(key, out["results"][key]["summary"], flush=True)

(D / "neutral_nested_1se_elastic_net_stability.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
