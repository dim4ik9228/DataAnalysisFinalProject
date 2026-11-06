"""Render static descriptive figures from exported aggregate CSV tables only."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from parentedu.paths import FIGURES, TABLES

SUBJECTS = ("mat", "por")
SUBJECT_LABELS = {"mat": "Математика", "por": "Португальська мова"}
PARENTS = ("Medu", "Fedu")
PARENT_LABELS = {"Medu": "Освіта матері", "Fedu": "Освіта батька"}
EDUCATION_LABELS = ("1\nПочаткова", "2\n5–9 класи", "3\nСередня", "4\nВища")
CORRELATION_VARIABLES = (
    "Medu",
    "Fedu",
    "studytime",
    "age",
    "absences",
    "failures",
    "G1",
    "G2",
    "G3",
)
CORRELATION_LABELS = (
    "Освіта\nматері",
    "Освіта\nбатька",
    "Час\nнавчання",
    "Вік",
    "Пропуски",
    "Невдачі",
    "G1",
    "G2",
    "G3",
)
BLUE = "#28658A"
ORANGE = "#C67635"
INK = "#243848"
GRAY = "#73818B"


def _read(tables_dir: Path, name: str) -> pd.DataFrame:
    frame = pd.read_csv(tables_dir / f"eda_{name}.csv")
    if "layer" not in frame:
        raise ValueError(f"Missing layer in eda_{name}.csv")
    return frame.loc[frame["layer"].eq("replication")].copy()


def _counts(overview: pd.DataFrame) -> dict[str, int]:
    if overview["subject"].duplicated().any() or set(overview["subject"]) != set(SUBJECTS):
        raise ValueError("Replication overview must contain exactly mat and por")
    return {row.subject: int(row.n) for row in overview.itertuples()}


def _ordered(frame: pd.DataFrame, column: str, levels: list | range) -> pd.DataFrame:
    if frame[column].duplicated().any() or set(frame[column]) != set(levels):
        raise ValueError(f"Expected a complete unique grid for {column}")
    return frame.set_index(column).reindex(levels)


def _title(fig: Figure, text: str, subtitle: str | None = None) -> None:
    fig.suptitle(text, x=0.06, y=0.98, ha="left", fontsize=19, fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.06, 0.915, subtitle, ha="left", va="top", fontsize=10.5, color=GRAY)


def _footer(fig: Figure, counts: dict, aggregate: str, note: str = "") -> None:
    fig.text(
        0.06,
        0.035,
        "Джерело: UCI Student Performance · replication · "
        f"математика N={counts['mat']}; португальська N={counts['por']}\n"
        f"Агрегати: {aggregate}" + (f" · {note}" if note else ""),
        ha="left",
        va="bottom",
        fontsize=9,
        color=GRAY,
    )


def _clean_axis(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#E2E7EB", linewidth=0.7)
    ax.set_axisbelow(True)


def _distribution_figure(frame: pd.DataFrame, counts: dict) -> Figure:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.7), sharex=True, sharey=True)
    maximum = max(float(frame["count"].max()), 1)
    for ax, subject in zip(axes, SUBJECTS, strict=True):
        selected = _ordered(frame.loc[frame["subject"].eq(subject)], "grade", range(21))
        if int(selected["count"].sum()) != counts[subject]:
            raise ValueError(f"Grade frequencies do not sum to N for {subject}")
        ax.bar(range(21), selected["count"], color=[ORANGE] + [BLUE] * 20, width=0.82)
        ax.set(xlim=(-0.7, 20.7), ylim=(0, maximum * 1.15), xlabel="Підсумкова оцінка G3")
        ax.set_xticks(range(0, 21, 2))
        ax.set_title(f"{SUBJECT_LABELS[subject]} · N={counts[subject]}", fontsize=13, pad=14)
        ax.set_ylabel("Кількість записів")
        zero_n = int(selected.loc[0, "count"])
        ax.annotate(
            f"G3=0: {zero_n}",
            xy=(0, zero_n),
            xytext=(8, 9),
            textcoords="offset points",
            fontsize=10,
            color=ORANGE,
        )
        _clean_axis(ax)
    _title(
        fig,
        "Розподіл підсумкових оцінок",
        "Нульові оцінки виділено кольором і збережено у вибірці.",
    )
    _footer(fig, counts, "eda_grade_counts.csv")
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.18, top=0.81, wspace=0.18)
    return fig


def _frequencies_figure(frame: pd.DataFrame, counts: dict) -> Figure:
    education = frame.loc[frame["variable"].isin(PARENTS)].copy()
    # The CSV level column also contains nominal codes, so its inferred dtype is string.
    education["level"] = pd.to_numeric(education["level"], errors="raise")
    maximum = max(float(education["count"].max()), 1)
    fig, axes = plt.subplots(2, 2, figsize=(14, 9.4), sharey=True)
    for row, subject in enumerate(SUBJECTS):
        for col, parent in enumerate(PARENTS):
            ax = axes[row, col]
            selected = _ordered(
                education.loc[education["subject"].eq(subject) & education["variable"].eq(parent)],
                "level",
                range(1, 5),
            )
            if int(selected["count"].sum()) != counts[subject]:
                raise ValueError(f"Education frequencies do not sum to N for {subject}/{parent}")
            bars = ax.bar(range(1, 5), selected["count"], width=0.64, color=BLUE)
            ax.bar_label(
                bars,
                labels=[str(int(value)) for value in selected["count"]],
                padding=4,
                fontsize=10,
                color=INK,
            )
            ax.set(ylim=(0, maximum * 1.18), ylabel="Кількість записів")
            ax.set_xticks(range(1, 5), EDUCATION_LABELS)
            ax.set_title(
                f"{SUBJECT_LABELS[subject]} · {PARENT_LABELS[parent].lower()} · N={counts[subject]}",
                fontsize=12,
                pad=14,
            )
            _clean_axis(ax)
    _title(
        fig, "Склад вибірки за освітою батьків", "Частоти категорій, а не кількість років навчання."
    )
    _footer(fig, counts, "eda_category_counts.csv")
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.15, top=0.83, hspace=0.56, wspace=0.18)
    return fig


def _cross_figure(frame: pd.DataFrame, counts: dict) -> Figure:
    fig, axes = plt.subplots(1, 2, figsize=(14, 7.2))
    maximum = max(float(frame["count"].max()), 1)
    image = None
    for ax, subject in zip(axes, SUBJECTS, strict=True):
        selected = frame.loc[frame["subject"].eq(subject)]
        if selected.duplicated(["Medu", "Fedu"]).any() or len(selected) != 16:
            raise ValueError("Parent cross-tab must contain all 16 unique combinations")
        matrix = selected.pivot(index="Medu", columns="Fedu", values="count").reindex(
            index=range(1, 5), columns=range(1, 5)
        )
        if matrix.isna().any().any() or int(matrix.to_numpy().sum()) != counts[subject]:
            raise ValueError(f"Incomplete parent cross-tab for {subject}")
        image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=maximum, aspect="equal")
        for row in range(4):
            for col in range(4):
                value = int(matrix.iloc[row, col])
                ax.text(
                    col,
                    row,
                    str(value),
                    ha="center",
                    va="center",
                    fontsize=13,
                    color="white" if value > maximum * 0.55 else INK,
                )
        ax.set_xticks(range(4), EDUCATION_LABELS)
        ax.set_yticks(range(4), ["1 · Початкова", "2 · 5–9 класи", "3 · Середня", "4 · Вища"])
        ax.set(xlabel="Освіта батька (Fedu)", ylabel="Освіта матері (Medu)")
        ax.set_title(f"{SUBJECT_LABELS[subject]} · N={counts[subject]}", fontsize=13, pad=14)
    cax = fig.add_axes((0.94, 0.24, 0.014, 0.52))
    fig.colorbar(image, cax=cax, label="Кількість записів")
    _title(
        fig,
        "Поєднання освіти матері й батька",
        "У кожній клітинці — кількість записів; нульові клітинки показано явно.",
    )
    _footer(fig, counts, "eda_parent_cross.csv")
    fig.subplots_adjust(left=0.11, right=0.89, bottom=0.20, top=0.81, wspace=0.42)
    return fig


def _grade_figure(frame: pd.DataFrame, counts: dict) -> Figure:
    fig, axes = plt.subplots(2, 2, figsize=(14, 9.4), sharey=True)
    for row, subject in enumerate(SUBJECTS):
        for col, parent in enumerate(PARENTS):
            ax = axes[row, col]
            selected = _ordered(
                frame.loc[frame["subject"].eq(subject) & frame["parent"].eq(parent)],
                "education_level",
                range(1, 5),
            )
            if int(selected["n"].sum()) != counts[subject]:
                raise ValueError(f"Grade group sizes do not sum to N for {subject}/{parent}")
            for level, point in selected.iterrows():
                count = int(point["n"])
                ax.text(level, 19.25, f"n={count}", ha="center", fontsize=10, color=GRAY)
                if count == 0:
                    ax.text(level, 10, "немає\nданих", ha="center", color=GRAY, fontsize=9)
                    continue
                if not np.isfinite([point["q1"], point["median"], point["q3"]]).all():
                    raise ValueError("A nonempty grade group must have finite quartiles")
                if not 0 <= point["q1"] <= point["median"] <= point["q3"] <= 20:
                    raise ValueError("Invalid grade quartile order/range")
                ax.vlines(level, point["q1"], point["q3"], color=BLUE, linewidth=8, alpha=0.35)
                ax.hlines(
                    [point["q1"], point["q3"]],
                    level - 0.11,
                    level + 0.11,
                    color=BLUE,
                    linewidth=1.5,
                )
                ax.scatter(level, point["median"], s=45, color=BLUE, edgecolor="white", zorder=3)
            ax.set(xlim=(0.55, 4.45), ylim=(0, 20), ylabel="Підсумкова оцінка G3")
            ax.set_xticks(range(1, 5), EDUCATION_LABELS)
            ax.set_yticks(range(0, 21, 5))
            ax.set_title(
                f"{SUBJECT_LABELS[subject]} · {PARENT_LABELS[parent].lower()} · N={counts[subject]}",
                fontsize=12,
                pad=14,
            )
            _clean_axis(ax)
    _title(
        fig,
        "Оцінки за рівнем освіти батьків",
        "Точка — медіана; смуга — Q1–Q3 (IQR), розкид оцінок, не довірчий інтервал.",
    )
    _footer(fig, counts, "eda_grade_by_education.csv", "Не скориговано за іншими ознаками")
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.15, top=0.83, hspace=0.56, wspace=0.18)
    return fig


def _correlations_figure(frame: pd.DataFrame, counts: dict) -> Figure:
    fig, axes = plt.subplots(1, 2, figsize=(16, 8.6))
    cmap = matplotlib.colormaps["RdBu_r"].copy()
    cmap.set_bad("#D9DEE2")
    image = None
    for ax, subject in zip(axes, SUBJECTS, strict=True):
        selected = frame.loc[frame["subject"].eq(subject)]
        if selected.duplicated(["variable1", "variable2"]).any():
            raise ValueError("Duplicate correlation pairs")
        if set(selected["variable1"]) != set(CORRELATION_VARIABLES) or set(
            selected["variable2"]
        ) != set(CORRELATION_VARIABLES):
            raise ValueError("Unexpected correlation variables")
        matrix = selected.pivot(
            index="variable1", columns="variable2", values="coefficient"
        ).reindex(index=CORRELATION_VARIABLES, columns=CORRELATION_VARIABLES)
        if len(selected) != 81:
            raise ValueError(
                "Correlation matrix must contain all 81 pairs, including undefined ones"
            )
        image = ax.imshow(matrix, cmap=cmap, vmin=-1, vmax=1, aspect="equal")
        for row in range(9):
            for col in range(9):
                value = matrix.iloc[row, col]
                label = "—" if pd.isna(value) else f"{value:.2f}"
                ax.text(
                    col,
                    row,
                    label,
                    ha="center",
                    va="center",
                    fontsize=8.5,
                    color="white" if pd.notna(value) and abs(value) > 0.55 else INK,
                )
        ax.set_xticks(range(9), CORRELATION_LABELS, rotation=45, ha="right")
        ax.set_yticks(range(9), CORRELATION_LABELS)
        ax.tick_params(labelsize=10)
        ax.set_title(f"{SUBJECT_LABELS[subject]} · N={counts[subject]}", fontsize=13, pad=16)
    cax = fig.add_axes((0.945, 0.29, 0.012, 0.47))
    fig.colorbar(image, cax=cax, label="Spearman ρ")
    _title(
        fig,
        "Описові рангові зв'язки",
        "Spearman: без p-values; сірий колір і «—» означають невизначену кореляцію.",
    )
    _footer(fig, counts, "eda_correlations.csv", "Кореляція не доводить причинність")
    fig.subplots_adjust(left=0.10, right=0.90, bottom=0.25, top=0.82, wspace=0.42)
    return fig


def render_eda_figures(tables_dir: Path = TABLES, figures_dir: Path = FIGURES) -> dict[str, Path]:
    """Save five PNG/SVG pairs using only replication-layer aggregate CSV values."""
    tables_dir, figures_dir = Path(tables_dir), Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    counts = _counts(_read(tables_dir, "sample_overview"))
    specifications = (
        ("grade_distribution", "grade_counts", _distribution_figure),
        ("education_frequencies", "category_counts", _frequencies_figure),
        ("parent_cross", "parent_cross", _cross_figure),
        ("grade_by_education", "grade_by_education", _grade_figure),
        ("correlations", "correlations", _correlations_figure),
    )
    outputs = {}
    with matplotlib.rc_context(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.labelcolor": INK,
            "text.color": INK,
            "svg.hashsalt": "parentedu-eda-v1",
            "svg.fonttype": "none",
        }
    ):
        for stem, table, renderer in specifications:
            fig = renderer(_read(tables_dir, table), counts)
            try:
                for extension in ("png", "svg"):
                    destination = figures_dir / f"eda_{stem}.{extension}"
                    metadata = (
                        {"Date": None}
                        if extension == "svg"
                        else {"Software": "parentedu-replication"}
                    )
                    fig.savefig(
                        destination,
                        dpi=180,
                        bbox_inches="tight",
                        facecolor="white",
                        metadata=metadata,
                    )
                    if extension == "svg":
                        svg = destination.read_text(encoding="utf-8")
                        destination.write_text(
                            "\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
                            encoding="utf-8",
                            newline="\n",
                        )
                    outputs[f"{stem}_{extension}"] = destination
            finally:
                plt.close(fig)
    return outputs
