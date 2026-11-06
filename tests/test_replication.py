"""Publication comparison contracts without student records or model fitting."""

from copy import deepcopy
from decimal import Decimal

import pandas as pd
import pytest

from parentedu.config import load_config
from parentedu.paths import ROOT
from parentedu.replication import _cell, compare_replication, validate_references


@pytest.fixture
def inputs():
    config = load_config()
    refs = validate_references(ROOT / "data/reference", config)
    rows = []
    for covariance in ["HC3", "nonrobust", "HC1"]:
        for r in refs["coefficients"].to_dict("records"):
            rows.append(
                {k: r[k] for k in ["subject", "model_id", "term", "estimate", "std_error"]}
                | {"covariance_type": covariance}
            )
        for r in refs["models"].to_dict("records"):
            rows.append(
                {
                    "subject": r["subject"],
                    "model_id": r["model_id"],
                    "term": "intercept",
                    "estimate": "1",
                    "std_error": "1",
                    "covariance_type": covariance,
                }
            )
    return pd.DataFrame(rows), refs["models"].copy(), refs, config


def test_decimal_inclusive_boundary():
    tolerance = Decimal("0.0005000001")
    for sign in [-1, 1]:
        inside = Decimal("0.098") + sign * tolerance
        assert _cell("mat", "M1", "Medu_2", "estimate", "0.098", inside, tolerance)["matches"]
        outside = inside + sign * Decimal("0.00000000001")
        assert not _cell("mat", "M1", "Medu_2", "estimate", "0.098", outside, tolerance)["matches"]


def test_complete_and_se_excluded(inputs):
    coefficients, models, refs, config = inputs
    coefficients["std_error"] = "999"
    result = compare_replication(coefficients, models, refs, config)
    assert len(result["comparison"]) == 84
    assert len(result["se_comparison"]) == 204
    assert set(result["verdicts"].verdict) == {"complete_match"}
    assert not result["se_comparison"].matches.any()
    assert set(result["se_comparison"].original_method) == {"not_identified"}


@pytest.mark.parametrize("kind", ["missing", "duplicate", "extra"])
def test_coverage_failures(inputs, kind):
    coefficients, models, refs, config = inputs
    if kind == "missing":
        coefficients = coefficients.iloc[1:]
    elif kind == "duplicate":
        coefficients = pd.concat([coefficients, coefficients.iloc[:1]])
    else:
        coefficients.loc[0, "term"] = "unexpected"
    with pytest.raises(ValueError):
        compare_replication(coefficients, models, refs, config)


def test_reference_missing_duplicate_and_config(inputs, tmp_path):
    _, _, refs, config = inputs
    import shutil

    shutil.copytree(ROOT / "data/reference", tmp_path / "reference")
    path = tmp_path / "reference/table8_coefficients.csv"
    for frame in [
        refs["coefficients"].iloc[1:],
        pd.concat([refs["coefficients"].iloc[1:], refs["coefficients"].iloc[1:2]]),
    ]:
        frame.to_csv(path, index=False)
        with pytest.raises(ValueError):
            validate_references(tmp_path / "reference", config)
    changed = deepcopy(config)
    changed["replication"]["intercept"] = False
    with pytest.raises(ValueError):
        compare_replication(*inputs[:3], changed)


def test_partial_and_sample_forces_global_mismatch(inputs):
    coefficients, models, refs, config = inputs
    coefficients.loc[coefficients.term == "Medu_2", "estimate"] = "999"
    result = compare_replication(coefficients, models, refs, config)
    assert result["verdicts"].iloc[-1].verdict == "partial_match"
    models.loc[0, "nobs"] = "389"
    result = compare_replication(coefficients, models, refs, config)
    assert result["verdicts"].iloc[0].verdict == "mismatch"
    assert result["verdicts"].iloc[-1].verdict == "mismatch"
    assert result["verdicts"].iloc[-1].mismatch_models == 1


def test_all_mismatch(inputs):
    coefficients, models, refs, config = inputs
    models["nobs"] = "1"
    result = compare_replication(coefficients, models, refs, config)
    assert set(result["verdicts"].verdict) == {"mismatch"}
    assert result["verdicts"].iloc[-1].mismatch_models == 8
