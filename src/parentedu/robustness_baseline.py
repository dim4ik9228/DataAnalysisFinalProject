"""Контроль відтворення незмінних M4/M10 перед аналізом стійкості."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from parentedu.models import adjust_hypotheses, contrast_test, fit_model


def _unique(table, keys, label):
    if not set(keys) <= set(table) or table[keys].isna().any().any():
        raise ValueError(f"Baseline: missing keys in {label}")
    if table.duplicated(keys).any():
        raise ValueError(f"Baseline: duplicate keys in {label}")


def _order_hash(values):
    payload = json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def check_baseline(frames, config, table_dir: Path):
    """Звірити P05 у пам'яті; невідповідність зупиняє роботу без експорту."""
    table_dir = Path(table_dir)
    coefficients = pd.read_csv(table_dir / "replication_coefficients.csv")
    models = pd.read_csv(table_dir / "replication_models.csv")
    hypotheses = pd.read_csv(table_dir / "replication_hypotheses.csv")
    row_path = table_dir.parents[1] / "data/processed/replication_diagnostics.csv"
    rows = pd.read_csv(row_path)
    _unique(coefficients, ["subject", "model_id", "covariance_type", "term"], "coefficients")
    _unique(models, ["subject", "model_id"], "models")
    _unique(hypotheses, ["subject", "model_id", "family"], "hypotheses")
    _unique(rows, ["subject", "model_id", "record_id"], "row diagnostics")
    checks, tests = [], []

    def compare(subject, model_id, metric, term, expected, actual):
        numeric = isinstance(actual, (int, float, np.number)) and not isinstance(actual, bool)
        if numeric:
            try:
                difference = abs(float(expected) - float(actual))
                matches = bool(
                    np.isfinite(float(expected))
                    and np.isfinite(float(actual))
                    and np.isclose(expected, actual, atol=1e-10, rtol=1e-10)
                )
            except (ValueError, TypeError):
                difference, matches = np.nan, False
        else:
            difference, matches = np.nan, expected == actual
        checks.append(
            {
                "subject": subject,
                "base_model_id": model_id,
                "metric": metric,
                "term": term,
                "expected": expected,
                "actual": actual,
                "absolute_difference": difference,
                "matches": matches,
            }
        )

    for subject, model_id in (("mat", "M4"), ("por", "M10")):
        definitions = [d for d in config["models"] if d["id"] == model_id]
        if len(definitions) != 1 or definitions[0]["subject"] != subject:
            raise ValueError("Baseline: invalid model definition")
        fitted = fit_model(frames[subject], definitions[0], config)
        result = fitted["result"]
        expected_model = models.loc[models.subject.eq(subject) & models.model_id.eq(model_id)]
        if len(expected_model) != 1:
            raise ValueError("Baseline: missing model")
        for metric, actual in fitted["summary"].items():
            compare(subject, model_id, metric, "", expected_model.iloc[0][metric], actual)
        exported = coefficients.loc[
            coefficients.subject.eq(subject)
            & coefficients.model_id.eq(model_id)
            & coefficients.covariance_type.eq("HC3")
        ]
        if set(exported.term) != set(fitted["X"]):
            raise ValueError("Baseline: missing or unexpected coefficient terms")
        ci = result.conf_int(alpha=1 - config["inference"]["confidence_level"])
        for term in fitted["X"]:
            old = exported.loc[exported.term.eq(term)].iloc[0]
            actuals = {
                "estimate": result.params[term],
                "std_error": result.bse[term],
                "ci_low": ci.loc[term, 0],
                "ci_high": ci.loc[term, 1],
                "p_value": result.pvalues[term],
                "nobs": result.nobs,
                "adjusted_r2": result.rsquared_adj,
                "use_t": False,
                "variant": "baseline",
            }
            for metric, actual in actuals.items():
                compare(subject, model_id, metric, term, old[metric], actual)
        previous_rows = rows.loc[rows.subject.eq(subject) & rows.model_id.eq(model_id)]
        current_rows = fitted["row_diagnostics"]
        compare(
            subject,
            model_id,
            "ordered_record_id_hash",
            "",
            _order_hash(previous_rows.record_id),
            _order_hash(current_rows.record_id),
        )
        if len(previous_rows) != len(current_rows):
            raise ValueError("Baseline: row diagnostic N mismatch")
        for metric in ("fitted", "residual", "leverage", "cooks_distance"):
            for record_id, expected, actual in zip(
                current_rows.record_id, previous_rows[metric], current_rows[metric], strict=True
            ):
                compare(subject, model_id, metric, record_id, expected, actual)
        for family, weights, label, distribution in (
            ("H1", {"Medu_4": 1}, "Medu_4=0", "normal"),
            ("H2", {"Medu_4": 1, "Fedu_4": -1}, "Medu_4-Fedu_4=0", "chi2"),
        ):
            test = contrast_test(
                result, weights, config["inference"]["confidence_level"], distribution
            )
            tests.append(
                dict(
                    subject=subject,
                    model_id=model_id,
                    family=family,
                    contrast=label,
                    covariance_type="HC3",
                    use_t=False,
                    **test,
                )
            )
    actual_tests = adjust_hypotheses(pd.DataFrame(tests), config["inference"]["alpha"])
    expected_keys = set(map(tuple, actual_tests[["subject", "model_id", "family"]].to_numpy()))
    if set(map(tuple, hypotheses[["subject", "model_id", "family"]].to_numpy())) != expected_keys:
        raise ValueError("Baseline: missing or unexpected hypothesis keys")
    for test in actual_tests.to_dict("records"):
        old = hypotheses.loc[
            hypotheses.subject.eq(test["subject"])
            & hypotheses.model_id.eq(test["model_id"])
            & hypotheses.family.eq(test["family"])
        ].iloc[0]
        for metric, actual in test.items():
            if metric not in ("subject", "model_id", "family"):
                compare(
                    test["subject"], test["model_id"], metric, test["family"], old[metric], actual
                )
    table = pd.DataFrame(checks)
    if not table.matches.all():
        failed = table.loc[~table.matches, ["base_model_id", "metric", "term"]]
        raise ValueError(f"Baseline P05 mismatch: {failed.head(8).to_dict('records')}")
    return table
