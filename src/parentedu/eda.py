"""Descriptive P04 tables; no fitting, hypothesis tests or p-values."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from parentedu.config import load_config
from parentedu.data import load_schema

NUMERIC_VARIABLES = ("age", "absences", "G1", "G2", "G3")
CORRELATION_VARIABLES = (
    "Medu",
    "Fedu",
    "studytime",
    "age",
    "absences",
    "failures",
    "G1",
    "G2",
    "G3",
)
CATEGORY_VARIABLES = ("Medu", "Fedu", "studytime", "sex", "school", "guardian")
EDUCATION_LABELS = {
    0: "Без освіти",
    1: "Початкова",
    2: "5–9 класи",
    3: "Середня",
    4: "Вища",
}
STUDYTIME_LABELS = {1: "<2 год", 2: "2–5 год", 3: "5–10 год", 4: ">10 год"}
NOMINAL_LABELS = {
    "sex": {"F": "Жіноча (F)", "M": "Чоловіча (M)"},
    "guardian": {"mother": "Мати", "father": "Батько", "other": "Інший"},
}
TABLE_NAMES = (
    "sample_overview",
    "numeric_summary",
    "category_counts",
    "grade_counts",
    "parent_cross",
    "grade_by_education",
    "correlations",
    "group_screen",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _proportion(count: int, denominator: int) -> float:
    return count / denominator if denominator else np.nan


def sample_stats(values: pd.Series) -> dict:
    """Sample SD and linear quartiles; empty/singleton groups remain explicit."""
    valid = values.dropna().astype(float)
    n = len(valid)
    result = {key: np.nan for key in ("mean", "std", "min", "q1", "median", "q3", "max")}
    if n:
        result.update(
            {
                "mean": float(valid.mean()),
                "min": float(valid.min()),
                "q1": float(valid.quantile(0.25, interpolation="linear")),
                "median": float(valid.quantile(0.5, interpolation="linear")),
                "q3": float(valid.quantile(0.75, interpolation="linear")),
                "max": float(valid.max()),
            }
        )
    if n > 1:
        result["std"] = float(valid.std(ddof=1))
    return {"n": n, **result, "status": "empty" if n == 0 else "singleton" if n == 1 else "ok"}


def _label(variable: str, level: int | str) -> str:
    if variable in ("Medu", "Fedu"):
        return EDUCATION_LABELS[int(level)]
    if variable == "studytime":
        return STUDYTIME_LABELS[int(level)]
    return NOMINAL_LABELS.get(variable, {}).get(level, str(level))


def _check_layers(layers: dict, config: dict) -> None:
    _require(set(layers) == {"validated", "replication"}, "Expected both named data layers")
    required = set(CORRELATION_VARIABLES) | set(CATEGORY_VARIABLES)
    for layer in ("validated", "replication"):
        _require(set(layers[layer]) == {"mat", "por"}, "Expected separate mat/por frames")
        for subject in ("mat", "por"):
            frame = layers[layer][subject]
            _require(frame.columns.is_unique, "Duplicate EDA columns")
            _require(required.issubset(frame.columns), f"Missing EDA fields: {layer}/{subject}")
            _require(
                not frame[list(required)].isna().any().any(), "EDA inputs contain missing data"
            )
            if "subject" in frame:
                _require(frame["subject"].eq(subject).all(), "Mixed subject values")
            levels = (
                [0, *config["replication"]["education_levels"]]
                if layer == "validated"
                else config["replication"]["education_levels"]
            )
            for parent in ("Medu", "Fedu"):
                _require(frame[parent].isin(levels).all(), f"Invalid education in {layer}")


def _correlations(frame: pd.DataFrame, layer: str, subject: str) -> list[dict]:
    # pandas returns coefficients only, unlike a hypothesis-testing API.
    matrix = frame[list(CORRELATION_VARIABLES)].corr(method="spearman")
    result = []
    for first in CORRELATION_VARIABLES:
        for second in CORRELATION_VARIABLES:
            pair = frame[[first]] if first == second else frame[[first, second]]
            pair = pair.dropna()
            n = len(pair)
            constant = pair.nunique().le(1).any()
            if n < 2:
                status, coefficient = "insufficient_pairs", np.nan
            elif constant:
                status, coefficient = "constant", np.nan
            else:
                coefficient = float(matrix.loc[first, second])
                status = "ok" if math.isfinite(coefficient) else "undefined"
            result.append(
                {
                    "layer": layer,
                    "subject": subject,
                    "variable1": first,
                    "variable2": second,
                    "coefficient": coefficient,
                    "pair_n": n,
                    "status": status,
                }
            )
    return result


def build_eda_tables(
    layers: dict, schema: dict | None = None, config: dict | None = None
) -> dict[str, pd.DataFrame]:
    """Describe named layers, with substantive summaries restricted to replication.

    Input validation/provenance is the workflow's responsibility. This function
    also rejects missing relevant values or ambiguous layer/subject assignments.
    It never changes input frames, categories, sample membership or the protocol.
    """
    schema = load_schema() if schema is None else schema
    config = load_config() if config is None else config
    _check_layers(layers, config)
    specifications = {column["name"]: column for column in schema["columns"]}
    education_levels = config["replication"]["education_levels"]
    result = {name: [] for name in TABLE_NAMES}
    for layer in ("validated", "replication"):
        for subject in ("mat", "por"):
            frame = layers[layer][subject]
            denominator = len(frame)
            for variable in ("studytime", "sex", "school", "guardian"):
                _require(
                    frame[variable].isin(specifications[variable]["allowed"]).all(),
                    f"Unknown category: {layer}/{subject}/{variable}",
                )
            original = [name for name in specifications if name in frame]
            result["sample_overview"].append(
                {
                    "layer": layer,
                    "subject": subject,
                    "n": denominator,
                    "zero_g3": int(frame["G3"].eq(0).sum()),
                    "education_zero": int((frame["Medu"].eq(0) | frame["Fedu"].eq(0)).sum()),
                    "original_columns": len(original),
                    "duplicate_excess": int(frame[original].duplicated().sum()),
                }
            )
            variables = ("Medu", "Fedu") if layer == "validated" else CATEGORY_VARIABLES
            for variable in variables:
                if variable in ("Medu", "Fedu"):
                    levels = [0, *education_levels] if layer == "validated" else education_levels
                else:
                    levels = specifications[variable]["allowed"]
                for level in levels:
                    count = int(frame[variable].eq(level).sum())
                    result["category_counts"].append(
                        {
                            "layer": layer,
                            "subject": subject,
                            "variable": variable,
                            "level": level,
                            "label": _label(variable, level),
                            "count": count,
                            "denominator": denominator,
                            "proportion": _proportion(count, denominator),
                            "status": "observed" if count else "empty_category",
                        }
                    )
            if layer != "replication":
                continue
            for variable in NUMERIC_VARIABLES:
                result["numeric_summary"].append(
                    {
                        "layer": layer,
                        "subject": subject,
                        "variable": variable,
                        **sample_stats(frame[variable]),
                    }
                )
            for grade in range(21):
                count = int(frame["G3"].eq(grade).sum())
                result["grade_counts"].append(
                    {
                        "layer": layer,
                        "subject": subject,
                        "grade": grade,
                        "count": count,
                        "denominator": denominator,
                        "proportion": _proportion(count, denominator),
                    }
                )
            for mother in education_levels:
                row_total = int(frame["Medu"].eq(mother).sum())
                for father in education_levels:
                    count = int((frame["Medu"].eq(mother) & frame["Fedu"].eq(father)).sum())
                    result["parent_cross"].append(
                        {
                            "layer": layer,
                            "subject": subject,
                            "Medu": mother,
                            "Fedu": father,
                            "count": count,
                            "row_total": row_total,
                            "column_total": int(frame["Fedu"].eq(father).sum()),
                            "denominator": denominator,
                            "row_proportion": _proportion(count, row_total),
                            "overall_proportion": _proportion(count, denominator),
                            "status": "observed" if count else "empty_combination",
                        }
                    )
            for parent in ("Medu", "Fedu"):
                for level in education_levels:
                    grades = frame.loc[frame[parent].eq(level), "G3"]
                    stats = sample_stats(grades)
                    result["grade_by_education"].append(
                        {
                            "layer": layer,
                            "subject": subject,
                            "parent": parent,
                            "education_level": level,
                            **{
                                key: stats[key]
                                for key in ("n", "mean", "std", "median", "q1", "q3")
                            },
                            "zero_g3": int(grades.eq(0).sum()),
                            "status": stats["status"],
                        }
                    )
            result["correlations"].extend(_correlations(frame, layer, subject))
            min_n = config["robustness"]["min_subgroup_n"]
            min_category_n = config["robustness"]["min_compared_category_n"]
            reference = config["replication"]["education_reference"]
            for school in specifications["school"]["allowed"]:
                group = frame.loc[frame["school"].eq(school)]
                for parent in ("Medu", "Fedu"):
                    reference_n = int(group[parent].eq(reference).sum())
                    target_n = int(group[parent].eq(4).sum())
                    passed = len(group) >= min_n and min(reference_n, target_n) >= min_category_n
                    missing = [
                        str(level)
                        for level in education_levels
                        if not group[parent].eq(level).any()
                    ]
                    result["group_screen"].append(
                        {
                            "layer": layer,
                            "subject": subject,
                            "school": school,
                            "parent": parent,
                            "n": len(group),
                            "reference_n": reference_n,
                            "target_n": target_n,
                            "min_n": min_n,
                            "min_category_n": min_category_n,
                            "counts_screen_pass": passed,
                            "status": "counts_screen_pass" if passed else "counts_screen_fail",
                            "missing_levels": "|".join(missing),
                        }
                    )
    return {name: pd.DataFrame(rows) for name, rows in result.items()}
