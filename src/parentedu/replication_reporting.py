"""Render descriptive OLS diagnostic panels from local derived row diagnostics."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

MODELS = {"mat": ("M1", "M2", "M3", "M4"), "por": ("M7", "M8", "M9", "M10")}
LABELS = {"mat": "Математика", "por": "Португальська мова"}
BLUE, INK, GRAY = "#28658A", "#243848", "#73818B"


def _validate(frame: pd.DataFrame) -> None:
    required = {"subject", "model_id", "record_id", "fitted", "residual"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Missing diagnostic columns: {sorted(required - set(frame.columns))}")
    expected = {(subject, model) for subject, models in MODELS.items() for model in models}
    if set(frame[["subject", "model_id"]].itertuples(index=False, name=None)) != expected:
        raise ValueError("Diagnostics must contain exactly the eight replication models")
    if frame[list(required)].isna().any().any():
        raise ValueError("Diagnostic values and keys must not be missing")
    if frame.duplicated(["subject", "model_id", "record_id"]).any():
        raise ValueError("Duplicate diagnostic record within a model")
    if not np.isfinite(frame[["fitted", "residual"]].to_numpy(dtype=float)).all():
        raise ValueError("Fitted values and residuals must be finite")
    for subject, models in MODELS.items():
        groups = [frame.loc[frame.subject.eq(subject) & frame.model_id.eq(m)] for m in models]
        records = set(groups[0].record_id)
        if len(records) < 2 or any(set(group.record_id) != records for group in groups):
            raise ValueError("Models within a subject must use the same records (N >= 2)")


def _limits(values: np.ndarray) -> tuple[float, float]:
    low, high = float(values.min()), float(values.max())
    padding = max((high - low) * 0.07, 0.25)
    return low - padding, high + padding


def _diagnostic_figure(frame: pd.DataFrame, subject: str, kind: str):
    selected = frame.loc[frame.subject.eq(subject)]
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), sharex=True, sharey=True)
    residual_limit = max(float(selected.residual.abs().max()) * 1.08, 0.5)
    fitted_limits = _limits(selected.fitted.to_numpy())
    n = len(selected) // 4
    quantiles = norm.ppf((np.arange(n) + 0.5) / n)
    for ax, model in zip(axes.flat, MODELS[subject], strict=True):
        group = selected.loc[selected.model_id.eq(model)].sort_values("record_id")
        if kind == "residual_fitted":
            x, y = group.fitted.to_numpy(), group.residual.to_numpy()
            ax.axhline(0, color=GRAY, linewidth=1, linestyle="--")
            ax.set(xlabel="Прогнозоване значення", xlim=fitted_limits, ylabel="Залишок")
        else:
            x, y = quantiles, np.sort(group.residual.to_numpy())
            ax.set(xlabel="Теоретичні квантилі N(0, 1)", ylabel="Квантилі залишків")
            ax.set_xlim(_limits(quantiles))
        ax.scatter(x, y, color=BLUE, s=15, alpha=0.45, edgecolors="none")
        ax.set_ylim(-residual_limit, residual_limit)
        ax.set_title(f"Модель {model} · N={n}", fontsize=12, pad=10)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(color="#E2E7EB", linewidth=0.7)
        ax.set_axisbelow(True)
        ax.tick_params(labelbottom=True, labelleft=True)
    title = "Залишки та прогнозовані значення" if kind == "residual_fitted" else "Q–Q залишків"
    fig.suptitle(
        f"{LABELS[subject]} · {title}",
        x=0.08,
        y=0.98,
        ha="left",
        fontsize=16,
        fontweight="bold",
        color=INK,
    )
    subtitle = (
        "Пунктир — нульовий залишок; однакові шкали для чотирьох моделей."
        if kind == "residual_fitted"
        else "Описове зіставлення з нормальною формою; залишки не стандартизовано."
    )
    fig.text(0.08, 0.925, subtitle, fontsize=10, color=GRAY)
    fig.text(
        0.08,
        0.025,
        f"Джерело: UCI Student Performance · вибірка реплікації · N={n}\n"
        "Власні OLS-розрахунки; точки — похідні діагностичні значення без ідентифікаторів.",
        fontsize=9,
        color=GRAY,
    )
    fig.subplots_adjust(left=0.09, right=0.97, bottom=0.13, top=0.86, hspace=0.38, wspace=0.25)
    return fig


def render_replication_figures(row_diagnostics: pd.DataFrame, figures_dir: Path) -> dict[str, Path]:
    """Save four PNG/SVG figure pairs without fitting models or exposing record IDs."""
    _validate(row_diagnostics)
    figures_dir = Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    with matplotlib.rc_context(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.labelcolor": INK,
            "text.color": INK,
            "svg.hashsalt": "parentedu-replication-v1",
            "svg.fonttype": "none",
        }
    ):
        for subject in MODELS:
            for kind in ("residual_fitted", "qq"):
                fig = _diagnostic_figure(row_diagnostics, subject, kind)
                try:
                    for extension in ("png", "svg"):
                        path = figures_dir / f"replication_{subject}_{kind}.{extension}"
                        metadata = (
                            {"Date": None}
                            if extension == "svg"
                            else {"Software": "parentedu-replication"}
                        )
                        fig.savefig(path, dpi=180, facecolor="white", metadata=metadata)
                        if extension == "svg":
                            svg = path.read_text(encoding="utf-8")
                            path.write_text(
                                "\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
                                encoding="utf-8",
                                newline="\n",
                            )
                        outputs[f"{subject}_{kind}_{extension}"] = path
                finally:
                    plt.close(fig)
    return outputs
