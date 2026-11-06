"""Compare estimates with verified publication cells using Decimal precision."""

import csv
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import pandas as pd


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(text: str) -> Decimal:
    return Decimal(re.sub(r"\s", "", text.replace("−", "-")))


def _validate_config(config: dict) -> None:
    expected = [
        ("M1", "mat", 1, []),
        ("M2", "mat", 2, ["age", "sex"]),
        ("M3", "mat", 3, ["age", "sex", "school"]),
        ("M4", "mat", 4, ["age", "sex", "school", "guardian"]),
        ("M7", "por", 7, []),
        ("M8", "por", 8, ["age", "sex"]),
        ("M9", "por", 9, ["age", "sex", "school"]),
        ("M10", "por", 10, ["age", "sex", "school", "guardian"]),
    ]
    actual = [(m["id"], m["subject"], m["source_column"], m["controls"]) for m in config["models"]]
    require(actual == expected, "Changed model specifications")
    for section, fields in {
        "replication": {
            "outcome": "G3",
            "intercept": True,
            "education_reference": 1,
            "education_levels": [1, 2, 3, 4],
            "standard_errors": "unresolved",
            "exclude_parent_education_zero": True,
            "exclude_zero_grades": False,
            "train_test_split": False,
            "missing_policy": "error_no_silent_dropping",
        },
        "reference_categories": {"sex": "M", "school": "MS", "guardian": "other"},
        "expected_sample": {"mat": 390, "por": 637},
        "comparison": {
            "nobs_rule": "exact",
            "rounding_rule": "half_last_printed_unit_plus_epsilon",
            "rounding_epsilon": "0.0000000001",
            "require_all_published_coefficients": True,
            "unknown_original_se_verdict": "not_identified_no_exact_inference_claim",
        },
        "inference": {
            "covariance": "HC3",
            "use_t": False,
            "covariance_sensitivity": ["nonrobust", "HC1"],
            "sensitivity_use_t": False,
        },
    }.items():
        for field, value in fields.items():
            require(config[section][field] == value, f"Changed protocol: {section}.{field}")


def validate_references(reference_dir: Path, config: dict) -> dict[str, pd.DataFrame]:
    """Check reviewed reference cells, exact coverage and source snapshot integrity."""
    _validate_config(config)
    reference = Path(reference_dir)
    coefficients = rows(reference / "table8_coefficients.csv")
    models = rows(reference / "table8_models.csv")
    definitions = {model["id"]: model for model in config["models"]}
    expected_ids = {"M1", "M2", "M3", "M4", "M7", "M8", "M9", "M10"}
    require(set(definitions) == expected_ids, "Wrong model definitions")
    require(len(models) == 8 and len(coefficients) == 68, "Incomplete reference tables")
    keys = [(r["subject"], r["model_id"], r["term"]) for r in coefficients]
    require(len(keys) == len(set(keys)), "Duplicate coefficient keys")
    require(len({r["model_id"] for r in models}) == 8, "Duplicate model rows")
    epsilon = Decimal(config["comparison"]["rounding_epsilon"])
    for row in coefficients:
        definition = definitions[row["model_id"]]
        require(row["subject"] == definition["subject"], "Subject mismatch")
        require(int(row["source_column"]) == definition["source_column"], "Column mismatch")
        require(row["verified"] == "true", "Unreviewed coefficient")
        require(row["significance_marker"] in ("", "*", "**", "***"), "Invalid stars")
        require(number(row["std_error"]) > 0, "Nonpositive standard error")
        for value_field, printed_field, tolerance_field in (
            ("estimate", "estimate_printed", "estimate_tolerance"),
            ("std_error", "se_printed", "se_tolerance"),
        ):
            printed = number(row[printed_field])
            require(number(row[value_field]) == printed, "Printed/numeric mismatch")
            tolerance = Decimal("0.5") * Decimal(10) ** printed.as_tuple().exponent + epsilon
            require(number(row[tolerance_field]) == tolerance, "Wrong rounding tolerance")
        snapshot = (reference / row["source_snapshot"]).resolve()
        require(snapshot.is_relative_to(reference.resolve()), "Invalid snapshot path")
        require(snapshot.is_file(), "Missing source snapshot")
    for row in coefficients + models:
        require(row["source_xml_id"] == "Tab8", "Wrong source table")
        require(
            row["source_url"] == "https://www.nature.com/articles/s41598-025-89394-2/tables/8",
            "Wrong publication source URL",
        )
        require(
            row["source_snapshot"] == "sources/da2025_fulltext.xml", "Wrong publication snapshot"
        )
    for row in coefficients:
        for printed_field, decimals_field in (
            ("estimate_printed", "estimate_decimals"),
            ("se_printed", "se_decimals"),
        ):
            require(
                int(row[decimals_field]) == max(0, -number(row[printed_field]).as_tuple().exponent),
                "Wrong printed decimals",
            )
    base_terms = {f"{parent}_{level}" for parent in ("Medu", "Fedu") for level in (2, 3, 4)}
    for model_id, definition in definitions.items():
        expected = set(base_terms)
        controls = definition["controls"]
        if "age" in controls:
            expected.add("age")
        if "sex" in controls:
            expected.add("sex_F")
        if "school" in controls:
            expected.add("school_GP")
        if "guardian" in controls:
            expected.update(("guardian_mother", "guardian_father"))
        actual = {r["term"] for r in coefficients if r["model_id"] == model_id}
        require(actual == expected, f"Wrong published terms: {model_id}")
    for row in models:
        definition = definitions[row["model_id"]]
        require(row["subject"] == definition["subject"], "Model subject mismatch")
        require(int(row["source_column"]) == definition["source_column"], "Model column mismatch")
        require(row["outcome"] == config["replication"]["outcome"], "Wrong outcome")
        require(int(row["nobs"]) == config["expected_sample"][row["subject"]], "Wrong N")
        require(row["verified"] == "true", "Unreviewed model row")
        snapshot = (reference / row["source_snapshot"]).resolve()
        require(snapshot.is_relative_to(reference.resolve()), "Invalid model snapshot path")
        require(snapshot.is_file(), "Missing model source snapshot")
        printed = number(row["adjusted_r2_printed"])
        require(number(row["adjusted_r2"]) == printed, "Wrong adjusted R-squared")
        tolerance = Decimal("0.5") * Decimal(10) ** printed.as_tuple().exponent + epsilon
        require(number(row["adjusted_r2_tolerance"]) == tolerance, "Wrong R-squared tolerance")
    source_root = reference / "sources"
    manifest = json.loads((source_root / "manifest.json").read_text(encoding="utf-8"))
    require(
        "da2025_fulltext.xml" in {item["file"] for item in manifest},
        "Publication snapshot absent from source manifest",
    )
    for item in manifest:
        path = (source_root / item["file"]).resolve()
        require(path.is_relative_to(source_root.resolve()), "Invalid manifest path")
        content = path.read_bytes()
        require(hashlib.sha256(content).hexdigest() == item["sha256"], "Source hash mismatch")
        if "bytes" in item:
            require(len(content) == item["bytes"], "Source length mismatch")
    return {"coefficients": pd.DataFrame(coefficients), "models": pd.DataFrame(models)}


def _cell(subject, model_id, term, metric, original, ours, tolerance):
    published, replicated, allowed = (
        number(str(original)),
        number(str(ours)),
        number(str(tolerance)),
    )
    require(replicated.is_finite(), "Nonfinite replicated value")
    difference = abs(published - replicated)
    matches = difference <= allowed
    return {
        "subject": subject,
        "model_id": model_id,
        "term": term,
        "metric": metric,
        "original_value": str(original),
        "replicated_value": str(ours),
        "absolute_difference": str(difference),
        "tolerance": str(tolerance),
        "matches": matches,
        "verdict": "match" if matches else "mismatch",
    }


def _keys(frame, columns):
    require(not frame.duplicated(columns).any(), f"Duplicate keys: {columns}")
    require(not frame[columns].isna().any().any(), "Missing keys")
    return set(frame[columns].itertuples(index=False, name=None))


def compare_replication(
    coefficients: pd.DataFrame, models: pd.DataFrame, references: dict, config: dict
) -> dict[str, pd.DataFrame]:
    """Compare all published cells; SE sensitivity never affects numerical verdicts.

    Coverage/specification failures raise ValueError rather than producing a misleading
    numerical comparison. A different sample N forces model and global mismatch.
    """
    _validate_config(config)
    refs, model_refs = references["coefficients"], references["models"]
    key = ["subject", "model_id", "term"]
    expected = _keys(refs, key)
    model_keys = _keys(model_refs, key[:2])
    require(len(expected) == 68 and len(model_keys) == 8, "Incomplete references")
    require(_keys(models, key[:2]) == model_keys, "Wrong model coverage")
    covariances = ["HC3", "nonrobust", "HC1"]
    require(set(coefficients.covariance_type) == set(covariances), "Wrong covariance coverage")
    _keys(coefficients, key + ["covariance_type"])
    intercepts = {(s, m, "intercept") for s, m in model_keys}
    indexed = {}
    for covariance in covariances:
        subset = coefficients.loc[coefficients.covariance_type == covariance]
        require(_keys(subset, key) == expected | intercepts, "Wrong coefficient coverage/terms")
        indexed[covariance] = subset.set_index(key)
    primary = indexed["HC3"]
    for covariance in covariances[1:]:
        other = indexed[covariance]
        require(
            all(
                number(str(primary.loc[k, "estimate"])) == number(str(other.loc[k, "estimate"]))
                for k in expected | intercepts
            ),
            "Estimates changed across covariance methods",
        )
    comparison, se_comparison = [], []
    for row in refs.to_dict("records"):
        k = tuple(row[c] for c in key)
        comparison.append(
            _cell(
                *k,
                "estimate",
                row["estimate_printed"],
                primary.loc[k, "estimate"],
                row["estimate_tolerance"],
            )
        )
        for covariance in covariances:
            cell = _cell(
                *k,
                "std_error",
                row["se_printed"],
                indexed[covariance].loc[k, "std_error"],
                row["se_tolerance"],
            )
            cell.update(covariance_type=covariance, original_method="not_identified")
            se_comparison.append(cell)
    ours_models = models.set_index(key[:2])
    for row in model_refs.to_dict("records"):
        k = tuple(row[c] for c in key[:2])
        ours = ours_models.loc[k]
        require(
            number(str(ours.nobs)) == number(str(ours.nobs)).to_integral_value(),
            "Nonintegral sample size",
        )
        comparison.append(_cell(*k, "", "nobs", row["nobs"], ours.nobs, "0"))
        comparison.append(
            _cell(
                *k,
                "",
                "adjusted_r2",
                row["adjusted_r2_printed"],
                ours.adjusted_r2,
                row["adjusted_r2_tolerance"],
            )
        )
    comparison = pd.DataFrame(comparison)
    verdicts = []
    for definition in config["models"]:
        subject, model_id = definition["subject"], definition["id"]
        cells = comparison.loc[(comparison.subject == subject) & (comparison.model_id == model_id)]
        sample_match = bool(cells.loc[cells.metric == "nobs", "matches"].all())
        count = int(cells.matches.sum())
        verdict = (
            "mismatch"
            if not sample_match or count == 0
            else "complete_match"
            if count == len(cells)
            else "partial_match"
        )
        verdicts.append(
            {
                "subject": subject,
                "model_id": model_id,
                "verdict": verdict,
                "matched_cells": count,
                "total_cells": len(cells),
                "sample_match": sample_match,
                "specification_match": True,
                "original_method": "not_identified",
            }
        )
    counts = {
        status: sum(r["verdict"] == status for r in verdicts)
        for status in ("complete_match", "partial_match", "mismatch")
    }
    global_verdict = (
        "mismatch"
        if not all(r["sample_match"] for r in verdicts)
        else "complete_match"
        if counts["complete_match"] == 8
        else "mismatch"
        if counts["mismatch"] == 8
        else "partial_match"
    )
    for row in verdicts:
        row.update({f"{status}_models": count for status, count in counts.items()})
    verdicts.append(
        dict(
            subject="all",
            model_id="global",
            verdict=global_verdict,
            matched_cells=int(comparison.matches.sum()),
            total_cells=len(comparison),
            sample_match=all(r["sample_match"] for r in verdicts),
            specification_match=True,
            original_method="not_identified",
            **{f"{status}_models": count for status, count in counts.items()},
        )
    )
    return {
        "comparison": comparison,
        "se_comparison": pd.DataFrame(se_comparison),
        "verdicts": pd.DataFrame(verdicts),
    }
