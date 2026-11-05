"""Critical sample-selection and export invariants on synthetic records."""

from copy import deepcopy

import pandas as pd
import pytest

from parentedu.config import load_config
from parentedu.preparation import (
    PreparationError,
    SampleSizeMismatch,
    export_samples,
    prepare_samples,
    read_prepared_csv,
)


@pytest.fixture
def schema():
    return {
        "columns": [
            {"name": "Medu", "dtype": "integer", "min": 0, "max": 4},
            {"name": "Fedu", "dtype": "integer", "min": 0, "max": 4},
            {"name": "G3", "dtype": "integer", "min": 0, "max": 20},
            {"name": "school", "dtype": "categorical", "allowed": ["GP", "MS"]},
            {"name": "studytime", "dtype": "integer", "allowed": [1, 2, 3, 4]},
        ]
    }


def make_frame(subject, values):
    frame = pd.DataFrame(values, columns=["Medu", "Fedu", "G3"])
    frame["school"] = "GP"
    frame["studytime"] = 1
    frame["subject"] = subject
    frame["source_file"] = f"student-{subject}.csv"
    frame["source_row"] = range(1, len(frame) + 1)
    frame["record_id"] = [f"{subject}:{i:06d}" for i in frame["source_row"]]
    return frame


@pytest.fixture
def inputs():
    return {
        "mat": make_frame(
            "mat", [(1, 1, 0), (2, 2, 10), (0, 1, 0), (1, 0, 8), (0, 0, 0), (1, 1, 0)]
        ),
        "por": make_frame("por", [(4, 4, 11), (0, 4, 5), (3, 2, 0)]),
    }


@pytest.fixture
def settings(tmp_path):
    config = deepcopy(load_config())
    config["expected_sample"] = {"mat": 3, "por": 2}
    reference = tmp_path / "models.csv"
    pd.DataFrame(
        [
            {"subject": "mat", "model_id": "M1", "nobs": 3},
            {"subject": "mat", "model_id": "M4", "nobs": 3},
            {"subject": "por", "model_id": "M7", "nobs": 2},
            {"subject": "por", "model_id": "M10", "nobs": 2},
        ]
    ).to_csv(reference, index=False)
    return config, reference


def test_exact_filter_keeps_zero_grades_duplicates_and_order(inputs, settings):
    config, reference = settings
    before = {key: value.copy(deep=True) for key, value in inputs.items()}
    result = prepare_samples(inputs, config, reference)
    assert result["replication"]["mat"]["source_row"].tolist() == [1, 2, 6]
    assert result["replication"]["mat"]["G3"].tolist() == [0, 10, 0]
    assert result["replication"]["por"]["source_row"].tolist() == [1, 3]
    assert len(result["validated"]["mat"]) == 6
    assert result["validated"]["mat"]["Medu"].eq(0).sum() == 2
    flow = result["flow"].set_index("subject").loc["mat"]
    assert (flow["medu_zero"], flow["fedu_zero"], flow["both_zero"]) == (2, 2, 1)
    assert flow["n_excluded"] == 3  # Union, not the sum 2+2.
    assert flow["duplicate_rows_original"] == 1
    assert (flow["g3_zero_before"], flow["g3_zero_after"]) == (4, 2)
    reasons = result["membership"].set_index("record_id")["exclusion_reason"]
    assert reasons.loc["mat:000003"] == "Medu0"
    assert reasons.loc["mat:000004"] == "Fedu0"
    assert reasons.loc["mat:000005"] == "both0"
    assert reasons.loc["mat:000001"] == ""
    for key in inputs:
        pd.testing.assert_frame_equal(inputs[key], before[key])
    assert result["comparison"]["status"].eq("match").all()


def test_mismatch_is_explicit_and_does_not_trim(inputs, settings, tmp_path):
    config, reference = settings
    inputs["mat"].loc[0, "Medu"] = 0
    with pytest.raises(SampleSizeMismatch) as caught:
        prepare_samples(inputs, config, reference)
    comparison = caught.value.comparison.set_index("subject")
    assert comparison.loc["mat", "n_ours"] == 2
    assert comparison.loc["mat", "status"] == "mismatch"
    assert len(caught.value.membership) == 9
    assert not (tmp_path / "processed").exists()


def test_config_reference_disagreement_fails_before_preparation(inputs, settings):
    config, reference = settings
    config["expected_sample"]["mat"] = 4
    with pytest.raises(PreparationError, match="Config/reference N"):
        prepare_samples(inputs, config, reference)


def test_inconsistent_model_reference_counts_fail(inputs, settings):
    config, reference = settings
    table = pd.read_csv(reference)
    table.loc[table["model_id"].eq("M4"), "nobs"] = 4
    table.to_csv(reference, index=False)
    with pytest.raises(PreparationError, match="Inconsistent reference N"):
        prepare_samples(inputs, config, reference)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "wrong_code",
        "wrong_type",
        "bad_id",
        "repeat_id",
        "mixed_subject",
        "missing_value",
    ],
)
def test_invalid_preparation_inputs_are_not_silently_fixed(inputs, settings, change):
    config, reference = settings
    frame = inputs["mat"]
    if change == "missing":
        inputs["mat"] = frame.drop(columns="Medu")
    elif change == "wrong_code":
        frame.loc[0, "Fedu"] = -1
    elif change == "wrong_type":
        inputs["mat"]["Medu"] = frame["Medu"].astype(str)
    elif change == "bad_id":
        frame.loc[0, "record_id"] = "mat:999999"
    elif change == "missing_value":
        frame.loc[0, "G3"] = float("nan")
    elif change == "repeat_id":
        frame.loc[0, "record_id"] = frame.loc[1, "record_id"]
    else:
        frame.loc[0, "subject"] = "por"
    with pytest.raises(PreparationError):
        prepare_samples(inputs, config, reference)


def test_export_roundtrip_and_repeated_bytes(inputs, settings, schema, tmp_path):
    config, reference = settings
    result = prepare_samples(inputs, config, reference)
    processed, tables = tmp_path / "processed", tmp_path / "tables"
    files = export_samples(result, processed, tables, schema)
    first = {name: path.read_bytes() for name, path in files.items()}
    assert set(files) == {
        "mat_validated",
        "mat_replication",
        "por_validated",
        "por_replication",
        "membership",
        "flow",
        "comparison",
    }
    for subject in ("mat", "por"):
        for layer in ("validated", "replication"):
            restored = read_prepared_csv(files[f"{subject}_{layer}"], schema)
            pd.testing.assert_frame_equal(result[layer][subject].reset_index(drop=True), restored)
    assert files["membership"].parent == processed
    assert files["comparison"].parent == tables
    assert all(b"\r\n" not in content for content in first.values())
    export_samples(result, processed, tables, schema)
    assert first == {name: path.read_bytes() for name, path in files.items()}
    assert not list(tmp_path.rglob(".preparation-*"))


def test_modified_layer_cannot_be_exported(inputs, settings, schema, tmp_path):
    config, reference = settings
    result = prepare_samples(inputs, config, reference)
    result["replication"]["mat"] = result["replication"]["mat"].iloc[1:]
    with pytest.raises(PreparationError, match="modified"):
        export_samples(result, tmp_path / "processed", tmp_path / "tables", schema)
    assert not (tmp_path / "processed").exists()


def test_unready_result_cannot_be_exported(inputs, settings, schema, tmp_path):
    config, reference = settings
    result = prepare_samples(inputs, config, reference)
    result["ready_for_export"] = False
    with pytest.raises(PreparationError, match="not passed"):
        export_samples(result, tmp_path / "processed", tmp_path / "tables", schema)
    assert not (tmp_path / "processed").exists()


def test_invalid_prepared_category_is_rejected(inputs, settings, schema, tmp_path):
    config, reference = settings
    result = prepare_samples(inputs, config, reference)
    files = export_samples(result, tmp_path / "processed", tmp_path / "tables", schema)
    path = files["mat_validated"]
    text = path.read_text(encoding="utf-8").replace(",GP,", ",UNKNOWN,", 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(PreparationError, match="category"):
        read_prepared_csv(path, schema)
