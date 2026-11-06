"""Contracts and estimand separation for P06 aggregate-only plots."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from parentedu.robustness_reporting import (
    PARENTS,
    SPECS,
    SUBJECTS,
    _categorical_figure,
    _read_summary,
    render_robustness_figures,
)


@pytest.fixture
def tables(tmp_path):
    rows = []
    for subject in SUBJECTS:
        for variant, school in SPECS:
            for parent in PARENTS:
                ordinal = variant == "R3"
                rows.append(
                    {
                        "subject": subject,
                        "base_model_id": {"mat": "M4", "por": "M10"}[subject],
                        "variant": variant,
                        "school": school,
                        "parent": parent,
                        "term": f"{parent}_{'ordinal' if ordinal else '4'}",
                        "estimand": "ordinal_per_level" if ordinal else "categorical_4_vs_1",
                        "nobs": 100,
                        "estimate": 100 if ordinal else 1,
                        "std_error": 0.1,
                        "ci_low": 99 if ordinal else 0.8,
                        "ci_high": 101 if ordinal else 1.2,
                        "p_value": 0.01,
                        "status": "available",
                        "reason": "",
                    }
                )
    frame = pd.DataFrame(rows)
    mask = (frame.subject == "mat") & (frame.variant == "R4") & (frame.school == "MS")
    frame.loc[mask, ["estimate", "std_error", "ci_low", "ci_high", "p_value"]] = np.nan
    frame.loc[mask, "status"] = "not_estimable"
    frame.loc[mask, "reason"] = "Недостатньо спостережень у категорії"
    frame.to_csv(tmp_path / "robustness_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "subject": s,
                "base_model_id": {"mat": "M4", "por": "M10"}[s],
                "beta_base": 1,
                "beta_augmented": 1,
                "delta_abs": 0,
                "sign_change": False,
                "nobs": 100,
            }
            for s in SUBJECTS
        ]
    ).to_csv(tmp_path / "robustness_h3.csv", index=False)
    return tmp_path


def test_missing_estimates_remain_missing_and_ordinal_not_categorical(tables):
    frame = _read_summary(tables)
    assert frame.loc[frame.status == "not_estimable", "estimate"].isna().all()
    fig = _categorical_figure(frame)
    try:
        for ax in fig.axes:
            assert ax.get_xlim()[1] < 10  # R3's synthetic 100 never enters this estimand's axes.
        labels = " ".join(t.get_text() for ax in fig.axes for t in ax.get_yticklabels())
        assert "Недостатньо" in labels
        assert "N=100" in labels
    finally:
        plt.close(fig)


@pytest.mark.parametrize("change", ["missing", "duplicate", "wrong_estimand", "fake_zero"])
def test_reject_invalid_grid_or_missing_status_values(tables, change):
    path = tables / "robustness_summary.csv"
    frame = pd.read_csv(path, keep_default_na=False)
    if change == "missing":
        frame = frame.iloc[:-1]
    elif change == "duplicate":
        frame = pd.concat([frame, frame.iloc[[0]]])
    elif change == "wrong_estimand":
        frame.loc[0, "estimand"] = "ordinal_per_level"
    else:
        frame.loc[frame.status == "not_estimable", "estimate"] = 0
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError):
        _read_summary(tables)


def test_svg_is_deterministic_and_preserves_explicit_h3_limits(tables):
    outputs = render_robustness_figures(tables, tables / "figures")
    assert len(outputs) == 6
    first = {key: path.read_bytes() for key, path in outputs.items() if key.endswith("svg")}
    render_robustness_figures(tables, tables / "figures")
    assert all(outputs[key].read_bytes() == content for key, content in first.items())
    h3 = outputs["h3_svg"].read_text(encoding="utf-8")
    assert "не тест різниці" in h3
    assert "без висновку про медіацію" in h3
    assert all(line == line.rstrip() for line in h3.splitlines())
