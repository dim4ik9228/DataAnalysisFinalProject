"""Known-value EDA invariants, including empty groups and count-screen boundaries."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from parentedu.config import load_config
from parentedu.eda import CORRELATION_VARIABLES, TABLE_NAMES, build_eda_tables, sample_stats


def example_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Medu": [1, 1, 4, 4],
            "Fedu": [1, 4, 1, 4],
            "studytime": [1, 2, 3, 4],
            "age": [15, 16, 17, 18],
            "absences": [0, 1, 2, 3],
            "failures": [0, 0, 0, 0],
            "G1": [0, 4, 8, 12],
            "G2": [0, 4, 8, 12],
            "G3": [0, 4, 8, 12],
            "sex": ["F", "M", "F", "M"],
            "school": ["GP"] * 4,
            "guardian": ["mother"] * 4,
        }
    )


def layers(frame: pd.DataFrame) -> dict:
    return {
        layer: {subject: frame.copy(deep=True) for subject in ("mat", "por")}
        for layer in ("validated", "replication")
    }


def select(table: pd.DataFrame, **criteria) -> pd.DataFrame:
    selected = table
    for column, value in criteria.items():
        selected = selected.loc[selected[column].eq(value)]
    return selected


def test_numeric_summary_uses_linear_quartiles_and_sample_sd():
    result = build_eda_tables(layers(example_frame()))
    row = select(result["numeric_summary"], subject="mat", variable="G3").iloc[0]
    assert row["n"] == 4
    assert row["mean"] == 6 and row["median"] == 6
    assert row["q1"] == 3 and row["q3"] == 9
    assert row["std"] == pytest.approx(np.sqrt(80 / 3))
    assert row["min"] == 0 and row["max"] == 12


def test_category_denominators_and_missing_levels_are_explicit():
    result = build_eda_tables(layers(example_frame()))
    categories = select(result["category_counts"], subject="mat", layer="replication")
    for _variable, rows in categories.groupby("variable", sort=False):
        assert rows["denominator"].eq(4).all()
        assert rows["count"].sum() == 4
        assert rows["proportion"].sum() == pytest.approx(1)
    education = select(categories, variable="Medu")
    assert education["level"].tolist() == [1, 2, 3, 4]
    absent = select(education, level=2).iloc[0]
    assert absent["count"] == 0 and absent["proportion"] == 0
    assert absent["status"] == "empty_category"


def test_validated_education_zero_does_not_leak_into_primary_summaries():
    inputs = layers(example_frame())
    extra = example_frame().iloc[[0]].copy()
    extra["Medu"], extra["Fedu"], extra["G3"] = 0, 0, 20
    for subject in ("mat", "por"):
        inputs["validated"][subject] = pd.concat(
            [inputs["validated"][subject], extra], ignore_index=True
        )
    result = build_eda_tables(inputs)
    counts = result["category_counts"]
    full_zero = select(counts, layer="validated", subject="mat", variable="Medu", level=0).iloc[0]
    assert full_zero["count"] == 1 and full_zero["denominator"] == 5
    assert not select(counts, layer="replication")["level"].eq(0).any()
    assert result["numeric_summary"]["layer"].eq("replication").all()
    row = select(result["numeric_summary"], subject="mat", variable="G3").iloc[0]
    assert row["mean"] == 6
    assert select(result["sample_overview"], layer="validated", subject="mat")["n"].item() == 5


def test_cross_table_preserves_all_sixteen_cells_and_margins():
    result = build_eda_tables(layers(example_frame()))
    cross = select(result["parent_cross"], subject="mat")
    assert len(cross) == 16 and cross["count"].sum() == 4
    assert cross["denominator"].eq(4).all()
    assert select(cross, Medu=1)["count"].sum() == 2
    assert select(cross, Fedu=4)["count"].sum() == 2
    cell = select(cross, Medu=1, Fedu=4).iloc[0]
    assert cell["count"] == 1 and cell["row_total"] == 2 and cell["column_total"] == 2
    assert cell["row_proportion"] == 0.5 and cell["overall_proportion"] == 0.25
    empty_row = select(cross, Medu=2)
    assert empty_row["count"].eq(0).all() and empty_row["row_proportion"].isna().all()
    assert empty_row["overall_proportion"].eq(0).all()


def test_grade_zero_singleton_and_empty_group_have_different_meanings():
    frame = example_frame().iloc[[0]].copy()
    result = build_eda_tables(layers(frame))
    summary = select(result["grade_by_education"], subject="mat", parent="Medu")
    zero = select(summary, education_level=1).iloc[0]
    assert zero["n"] == 1 and zero["zero_g3"] == 1
    assert zero["mean"] == 0 and zero["median"] == 0
    assert pd.isna(zero["std"]) and zero["status"] == "singleton"
    empty = select(summary, education_level=2).iloc[0]
    assert empty["n"] == 0 and empty["zero_g3"] == 0 and empty["status"] == "empty"
    assert all(pd.isna(empty[key]) for key in ("mean", "std", "median", "q1", "q3"))
    histogram = select(result["grade_counts"], subject="mat")
    assert len(histogram) == 21 and histogram["count"].sum() == 1
    assert select(histogram, grade=0)["count"].item() == 1


def test_group_quantiles_are_from_actual_grades_not_rounded_means():
    result = build_eda_tables(layers(example_frame()))
    group = select(
        result["grade_by_education"], subject="mat", parent="Medu", education_level=1
    ).iloc[0]
    assert group["n"] == 2 and group["median"] == 2
    assert group["q1"] == 1 and group["q3"] == 3
    assert group["std"] == pytest.approx(np.sqrt(8))


def test_spearman_coefficients_only_and_constant_variable_is_undefined():
    result = build_eda_tables(layers(example_frame()))
    correlation = select(result["correlations"], subject="mat")
    assert len(correlation) == len(CORRELATION_VARIABLES) ** 2
    assert set(correlation["variable1"]) == set(CORRELATION_VARIABLES)
    assert not {"sex", "school", "guardian", "source_row", "record_id"} & set(
        correlation["variable1"]
    )
    assert not any("p_value" in column for column in correlation.columns)
    perfect = select(correlation, variable1="G1", variable2="G3").iloc[0]
    assert perfect["coefficient"] == pytest.approx(1) and perfect["pair_n"] == 4
    constant = select(correlation, variable1="failures", variable2="G3").iloc[0]
    assert pd.isna(constant["coefficient"]) and constant["status"] == "constant"
    reverse = select(correlation, variable1="G3", variable2="G1").iloc[0]
    assert reverse["coefficient"] == perfect["coefficient"]


@pytest.mark.parametrize(
    ("n", "reference_n", "target_n", "expected"),
    [(49, 5, 5, False), (50, 4, 5, False), (50, 5, 4, False), (50, 5, 5, True)],
)
def test_count_screen_has_inclusive_50_and_5_boundaries(n, reference_n, target_n, expected):
    frame = pd.concat([example_frame().iloc[[0]]] * n, ignore_index=True)
    frame["Medu"] = [1] * reference_n + [4] * target_n + [2] * (n - reference_n - target_n)
    config = deepcopy(load_config())
    config["robustness"]["min_subgroup_n"] = 50
    config["robustness"]["min_compared_category_n"] = 5
    result = build_eda_tables(layers(frame), config=config)
    screen = select(result["group_screen"], subject="mat", school="GP", parent="Medu").iloc[0]
    assert bool(screen["counts_screen_pass"]) is expected
    assert (
        screen["n"] == n and screen["reference_n"] == reference_n and screen["target_n"] == target_n
    )
    assert screen["min_n"] == 50 and screen["min_category_n"] == 5
    assert "estimable" not in screen["status"]
    absent_school = select(result["group_screen"], subject="mat", school="MS", parent="Medu").iloc[
        0
    ]
    assert absent_school["n"] == 0 and not absent_school["counts_screen_pass"]
    assert absent_school["missing_levels"] == "1|2|3|4"


def test_whole_empty_frame_keeps_categories_and_undefined_statistics():
    result = build_eda_tables(layers(example_frame().iloc[:0]))
    assert set(result) == set(TABLE_NAMES)
    assert result["sample_overview"]["n"].eq(0).all()
    assert result["numeric_summary"]["n"].eq(0).all()
    assert result["numeric_summary"]["mean"].isna().all()
    assert result["category_counts"]["count"].eq(0).all()
    assert result["category_counts"]["proportion"].isna().all()
    assert result["correlations"]["coefficient"].isna().all()


def test_input_frames_and_category_order_are_not_modified():
    inputs = layers(example_frame())
    before = deepcopy(inputs)
    first = build_eda_tables(inputs)
    second = build_eda_tables(inputs)
    for layer in inputs:
        for subject in inputs[layer]:
            pd.testing.assert_frame_equal(inputs[layer][subject], before[layer][subject])
    for name in TABLE_NAMES:
        pd.testing.assert_frame_equal(first[name], second[name])


@pytest.mark.parametrize("kind", ["missing", "education_zero", "unknown_category", "unknown_layer"])
def test_ambiguous_or_invalid_input_fails_before_description(kind):
    inputs = layers(example_frame())
    if kind == "missing":
        inputs["replication"]["mat"].loc[0, "G3"] = np.nan
    elif kind == "education_zero":
        inputs["replication"]["mat"].loc[0, "Medu"] = 0
    elif kind == "unknown_category":
        inputs["replication"]["mat"].loc[0, "sex"] = "unknown"
    else:
        inputs["full"] = inputs.pop("validated")
    with pytest.raises(ValueError):
        build_eda_tables(inputs)


def test_sample_stats_empty_and_singleton_sd_are_not_zero():
    empty = sample_stats(pd.Series([], dtype=float))
    one = sample_stats(pd.Series([0]))
    assert empty["status"] == "empty" and pd.isna(empty["mean"])
    assert one["mean"] == 0 and one["status"] == "singleton" and pd.isna(one["std"])
