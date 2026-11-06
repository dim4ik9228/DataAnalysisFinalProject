"""Синтетичний експорт P05 та захист контрольної звірки."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from parentedu.config import load_config
from parentedu.models import build_model_tables
from parentedu.robustness_baseline import check_baseline


@pytest.fixture
def baseline(tmp_path):
    rng = np.random.default_rng(638)
    config = deepcopy(load_config())
    config["expected_sample"] = {"mat": 160, "por": 160}
    frames = {}
    for subject in ("mat", "por"):
        n = 160
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
            }
        )
        frame["G3"] = 7 + 1.5 * frame.Medu.eq(4) + rng.normal(size=n)
        frames[subject] = frame
    tables = build_model_tables(frames, config)
    table_dir = tmp_path / "outputs/tables"
    table_dir.mkdir(parents=True)
    for name in ("coefficients", "models", "hypotheses"):
        tables[name].to_csv(
            table_dir / f"replication_{name}.csv", index=False, float_format="%.17g"
        )
    local = tmp_path / "data/processed"
    local.mkdir(parents=True)
    tables["row_diagnostics"].to_csv(
        local / "replication_diagnostics.csv", index=False, float_format="%.17g"
    )
    return frames, config, table_dir


def test_current_baseline_and_order_hashes(baseline):
    frames, config, table_dir = baseline
    originals = {key: frame.copy(deep=True) for key, frame in frames.items()}
    table = check_baseline(frames, config, table_dir)
    assert table.matches.all()
    hashes = table.loc[table.metric.eq("ordered_record_id_hash")]
    assert len(hashes) == 2 and hashes.actual.str.len().eq(64).all()
    assert table.loc[table.metric.eq("estimate") & table.term.str.startswith("Medu_")].shape[0] == 6
    for key in frames:
        pd.testing.assert_frame_equal(frames[key], originals[key])


@pytest.mark.parametrize(
    "kind,change",
    [
        ("coefficients", "estimate"),
        ("coefficients", "std_error"),
        ("coefficients", "nobs"),
        ("coefficients", "missing"),
        ("coefficients", "duplicate"),
        ("models", "formula"),
        ("models", "terms"),
        ("models", "rank"),
        ("hypotheses", "estimate"),
        ("hypotheses", "p_value"),
        ("hypotheses", "p_holm"),
        ("hypotheses", "missing"),
        ("hypotheses", "duplicate"),
    ],
)
def test_reject_changed_export(baseline, kind, change):
    frames, config, table_dir = baseline
    path = table_dir / f"replication_{kind}.csv"
    table = pd.read_csv(path)
    target = table.index[table.model_id.eq("M4")][0]
    if change == "missing":
        table = table.drop(target)
    elif change == "duplicate":
        table = pd.concat([table, table.loc[[target]]], ignore_index=True)
    elif change in ("formula", "terms"):
        table.loc[target, change] = "changed"
    else:
        table.loc[target, change] += 1
    table.to_csv(path, index=False, float_format="%.17g")
    with pytest.raises(ValueError, match="Baseline"):
        check_baseline(frames, config, table_dir)


@pytest.mark.parametrize(
    "change", ["order", "fitted", "residual", "leverage", "cooks_distance", "duplicate", "missing"]
)
def test_reject_row_changes(baseline, change):
    frames, config, table_dir = baseline
    path = table_dir.parents[1] / "data/processed/replication_diagnostics.csv"
    table = pd.read_csv(path)
    indices = table.index[table.model_id.eq("M4")]
    if change == "order":
        table.loc[indices[:2]] = table.loc[indices[:2][::-1]].to_numpy()
    elif change == "duplicate":
        table = pd.concat([table, table.loc[[indices[0]]]], ignore_index=True)
    elif change == "missing":
        table = table.drop(indices[0])
    else:
        table.loc[indices[0], change] += 0.1
    table.to_csv(path, index=False, float_format="%.17g")
    with pytest.raises(ValueError, match="Baseline"):
        check_baseline(frames, config, table_dir)


def test_reject_reordered_input(baseline):
    frames, config, table_dir = baseline
    frames["mat"] = frames["mat"].iloc[::-1].copy()
    with pytest.raises(ValueError, match="Baseline"):
        check_baseline(frames, config, table_dir)
