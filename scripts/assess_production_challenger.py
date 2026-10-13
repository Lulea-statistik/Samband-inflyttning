#!/usr/bin/env python3
"""#135: conservative, auditable promotion gate for the fair forecast challenger.

Reads the output from the existing #134 paired municipality-cluster bootstrap.
Never changes active model parameters or promotes a post-hoc stable model.
"""
import json
from pathlib import Path

SOURCE = Path("docs/data/model.json")
DEST = Path("docs/data/production_decision.json")
METRICS = ("rmse", "mae", "p90_abs_error", "worst_decile_mae")


def assess(data):
    test = data.get("forecast_production_candidate_test", {})
    result = {
        "evaluation": "135: fair challenger production readiness",
        "status": "not_approved",
        "active_model": "incumbent",
        "challenger": "dynamic_fair_reselection",
        "candidate_test_status": test.get("status", "missing"),
        "checks": {},
        "caveats": [
            "The stable post-hoc model is not an independent validation.",
            "Repeated use of the same holdout years for development can bias estimates.",
            "No automatic production promotion is performed.",
        ],
    }
    if test.get("status") != "tested":
        result["reason"] = "Production comparison missing or incomplete."
        return result
    boot = test.get("municipality_cluster_bootstrap", {}).get("dynamic", {})
    pooled = test.get("pooled_metrics", {})
    inc = pooled.get("incumbent", {})
    challenger = pooled.get("dynamic", {})
    for metric in METRICS:
        b = boot.get(metric, {})
        low = b.get("ci95_low")
        high = b.get("ci95_high")
        incumbent_value = inc.get(metric)
        challenger_value = challenger.get(metric)
        result["checks"][metric] = {
            "incumbent": incumbent_value,
            "challenger": challenger_value,
            "improvement": (
                incumbent_value - challenger_value
                if isinstance(incumbent_value, (int, float))
                and isinstance(challenger_value, (int, float))
                else None
            ),
            "ci95_low": low,
            "ci95_high": high,
            "credible_improvement": isinstance(low, (int, float)) and low > 0,
            "no_credible_deterioration": isinstance(high, (int, float)) and high >= 0,
        }
    folds = test.get("folds", [])
    result["folds"] = []
    for fold in folds:
        inc_fold, ch_fold = fold.get("incumbent", {}), fold.get("dynamic", {})
        delta = {
            metric: inc_fold[metric] - ch_fold[metric]
            if isinstance(inc_fold.get(metric), (int, float))
            and isinstance(ch_fold.get(metric), (int, float))
            else None
            for metric in METRICS
        }
        result["folds"].append({
            "holdout_year": fold.get("holdout_year"),
            "improvements": delta,
            "rmse_improved": delta["rmse"] is not None and delta["rmse"] > 0,
            "tail_not_worse": all(
                delta[m] is not None and delta[m] >= 0
                for m in ("p90_abs_error", "worst_decile_mae")
            ),
        })
    sufficient_folds = len(result["folds"]) >= 2
    mean_good = all(result["checks"][m]["credible_improvement"]
                    for m in ("rmse", "mae"))
    tail_safe = all(result["checks"][m]["no_credible_deterioration"]
                    for m in ("p90_abs_error", "worst_decile_mae"))
    fold_safe = sufficient_folds and all(f["rmse_improved"] and f["tail_not_worse"]
                                        for f in result["folds"])
    result["criteria"] = {
        "at_least_two_temporal_holdouts": sufficient_folds,
        "rmse_and_mae_positive_lower_95ci": mean_good,
        "tail_error_no_negative_upper_95ci": tail_safe,
        "no_year_with_rmse_or_tail_regression": fold_safe,
    }
    result["status"] = "eligible_for_independent_validation" if all(
        result["criteria"].values()
    ) else "not_approved"
    result["reason"] = (
        "All screening criteria pass, but a new independent validation "
        "period is required before any production change."
        if result["status"] == "eligible_for_independent_validation"
        else "At least one prespecified robustness or uncertainty criterion fails."
    )
    return result


def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    result = assess(data)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(json.dumps({"status": result["status"], "criteria": result.get("criteria"),
                      "reason": result["reason"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
