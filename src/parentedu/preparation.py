"""Prepare auditable replication samples without fitting statistical models."""

from __future__ import annotations

import os
import tempfile
from copy import deepcopy
from pathlib import Path

import pandas as pd

from parentedu.config import load_config
from parentedu.paths import DATA_PROCESSED, DATA_REFERENCE, TABLES

TECHNICAL_COLUMNS = ["subject", "source_file", "source_row", "record_id"]


class PreparationError(ValueError):
    """A preparation invariant is violated."""


class SampleSizeMismatch(PreparationError):
    """The rule-defined sample differs from the frozen publication sample size."""

    def __init__(self, result: dict):
        self.comparison = result["comparison"].copy()
        self.flow = result["flow"].copy()
        self.membership = result["membership"].copy()
        super().__init__("Replication N differs from the reference; no sample was exported.")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PreparationError(message)


def _check_frame(frame: pd.DataFrame, subject: str) -> None:
    required = ["Medu", "Fedu", "G3", *TECHNICAL_COLUMNS]
    _require(frame.columns.is_unique, f"Duplicate columns in {subject}")
    _require(set(required).issubset(frame.columns), f"Missing preparation columns in {subject}")
    _require(not frame[required].isna().any().any(), f"Missing required values in {subject}")
    _require(frame["subject"].eq(subject).all(), f"Mixed subject values in {subject}")
    _require(frame["record_id"].is_unique, f"Repeated record_id in {subject}")
    _require(frame["source_row"].is_unique, f"Repeated source_row in {subject}")
    for column, lower, upper in (("Medu", 0, 4), ("Fedu", 0, 4), ("G3", 0, 20)):
        values = frame[column]
        _require(pd.api.types.is_integer_dtype(values), f"{column} must be validated integers")
        _require(values.between(lower, upper).all(), f"Invalid {column} in {subject}")
    source_rows = frame["source_row"]
    _require(pd.api.types.is_integer_dtype(source_rows), "source_row must contain integers")
    _require(source_rows.gt(0).all(), "source_row must be positive")
    expected_ids = source_rows.map(lambda row: f"{subject}:{row:06d}")
    _require(frame["record_id"].eq(expected_ids).all(), "record_id/source_row mismatch")
    _require(frame["source_file"].eq(f"student-{subject}.csv").all(), "Wrong source filename")


def _expected_counts(reference_path: Path, config: dict) -> dict[str, int]:
    reference = pd.read_csv(reference_path, keep_default_na=False)
    _require({"subject", "model_id", "nobs"}.issubset(reference), "Invalid reference schema")
    expected = {}
    for subject in config["replication"]["subjects"]:
        selected = reference.loc[reference["subject"].eq(subject), "nobs"]
        _require(not selected.empty, f"Missing reference N for {subject}")
        _require(pd.api.types.is_integer_dtype(selected), f"Noninteger reference N for {subject}")
        _require(selected.nunique() == 1, f"Inconsistent reference N for {subject}")
        count = int(selected.iloc[0])
        configured = config["expected_sample"][subject]
        _require(type(configured) is int and count == configured, f"Config/reference N: {subject}")
        expected[subject] = count
    return expected


def prepare_samples(
    validated: dict[str, pd.DataFrame],
    config: dict | None = None,
    reference_path: Path = DATA_REFERENCE / "table8_models.csv",
) -> dict:
    """Apply only the frozen parental-education rule and audit every source record.

    The full validated layer is retained, including education zero and G3 zero.
    A mismatch raises SampleSizeMismatch with aggregate diagnostic tables, rather
    than trimming observations to the publication's expected N.
    """
    config = deepcopy(load_config() if config is None else config)
    protocol = config["replication"]
    _require(protocol["exclude_parent_education_zero"] is True, "Unsupported education rule")
    _require(protocol["exclude_zero_grades"] is False, "G3 zero must be retained")
    _require(protocol.get("train_test_split", False) is False, "No train/test split is allowed")
    subjects = protocol["subjects"]
    _require(len(subjects) == len(set(subjects)), "Duplicate configured subjects")
    _require(set(subjects) == {"mat", "por"}, "Expected mat and por separately")
    _require(set(validated) == set(subjects), "Input/config subjects differ")
    expected = _expected_counts(Path(reference_path), config)
    full, replication, memberships, flow, comparisons = {}, {}, [], [], []
    for subject in subjects:
        frame = validated[subject].copy(deep=True)
        _check_frame(frame, subject)
        full[subject] = frame
        mother_zero = frame["Medu"].eq(0)
        father_zero = frame["Fedu"].eq(0)
        both_zero = mother_zero & father_zero
        include = frame["Medu"].ge(1) & frame["Fedu"].ge(1)
        replication[subject] = frame.loc[include].copy()
        member = frame[TECHNICAL_COLUMNS].copy()
        member["include_in_replication"] = include.to_numpy()
        member["exclusion_reason"] = ""
        member.loc[mother_zero & ~father_zero, "exclusion_reason"] = "Medu0"
        member.loc[father_zero & ~mother_zero, "exclusion_reason"] = "Fedu0"
        member.loc[both_zero, "exclusion_reason"] = "both0"
        memberships.append(member)
        n_before, n_after = len(frame), int(include.sum())
        original_columns = [name for name in frame.columns if name not in TECHNICAL_COLUMNS]
        flow.append(
            {
                "subject": subject,
                "stage": "education_filter",
                "n_before": n_before,
                "n_excluded": n_before - n_after,
                "n_after": n_after,
                "rule": "Medu>=1 & Fedu>=1",
                "medu_zero": int(mother_zero.sum()),
                "fedu_zero": int(father_zero.sum()),
                "both_zero": int(both_zero.sum()),
                "g3_zero_before": int(frame["G3"].eq(0).sum()),
                "g3_zero_after": int(frame.loc[include, "G3"].eq(0).sum()),
                "duplicate_rows_original": int(frame.duplicated(subset=original_columns).sum()),
            }
        )
        comparisons.append(
            {
                "subject": subject,
                "n_raw": n_before,
                "n_excluded": n_before - n_after,
                "n_ours": n_after,
                "n_original": expected[subject],
                "n_config": config["expected_sample"][subject],
                "status": "match" if n_after == expected[subject] else "mismatch",
                "filter": "Medu>=1 & Fedu>=1",
                "education_codes_retained": "1|2|3|4",
                "education_reference": protocol["education_reference"],
                "g3_zero_policy": "retain",
                "train_test_split": False,
                "imputation": "none",
                "duplicate_policy": "retain",
            }
        )
    result = {
        "validated": full,
        "replication": replication,
        "membership": pd.concat(memberships, ignore_index=True),
        "flow": pd.DataFrame(flow),
        "comparison": pd.DataFrame(comparisons),
        "expected_sample": expected,
        "ready_for_export": True,
    }
    if not result["comparison"]["status"].eq("match").all():
        result["ready_for_export"] = False
        raise SampleSizeMismatch(result)
    return result


def read_prepared_csv(path: Path, schema: dict | None = None) -> pd.DataFrame:
    """Restore schema types and stable provenance from a prepared UTF-8 CSV."""
    if schema is None:
        from parentedu.data import load_schema

        schema = load_schema()
    specs = schema["columns"]
    original = [item["name"] for item in specs]
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    _require(list(frame.columns) == original + TECHNICAL_COLUMNS, "Prepared CSV column order")
    for spec in specs:
        name = spec["name"]
        values = frame[name]
        if spec["dtype"] == "integer":
            _require(values.str.fullmatch(r"[+-]?\d+").all(), f"Noninteger CSV: {name}")
            frame[name] = pd.to_numeric(values, errors="raise").astype("int64")
            if "min" in spec:
                _require(frame[name].ge(spec["min"]).all(), f"Out-of-range CSV: {name}")
            if "max" in spec:
                _require(frame[name].le(spec["max"]).all(), f"Out-of-range CSV: {name}")
        else:
            _require(spec["dtype"] == "categorical", f"Unknown schema dtype: {name}")
            _require(values.ne("").all(), f"Empty CSV value: {name}")
        if "allowed" in spec:
            _require(frame[name].isin(spec["allowed"]).all(), f"Invalid CSV category: {name}")
    _require(frame["source_row"].str.fullmatch(r"\d+").all(), "Invalid CSV source_row")
    frame["source_row"] = pd.to_numeric(frame["source_row"], errors="raise").astype("int64")
    subjects = frame["subject"].unique()
    _require(len(subjects) == 1 and subjects[0] in ("mat", "por"), "Prepared CSV subject")
    _check_frame(frame, str(subjects[0]))
    return frame


def _validate_export_result(result: dict) -> None:
    _require(result.get("ready_for_export") is True, "Preparation has not passed sample checks")
    _require(result["comparison"]["status"].eq("match").all(), "Sample comparison failed")
    members = result["membership"]
    for subject, full in result["validated"].items():
        _check_frame(full, subject)
        sample = result["replication"][subject]
        _check_frame(sample, subject)
        expected = full.loc[full["Medu"].ge(1) & full["Fedu"].ge(1)]
        _require(sample.equals(expected), f"Replication layer was modified: {subject}")
        _require(len(sample) == result["expected_sample"][subject], f"Sample N changed: {subject}")
        membership = members.loc[members["subject"].eq(subject)]
        _require(membership["record_id"].tolist() == full["record_id"].tolist(), "Membership order")
        included_ids = membership.loc[membership["include_in_replication"], "record_id"].tolist()
        _require(included_ids == sample["record_id"].tolist(), "Membership filter mismatch")


def export_samples(
    result: dict,
    processed_dir: Path = DATA_PROCESSED,
    tables_dir: Path = TABLES,
    schema: dict | None = None,
) -> dict[str, Path]:
    """Write deterministic CSV artifacts after validating all layers and read-backs.

    All temporary CSVs are verified before any destination is replaced. Raw data
    and reference files are never changed by this function.
    """
    _validate_export_result(result)
    processed_dir, tables_dir = Path(processed_dir), Path(tables_dir)
    frames = {}
    for subject in result["validated"]:
        for layer in ("validated", "replication"):
            frames[f"{subject}_{layer}"] = (
                processed_dir / f"student_{subject}_{layer}.csv",
                result[layer][subject],
                True,
            )
    frames["membership"] = (processed_dir / "sample_membership.csv", result["membership"], False)
    frames["flow"] = (tables_dir / "sample_flow.csv", result["flow"], False)
    frames["comparison"] = (
        tables_dir / "original_vs_ours_data.csv",
        result["comparison"],
        False,
    )
    temporary = []
    try:
        for destination, frame, is_sample in frames.values():
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(
                prefix=".preparation-", suffix=".csv", dir=destination.parent
            )
            os.close(fd)
            staging = Path(name)
            temporary.append((staging, destination))
            staging.write_text(
                frame.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline="\n"
            )
            if is_sample:
                restored = read_prepared_csv(staging, schema=schema)
                pd.testing.assert_frame_equal(
                    frame.reset_index(drop=True),
                    restored,
                    check_dtype=False,
                    check_categorical=False,
                )
            else:
                restored = pd.read_csv(staging, keep_default_na=False)
                pd.testing.assert_frame_equal(
                    frame.reset_index(drop=True), restored, check_dtype=False
                )
        for staging, destination in temporary:
            os.replace(staging, destination)
    finally:
        for staging, _ in temporary:
            staging.unlink(missing_ok=True)
    return {key: item[0] for key, item in frames.items()}
