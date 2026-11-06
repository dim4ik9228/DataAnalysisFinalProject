"""Static P06 figures rendered solely from exported aggregate tables."""

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SUBJECTS = {"mat": "Математика", "por": "Португальська мова"}
PARENTS = {"Medu": "Освіта матері", "Fedu": "Освіта батька"}
SPECS = (
    ("baseline", ""),
    ("R1", ""),
    ("R2", ""),
    ("R3", ""),
    ("R4", "GP"),
    ("R4", "MS"),
    ("R5", ""),
)
NUMERIC = ("estimate", "std_error", "ci_low", "ci_high", "p_value")
BLUE, ORANGE, GRAY = "#28658A", "#C67635", "#73818B"


def _read_summary(tables_dir: Path) -> pd.DataFrame:
    frame = pd.read_csv(tables_dir / "robustness_summary.csv", keep_default_na=False)
    required = {
        "subject",
        "base_model_id",
        "variant",
        "school",
        "parent",
        "term",
        "estimand",
        "nobs",
        "status",
        "reason",
        *NUMERIC,
    }
    if not required.issubset(frame):
        raise ValueError(f"Missing summary columns: {sorted(required - set(frame))}")
    keys = ["subject", "variant", "school", "parent"]
    expected = {(s, v, school, p) for s in SUBJECTS for v, school in SPECS for p in PARENTS}
    if (
        frame.duplicated(keys).any()
        or set(frame[keys].itertuples(index=False, name=None)) != expected
    ):
        raise ValueError("Summary must contain the complete unique 28-row robustness grid")
    for column in (*NUMERIC, "nobs"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for row in frame.itertuples():
        ordinal = row.variant == "R3"
        if (
            row.base_model_id != {"mat": "M4", "por": "M10"}[row.subject]
            or row.estimand != ("ordinal_per_level" if ordinal else "categorical_4_vs_1")
            or row.term != f"{row.parent}_{'ordinal' if ordinal else '4'}"
        ):
            raise ValueError("Summary model, term or estimand disagrees with variant")
        if not np.isfinite(row.nobs) or row.nobs < 0 or row.nobs != int(row.nobs):
            raise ValueError("Summary N must be a nonnegative integer")
        values = np.array([getattr(row, c) for c in NUMERIC])
        if row.status == "available":
            if (
                not np.isfinite(values).all()
                or row.std_error < 0
                or not row.ci_low <= row.estimate <= row.ci_high
                or not 0 <= row.p_value <= 1
            ):
                raise ValueError("Estimated rows require finite, ordered estimates and CI")
        elif row.status == "not_estimable":
            if not str(row.reason).strip() or not np.isnan(values).all():
                raise ValueError("Not-estimable rows need a reason and missing numeric estimates")
        else:
            raise ValueError("Unknown estimation status")
    return frame


def _point(ax, row, y, color=BLUE):
    if row.status == "available":
        ax.errorbar(
            row.estimate,
            y,
            xerr=[[row.estimate - row.ci_low], [row.ci_high - row.estimate]],
            fmt="o",
            color=color,
            capsize=3,
            markersize=5,
        )


def _style(ax, xlabel):
    ax.axvline(0, color=GRAY, linewidth=1, linestyle="--")
    ax.set_xlabel(xlabel)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", color="#E2E7EB", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)


def _categorical_figure(frame):
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    specs = [spec for spec in SPECS if spec[0] != "R3"]
    for i, (subject, label) in enumerate(SUBJECTS.items()):
        for j, (parent, parent_label) in enumerate(PARENTS.items()):
            ax = axes[i, j]
            labels = []
            for y, (variant, school) in enumerate(specs):
                row = frame.loc[
                    (frame.subject == subject)
                    & (frame.parent == parent)
                    & (frame.variant == variant)
                    & (frame.school == school)
                ].iloc[0]
                _point(ax, row, y)
                name = "База" if variant == "baseline" else variant
                name += f" · {school}" if school else ""
                line = f"{name} · N={int(row.nobs)}"
                if row.status != "available":
                    line += "\nНе оцінено: " + textwrap.fill(str(row.reason), 29)
                labels.append(line)
            ax.set_yticks(range(len(specs)), labels, fontsize=9)
            ax.set_ylim(len(specs) - 0.45, -0.65)
            ax.set_title(f"{label} · {parent_label}", fontsize=12, pad=14)
            _style(ax, "Різниця G3: вища vs початкова освіта, бали")
    fig.suptitle("Стійкість категоріальних контрастів освіти батьків", fontsize=17, y=0.98)
    fig.text(
        0.03,
        0.025,
        "Точки — оцінки OLS; відрізки — 95% CI HC3, не одночасні. R4 — окремі школи.\n"
        "Варіанти змінюють одну умову базової моделі; зв’язки не є причинними.",
        fontsize=10,
    )
    fig.subplots_adjust(left=0.20, right=0.98, bottom=0.13, top=0.90, wspace=0.75, hspace=0.40)
    return fig


def _ordinal_figure(frame):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    for ax, (subject, label) in zip(axes, SUBJECTS.items(), strict=True):
        labels = []
        for y, (parent, parent_label) in enumerate(PARENTS.items()):
            row = frame.loc[
                (frame.subject == subject) & (frame.parent == parent) & (frame.variant == "R3")
            ].iloc[0]
            _point(ax, row, y, (BLUE, ORANGE)[y])
            labels.append(f"{parent_label}\nN={int(row.nobs)}")
        ax.set_yticks([0, 1], labels)
        ax.set_ylim(1.6, -0.6)
        ax.set_title(label)
        _style(ax, "Зміна G3 на один рівень освіти, бали")
    fig.suptitle("R3 · порядкова освіта батьків", fontsize=17)
    fig.text(
        0.04,
        0.04,
        "Інший estimand: нахил на один рівень, а не контраст 4 vs 1.\n"
        "OLS; 95% CI HC3 не одночасні; рівні 1–4 припускають однаковий крок.",
        fontsize=10,
    )
    fig.subplots_adjust(left=0.16, right=0.98, top=0.80, bottom=0.24, wspace=0.65)
    return fig


def _h3_figure(frame, tables_dir):
    h3 = pd.read_csv(tables_dir / "robustness_h3.csv")
    required = {
        "subject",
        "base_model_id",
        "beta_base",
        "beta_augmented",
        "delta_abs",
        "sign_change",
        "nobs",
    }
    if not required.issubset(h3) or len(h3) != 2 or set(h3.subject) != set(SUBJECTS):
        raise ValueError("H3 must contain one row per subject and its descriptive comparison")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    for ax, (subject, label) in zip(axes, SUBJECTS.items(), strict=True):
        h = h3.loc[h3.subject == subject].iloc[0]
        rows = [
            frame.loc[
                (frame.subject == subject) & (frame.parent == "Medu") & (frame.variant == v)
            ].iloc[0]
            for v in ("baseline", "R5")
        ]
        if h.base_model_id != rows[0].base_model_id or not np.allclose(
            [h.beta_base, h.beta_augmented, h.nobs, h.delta_abs],
            [
                rows[0].estimate,
                rows[1].estimate,
                rows[1].nobs,
                abs(rows[1].estimate) - abs(rows[0].estimate),
            ],
        ):
            raise ValueError("H3 estimates disagree with exported summary")
        for y, row in enumerate(rows):
            _point(ax, row, y, (BLUE, ORANGE)[y])
        ax.set_yticks([0, 1], [f"База · N={int(rows[0].nobs)}", f"R5 · N={int(rows[1].nobs)}"])
        ax.set_ylim(1.6, -0.6)
        ax.set_title(f"{label}\nΔ|β| = {h.delta_abs:+.3f}")
        _style(ax, "Medu_4: вища vs початкова освіта, бали G3")
    fig.suptitle("H3 · освіта матері до та після додавання studytime", fontsize=16)
    fig.text(
        0.04,
        0.035,
        "95% CI окремих оцінок HC3, не одночасні; це не тест різниці між моделями.\n"
        "Δ|β| = |β(R5)| − |β(база)|; без p-value для зміни та без висновку про медіацію.",
        fontsize=10,
    )
    fig.subplots_adjust(left=0.15, right=0.98, top=0.77, bottom=0.24, wspace=0.60)
    return fig


def render_robustness_figures(tables_dir: Path, figures_dir: Path) -> dict[str, Path]:
    """Read P06 CSVs and save three deterministic PNG/SVG figure pairs; never fit models."""
    tables_dir, figures_dir = Path(tables_dir), Path(figures_dir)
    frame = _read_summary(tables_dir)
    outputs = {}
    figures_dir.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(
        {
            "font.family": "DejaVu Sans",
            "svg.fonttype": "none",
            "svg.hashsalt": "parentedu-robustness-v1",
            "font.size": 10,
        }
    ):
        for kind, factory in (
            ("categorical", lambda: _categorical_figure(frame)),
            ("ordinal", lambda: _ordinal_figure(frame)),
            ("h3", lambda: _h3_figure(frame, tables_dir)),
        ):
            fig = factory()
            try:
                for extension in ("png", "svg"):
                    path = figures_dir / f"robustness_{kind}.{extension}"
                    metadata = {"Date": None} if extension == "svg" else {"Software": "parentedu"}
                    fig.savefig(path, dpi=180, facecolor="white", metadata=metadata)
                    if extension == "svg":
                        svg = path.read_text(encoding="utf-8")
                        path.write_text(
                            "\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
                            encoding="utf-8",
                            newline="\n",
                        )
                    outputs[f"{kind}_{extension}"] = path
            finally:
                plt.close(fig)
    return outputs
