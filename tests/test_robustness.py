"""Інваріанти P06 на синтетичних даних, без учнівських файлів."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from parentedu.config import load_config
from parentedu.robustness import (
    NotEstimableError,
    build_robustness_tables,
    build_variant_design,
    fit_variant,
    h3_change,
    select_variant_frame,
)


@pytest.fixture
def inputs():
    config = deepcopy(load_config())
    layers = {"validated": {}, "replication": {}}
    for subject, seed in (("mat", 11), ("por", 12)):
        rng = np.random.default_rng(seed)
        n = 320
        frame = pd.DataFrame(
            {
                "record_id": [f"{subject}:{i}" for i in range(n)],
                "subject": subject,
                "Medu": rng.integers(1, 5, n),
                "Fedu": rng.integers(1, 5, n),
                "age": rng.integers(15, 21, n),
                "sex": rng.choice(["M", "F"], n),
                "school": rng.choice(["MS", "GP"], n),
                "guardian": rng.choice(["other", "mother", "father"], n),
                "studytime": rng.integers(1, 5, n),
            }
        )
        frame["G3"] = 5 + frame.Medu + rng.normal(size=n)
        frame.loc[0, "G3"] = 0
        layers["replication"][subject] = frame
        extra = frame.iloc[:20].copy()
        extra["record_id"] = [f"{subject}:extra:{i}" for i in range(20)]
        extra.loc[extra.index[:10], "Medu"] = 0
        extra.loc[extra.index[10:], "Fedu"] = 0
        layers["validated"][subject] = pd.concat([frame, extra], ignore_index=True)
    config["expected_sample"] = {"mat": 320, "por": 320}
    return layers, config


def test_independent_frames_and_terms(inputs):
    layers, config = inputs
    definition = config["models"][3]
    baseline = layers["replication"]["mat"]
    r1 = select_variant_frame(layers, "mat", "R1")
    X, _ = build_variant_design(r1, definition, config, "R1")
    assert "Medu_0" in X and "Fedu_0" in X and "Medu_1" not in X
    assert list(r1.record_id[: len(baseline)]) == list(baseline.record_id)
    r2 = select_variant_frame(layers, "mat", "R2")
    assert list(r2.record_id) == list(baseline.loc[baseline.G3.ne(0), "record_id"])
    for variant in ("R3", "R5"):
        frame = select_variant_frame(layers, "mat", variant)
        pd.testing.assert_frame_equal(frame, baseline)
        X, _ = build_variant_design(frame, definition, config, variant)
        if variant == "R3":
            assert "Medu_ordinal" in X and "Medu_4" not in X
            np.testing.assert_array_equal(X.Medu_ordinal, baseline.Medu)
        else:
            assert set(X).issuperset({"studytime_2", "studytime_3", "studytime_4"})
            assert "studytime_1" not in X
    frame = select_variant_frame(layers, "mat", "R4", "MS")
    X, _ = build_variant_design(frame, definition, config, "R4")
    assert "school_GP" not in X and "guardian_father" in X


def test_hc3_matches_independent_statsmodels(inputs):
    layers, config = inputs
    frame = layers["replication"]["mat"]
    fit = fit_variant(frame, config["models"][3], config, "R5")
    independent = sm.OLS(frame.G3, fit["X"]).fit(cov_type="HC3", use_t=False)
    np.testing.assert_allclose(fit["result"].params, independent.params)
    np.testing.assert_allclose(fit["result"].cov_params(), independent.cov_params())
    assert not fit["result"].use_t


def test_complete_tables_rng_and_immutability(inputs):
    layers, config = inputs
    original = deepcopy(layers)
    np.random.seed(314)
    state = np.random.get_state()
    tables = build_robustness_tables(layers, config)
    assert np.array_equal(state[1], np.random.get_state()[1])
    assert len(tables["specifications"]) == 16
    assert len(tables["summary"]) == 28
    assert len(tables["placebo"]) == len(tables["h3"]) == 2
    assert tables["summary"].query("variant == 'R3'").delta_beta.isna().all()
    assert (
        tables["summary"]
        .query("variant == 'R3'")
        .comparison_reason.eq("incomparable_estimand")
        .all()
    )
    for subject, offset in (("mat", 101), ("por", 102)):
        local = tables["noise"].query("subject == @subject")
        expected = np.random.default_rng(config["project"]["seed"] + offset).normal(size=320)
        np.testing.assert_array_equal(local.noise, expected)
    for layer in layers:
        for subject in layers[layer]:
            pd.testing.assert_frame_equal(layers[layer][subject], original[layer][subject])
    repeated = build_robustness_tables(layers, config)
    for key in tables:
        pd.testing.assert_frame_equal(tables[key], repeated[key])


@pytest.mark.parametrize(
    "before,after,delta,sign",
    [(2, 1, -1, False), (-2, -1, -1, False), (-2, 3, 1, True), (2, -2, 0, True)],
)
def test_h3_signed_absolute(before, after, delta, sign):
    assert h3_change(before, after) == {"delta_abs": delta, "sign_change": sign}


def test_school_failures_are_explicit_and_general_rank_failure_raises(inputs):
    layers, config = inputs
    frame = layers["replication"]["mat"]
    frame["school"] = "GP"
    frame.loc[:45, "school"] = "MS"
    tables = build_robustness_tables(layers, config)
    failed = tables["summary"].query("subject == 'mat' and variant == 'R4' and school == 'MS'")
    assert len(failed) == 2 and failed.reason.eq("min_subgroup_n").all()
    assert failed.estimate.isna().all()
    frame["studytime"] = 1
    with pytest.raises(NotEstimableError, match="rank_deficient"):
        build_robustness_tables(layers, config)


def test_fixed_missing_school_category_is_rank_failure(inputs):
    layers, config = inputs
    frame = layers["replication"]["mat"].query("school == 'MS'").copy()
    frame["guardian"] = "mother"
    X, _ = build_variant_design(frame, config["models"][3], config, "R4")
    assert "guardian_father" in X and X.guardian_father.eq(0).all()
    with pytest.raises(NotEstimableError, match="rank_deficient"):
        fit_variant(frame, config["models"][3], config, "R4")


def test_school_count_gate_is_per_parent_and_boundary_five(inputs):
    layers, config = inputs
    frame = layers["replication"]["mat"]
    frame["school"] = "GP"
    frame.loc[:99, "school"] = "MS"
    frame.loc[:99, "Medu"] = np.tile([2, 3, 4, 4], 25)
    frame.loc[:3, "Medu"] = 1
    tables = build_robustness_tables(layers, config)
    rows = tables["summary"].query("subject == 'mat' and variant == 'R4' and school == 'MS'")
    mother = rows.loc[rows.parent.eq("Medu")].iloc[0]
    father = rows.loc[rows.parent.eq("Fedu")].iloc[0]
    assert mother.model_status == "available" and mother.status == "not_estimable"
    assert mother.reason == "min_compared_category_n" and pd.isna(mother.estimate)
    assert father.status == "available"
    frame.loc[4, "Medu"] = 1
    tables = build_robustness_tables(layers, config)
    mother = (
        tables["summary"]
        .query("subject == 'mat' and variant == 'R4' and school == 'MS' and parent == 'Medu'")
        .iloc[0]
    )
    assert mother.reference_n == 5 and mother.status == "available"


def test_school_n_boundary_and_unexpected_errors(inputs, monkeypatch):
    layers, config = inputs
    frame = layers["replication"]["mat"]
    frame["school"] = "GP"
    frame.loc[:49, "school"] = "MS"
    tables = build_robustness_tables(layers, config)
    row = (
        tables["specifications"]
        .query("subject == 'mat' and variant == 'R4' and school == 'MS'")
        .iloc[0]
    )
    assert row.nobs == 50 and row.model_status == "available"
    import parentedu.robustness as engine

    original = engine.fit_variant

    def broken(frame, definition, config, variant, noise=None):
        if variant == "R4":
            raise RuntimeError("unexpected bug")
        return original(frame, definition, config, variant, noise)

    monkeypatch.setattr(engine, "fit_variant", broken)
    with pytest.raises(RuntimeError, match="unexpected bug"):
        build_robustness_tables(layers, config)


def test_technical_df_and_leverage_guards(inputs):
    layers, config = inputs
    frame = layers["replication"]["mat"]
    definition = config["models"][3]
    config["robustness"]["max_leverage"] = 0
    with pytest.raises(NotEstimableError, match="max_leverage"):
        fit_variant(frame, definition, config, "R5")
    # Saturated, full-rank ordinal design has zero residual degrees of freedom.
    tiny = frame.iloc[:7].copy()
    tiny.loc[:, "Medu"] = [1, 1, 1, 1, 1, 1, 2]
    tiny.loc[:, "Fedu"] = [1, 1, 1, 1, 1, 2, 1]
    tiny.loc[:, "age"] = [16, 16, 16, 16, 17, 16, 16]
    tiny.loc[:, "sex"] = ["M", "M", "M", "F", "M", "M", "M"]
    tiny.loc[:, "school"] = ["MS", "MS", "GP", "MS", "MS", "MS", "MS"]
    tiny.loc[:, "guardian"] = ["other", "mother", "other", "other", "other", "other", "other"]
    reduced = {**definition, "controls": ["age", "sex", "school", "guardian"]}
    # guardian_father is fixed and absent, so rank failure must remain explicit.
    with pytest.raises(NotEstimableError, match="rank_deficient"):
        fit_variant(tiny, reduced, config, "R3")


def test_full_rank_saturated_design_rejects_zero_df(inputs):
    layers, config = inputs
    frame = layers["replication"]["mat"].iloc[:8].copy()
    frame["Medu"] = [1, 2, 1, 1, 1, 1, 1, 1]
    frame["Fedu"] = [1, 1, 2, 1, 1, 1, 1, 1]
    frame["age"] = [16, 16, 16, 17, 16, 16, 16, 16]
    frame["sex"] = ["M", "M", "M", "M", "F", "M", "M", "M"]
    frame["school"] = ["MS", "MS", "MS", "MS", "MS", "GP", "MS", "MS"]
    frame["guardian"] = ["other", "other", "other", "other", "other", "other", "mother", "father"]
    with pytest.raises(NotEstimableError, match="nonpositive_residual_df"):
        fit_variant(frame, config["models"][3], config, "R3")


def test_education_diagnostic_counts_preserve_all_levels(inputs):
    layers, config = inputs
    tables = build_robustness_tables(layers, config)
    for row in tables["diagnostics"].itertuples(index=False):
        frame = select_variant_frame(layers, row.subject, row.variant, row.school)
        for parent in ("Medu", "Fedu"):
            assert sum(getattr(row, f"{parent}_{level}_n") for level in range(5)) == row.nobs
            for level in range(5):
                assert getattr(row, f"{parent}_{level}_n") == frame[parent].eq(level).sum()
    r1 = tables["diagnostics"].query("variant == 'R1'")
    assert r1.Medu_0_n.gt(0).all() and r1.Fedu_0_n.gt(0).all()


def test_empty_school_group_retains_explicit_failure(inputs):
    layers, config = inputs
    # Preserve baseline estimability while constructing an empty R4 candidate.
    from unittest.mock import patch

    import parentedu.robustness as engine

    original = engine.select_variant_frame

    def empty_ms(layers, subject, variant, school=""):
        frame = original(layers, subject, variant, school)
        return frame.iloc[:0].copy() if variant == "R4" and school == "MS" else frame

    with patch.object(engine, "select_variant_frame", empty_ms):
        tables = build_robustness_tables(layers, config)
    failed = tables["diagnostics"].query("variant == 'R4' and school == 'MS'")
    assert len(failed) == 2
    assert failed.nobs.eq(0).all() and failed["rank"].eq(0).all()
    assert failed.model_status.eq("not_estimable").all()
    assert failed.reason.eq("min_subgroup_n").all()
    assert failed.filter(regex=r"[MF]edu_[0-4]_n").eq(0).all().all()
    summary = tables["summary"].query("variant == 'R4' and school == 'MS'")
    assert len(summary) == 4 and summary.estimate.isna().all()
