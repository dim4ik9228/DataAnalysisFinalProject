"""Математичні та вибіркові інваріанти P05 на синтетичних даних."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from parentedu.config import load_config
from parentedu.models import (
    adjust_hypotheses,
    build_design,
    build_model_tables,
    contrast_test,
    fit_model,
    smoke_check_m1,
)


@pytest.fixture
def inputs():
    rng = np.random.default_rng(42)
    n = 240
    frame = pd.DataFrame(
        {
            "record_id": [f"mat:{i}" for i in range(n)],
            "subject": "mat",
            "Medu": rng.integers(1, 5, n),
            "Fedu": rng.integers(1, 5, n),
            "age": rng.integers(15, 21, n),
            "sex": rng.choice(["M", "F"], n),
            "school": rng.choice(["MS", "GP"], n),
            "guardian": rng.choice(["other", "mother", "father"], n),
        },
        index=np.arange(n) * 2,
    )
    frame["G3"] = 5 + 2 * frame["Medu"].eq(4) + rng.normal(size=n)
    config = deepcopy(load_config())
    config["expected_sample"] = {"mat": n, "por": n}
    return frame, config


def test_design_explicit_reference_and_order(inputs):
    frame, config = inputs
    X, y = build_design(frame, config["models"][3], config)
    assert list(X) == [
        "intercept",
        "Medu_2",
        "Medu_3",
        "Medu_4",
        "Fedu_2",
        "Fedu_3",
        "Fedu_4",
        "age",
        "sex_F",
        "school_GP",
        "guardian_mother",
        "guardian_father",
    ]
    assert X.index.equals(frame.index) and y.index.equals(frame.index)
    assert X["intercept"].eq(1).all()
    assert X.loc[frame.Medu.eq(1), ["Medu_2", "Medu_3", "Medu_4"]].eq(0).all().all()
    np.testing.assert_array_equal(X.sex_F, frame.sex.eq("F"))
    np.testing.assert_array_equal(X.school_GP, frame.school.eq("GP"))


def test_ols_and_hc3_independent_matrix_algebra(inputs):
    frame, config = inputs
    fit = smoke_check_m1(frame, config)
    X, y, result = fit["X"].to_numpy(), fit["y"].to_numpy(), fit["result"]
    beta = np.linalg.solve(X.T @ X, X.T @ y)
    residual = y - X @ beta
    bread = np.linalg.inv(X.T @ X)
    h = np.einsum("ij,jk,ik->i", X, bread, X)
    meat = X.T @ (X * (residual / (1 - h))[:, None] ** 2)
    np.testing.assert_allclose(result.params, beta, atol=1e-11)
    np.testing.assert_allclose(result.cov_params(), bread @ meat @ bread, atol=1e-11)
    np.testing.assert_allclose(
        result.conf_int()[0], beta - stats.norm.ppf(0.975) * result.bse, atol=1e-11
    )
    for covariance, other in fit["covariance_results"].items():
        np.testing.assert_allclose(other.params, beta, atol=1e-11)
        assert not other.use_t and other.cov_type == covariance
    assert list(fit["row_diagnostics"].record_id) == list(frame.record_id)


def test_contrast_includes_covariance(inputs):
    frame, config = inputs
    result = fit_model(frame, config["models"][3], config)["result"]
    test = contrast_test(result, {"Medu_4": 1, "Fedu_4": -1})
    covariance = result.cov_params()
    variance = covariance.loc["Medu_4", "Medu_4"] + covariance.loc["Fedu_4", "Fedu_4"]
    variance -= 2 * covariance.loc["Medu_4", "Fedu_4"]
    assert test["std_error"] == pytest.approx(np.sqrt(variance))
    assert test["p_value"] == pytest.approx(stats.chi2.sf(test["statistic"], 1))
    assert abs(covariance.loc["Medu_4", "Fedu_4"]) > 1e-6


def test_holm_separate_families_and_verdicts():
    table = pd.DataFrame(
        {
            "family": ["H1", "H1", "H2", "H2"],
            "p_value": [0.01, 0.04, 0.03, 0.9],
            "estimate": [1, -1, 1, 1],
        }
    )
    result = adjust_hypotheses(table)
    np.testing.assert_allclose(result.p_holm, [0.02, 0.04, 0.06, 0.9])
    assert list(result.verdict) == [
        "expected_supported",
        "opposite_evidence",
        "insufficient_evidence",
        "insufficient_evidence",
    ]


@pytest.mark.parametrize("change", ["missing", "unknown", "absent", "duplicate", "n", "inf"])
def test_invalid_inputs_fail_without_dropping(inputs, change):
    frame, config = inputs
    if change == "missing":
        frame.loc[0, "G3"] = np.nan
    elif change == "unknown":
        frame.loc[0, "Medu"] = 0
    elif change == "absent":
        frame["Fedu"] = 1
    elif change == "duplicate":
        frame.loc[2, "record_id"] = frame.loc[0, "record_id"]
    elif change == "n":
        frame = frame.iloc[:-1]
    else:
        frame.loc[0, "G3"] = np.inf
    with pytest.raises(ValueError):
        fit_model(frame, config["models"][0], config)


def test_rank_deficiency_is_error(inputs):
    frame, config = inputs
    frame["Fedu"] = frame["Medu"]
    with pytest.raises(ValueError, match="рангу"):
        fit_model(frame, config["models"][0], config)


def test_zero_df_is_error(inputs):
    frame, config = inputs
    # Seven independent patterns for seven model parameters.
    frame = frame.iloc[:7].copy()
    frame["Medu"] = [1, 2, 3, 4, 1, 1, 1]
    frame["Fedu"] = [1, 1, 1, 1, 2, 3, 4]
    config["expected_sample"]["mat"] = 7
    with pytest.raises(ValueError, match="df"):
        fit_model(frame, config["models"][0], config)


def test_unit_leverage_is_error(inputs):
    frame, config = inputs
    frame["Medu"] = 1
    frame.loc[frame.index[:3], "Medu"] = [2, 3, 4]
    with pytest.raises(ValueError, match="Leverage"):
        fit_model(frame, config["models"][0], config)


def test_all_tables_and_no_input_mutation(inputs):
    frame, config = inputs
    original = frame.copy(deep=True)
    por = frame.copy()
    por["subject"] = "por"
    por["record_id"] = por.record_id.str.replace("mat", "por")
    tables = build_model_tables({"mat": frame, "por": por}, config)
    assert len(tables["models"]) == 8
    assert len(tables["hypotheses"]) == 4
    assert len(tables["coefficients"]) == 3 * 2 * (7 + 9 + 10 + 12)
    assert set(tables["coefficients"].covariance_type) == {"HC3", "HC1", "nonrobust"}
    assert len(tables["row_diagnostics"]) == 8 * len(frame)
    assert not tables["vif"].term.eq("intercept").any()
    pd.testing.assert_frame_equal(original, frame)
