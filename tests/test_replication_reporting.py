"""Synthetic checks of plotted values, normal quantiles and export privacy."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from parentedu.replication_reporting import _diagnostic_figure, render_replication_figures


@pytest.fixture
def diagnostics():
    return pd.DataFrame(
        [
            {
                "subject": subject,
                "model_id": model,
                "record_id": f"private-student-{i}",
                "fitted": fitted,
                "residual": residual,
            }
            for subject, models in (
                ("mat", ("M1", "M2", "M3", "M4")),
                ("por", ("M7", "M8", "M9", "M10")),
            )
            for model in models
            for i, (fitted, residual) in enumerate(((3, 2), (5, -3), (9, 1)))
        ]
    ).sample(frac=1, random_state=4)


def test_panels_preserve_pairs_and_use_comparable_scales(diagnostics):
    fig = _diagnostic_figure(diagnostics, "mat", "residual_fitted")
    try:
        assert len(fig.axes) == 4
        for ax in fig.axes:
            assert set(map(tuple, ax.collections[0].get_offsets())) == {(3, 2), (5, -3), (9, 1)}
            assert ax.get_xlim() == fig.axes[0].get_xlim()
            assert ax.get_ylim() == fig.axes[0].get_ylim()
            assert ax.get_ylim()[0] < -3 < 2 < ax.get_ylim()[1]
    finally:
        plt.close(fig)


def test_qq_uses_ordered_residuals_and_standard_normal_quantiles(diagnostics):
    fig = _diagnostic_figure(diagnostics, "por", "qq")
    try:
        points = fig.axes[0].collections[0].get_offsets()
        np.testing.assert_allclose(points[:, 0], [-0.9674215661, 0, 0.9674215661])
        np.testing.assert_allclose(points[:, 1], [-3, 1, 2])
        assert len(fig.axes[0].lines) == 0
    finally:
        plt.close(fig)


def test_exports_are_reproducible_and_do_not_expose_identifiers(diagnostics, tmp_path):
    first = render_replication_figures(diagnostics, tmp_path / "first")
    second = render_replication_figures(diagnostics.iloc[::-1], tmp_path / "second")
    assert len(first) == 8
    for key, path in first.items():
        assert path.read_bytes() == second[key].read_bytes()
        if path.suffix == ".svg":
            svg = path.read_text(encoding="utf-8")
            assert "private-student" not in svg
            assert "Модель" in svg and "Джерело" in svg
            assert "<dc:date>" not in svg
            assert all(line == line.rstrip() for line in svg.splitlines())


@pytest.mark.parametrize(
    "problem", ["missing_model", "duplicate", "nonfinite", "different_records"]
)
def test_invalid_input_fails_before_creating_outputs(diagnostics, tmp_path, problem):
    frame = diagnostics.copy()
    if problem == "missing_model":
        frame = frame.loc[frame.model_id.ne("M1")]
    elif problem == "duplicate":
        frame = pd.concat([frame, frame.iloc[[0]]])
    elif problem == "nonfinite":
        frame["residual"] = frame["residual"].astype(float)
        frame.loc[frame.index[0], "residual"] = np.inf
    else:
        frame.loc[frame.index[0], "record_id"] = "unexpected-record"
    destination = tmp_path / "figures"
    with pytest.raises(ValueError):
        render_replication_figures(frame, destination)
    assert not destination.exists()
