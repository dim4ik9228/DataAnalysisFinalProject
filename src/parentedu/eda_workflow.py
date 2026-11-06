"""P04 input integrity, descriptive exports and reproducible run metadata."""

import hashlib
import json
import platform
import subprocess
import tomllib
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from parentedu.data import load_schema
from parentedu.eda import build_eda_tables
from parentedu.paths import ROOT
from parentedu.preparation import read_prepared_csv

P03_INPUTS = (
    "configs/data_schema.toml",
    "configs/analysis.toml",
    "docs/replication_protocol.md",
    "uv.lock",
)
P03_SOURCES = (
    "src/parentedu/data.py",
    "src/parentedu/preparation.py",
    "src/parentedu/data_workflow.py",
    "notebooks/01_data.ipynb",
)
TABLE_NAMES = (
    "sample_overview",
    "numeric_summary",
    "category_counts",
    "grade_counts",
    "parent_cross",
    "grade_by_education",
    "correlations",
    "group_screen",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message + " Re-run notebook 01 or investigate the discrepancy.")


def load_eda_inputs(root: Path = ROOT) -> dict:
    """Check relevant P03 content hashes, not equality to the current Git HEAD."""
    root = Path(root)
    metadata = json.loads((root / "outputs/logs/data_run.json").read_text(encoding="utf-8"))
    _require(metadata.get("status") == "prepared", "P03 data status is not prepared.")
    for name in P03_INPUTS:
        _require(
            metadata.get("inputs", {}).get(name) == digest(root / name), f"Stale P03 input: {name}."
        )
    for name in P03_SOURCES:
        _require(
            metadata.get("source_hashes", {}).get(name) == digest(root / name),
            f"Stale P03 code: {name}.",
        )
    _require(
        metadata.get("provenance_sha256") == digest(root / "docs/data_provenance.json"),
        "Changed pinned provenance.",
    )
    with (root / "configs/analysis.toml").open("rb") as handle:
        config = tomllib.load(handle)
    schema = load_schema(root / "configs/data_schema.toml")
    layers = {"validated": {}, "replication": {}}
    for layer in layers:
        for subject in ("mat", "por"):
            name = f"student_{subject}_{layer}.csv"
            recorded = [
                value
                for key, value in metadata.get("outputs", {}).items()
                if Path(key).name == name
            ]
            path = root / "data/processed" / name
            _require(
                len(recorded) == 1 and recorded[0] == digest(path),
                f"Changed processed input: {name}.",
            )
    for layer, subjects in layers.items():
        for subject in ("mat", "por"):
            name = f"student_{subject}_{layer}.csv"
            path = root / "data/processed" / name
            frame = read_prepared_csv(path, schema=schema)
            expected = (
                schema["dataset"]["expected_rows"][subject]
                if layer == "validated"
                else config["expected_sample"][subject]
            )
            _require(len(frame) == expected, f"Unexpected row count: {name}.")
            _require(frame["subject"].eq(subject).all(), f"Mixed subject: {name}.")
            subjects[subject] = frame
    for subject in ("mat", "por"):
        full = layers["validated"][subject]
        expected = full.loc[full.Medu.ge(1) & full.Fedu.ge(1)].reset_index(drop=True)
        pd.testing.assert_frame_equal(
            expected, layers["replication"][subject].reset_index(drop=True)
        )
    return {"layers": layers, "schema": schema, "config": config, "p03_metadata": metadata}


def _render(tables_dir: Path, figures_dir: Path) -> dict:
    from parentedu.reporting import render_eda_figures

    return render_eda_figures(tables_dir=tables_dir, figures_dir=figures_dir)


def write_eda_findings(tables_dir: Path, destination: Path) -> None:
    """Generate descriptive statements from exported CSV, without hypothesis verdicts."""
    tables = {name: pd.read_csv(tables_dir / f"eda_{name}.csv") for name in TABLE_NAMES}
    overview = tables["sample_overview"]
    correlations = tables["correlations"]
    grades = tables["grade_by_education"]
    cross = tables["parent_cross"]
    screen = tables["group_screen"]
    summary, rank_rows, grade_rows, cross_rows = [], [], [], []
    for subject in ("mat", "por"):
        view = overview.loc[(overview.subject == subject) & (overview.layer == "replication")].iloc[
            0
        ]
        summary.append(f"| {subject} | {int(view['n'])} | {int(view['zero_g3'])} |")
        for first, second in (("Medu", "Fedu"), ("Medu", "G3"), ("Fedu", "G3")):
            row = correlations.loc[
                (correlations.subject == subject)
                & (correlations.variable1 == first)
                & (correlations.variable2 == second)
            ].iloc[0]
            rank_rows.append(
                f"| {subject} | {first}–{second} | {row['coefficient']:.3f} | {int(row['pair_n'])} |"
            )
        for parent in ("Medu", "Fedu"):
            for level in (1, 4):
                row = grades.loc[
                    (grades.subject == subject)
                    & (grades.parent == parent)
                    & (grades.education_level == level)
                ].iloc[0]
                grade_rows.append(
                    f"| {subject} | {parent} | {level} | {int(row['n'])} | {row['median']:g} | {row['q1']:g}–{row['q3']:g} |"
                )
        cells = cross.loc[(cross.subject == subject) & (cross.layer == "replication")]
        cross_rows.append(
            f"| {subject} | {int((cells['count'] > 0).sum())} | {len(cells)} | {int(cells['count'].min())} |"
        )
    failed = screen.loc[~screen["counts_screen_pass"].astype(bool)]
    failed_rows = [
        f"| {r.subject} | {r.school} | {r.parent} | {int(r.n)} | {int(r.reference_n)} | {int(r.target_n)} |"
        for r in failed.itertuples()
    ]
    text = (
        """# Описові висновки EDA (P04)

Цей файл згенеровано з outputs/tables/eda_*.csv. Усі змістові описи нижче стосуються replication, предмети аналізуються окремо. H1–H3 тут не перевірялися.

## Вибірки та нульові оцінки

| Предмет | N | G3=0 |
|---|---:|---:|
"""
        + "\n".join(summary)
        + """

Дані P03 не змінено; нулі збережено. Це не кількість унікальних людей у двох предметах разом.

## Освіта батьків і рангові зв'язки

| Предмет | Пара | Spearman | pair N |
|---|---|---:|---:|
"""
        + "\n".join(rank_rows)
        + """

Джерело: eda_correlations.csv. Освіта матері й батька пов'язана між собою; тому окремі графіки не розділяють їхні умовні зв'язки з оцінками. Числа описові, без p-values. Вони не є коефіцієнтами майбутньої регресії та не доводять причинності або різниці між батьками.

## Розподіл оцінок у крайніх категоріях освіти

| Предмет | Змінна | Рівень освіти | N | Median G3 | Q1–Q3 |
|---|---|---:|---:|---:|---|
"""
        + "\n".join(grade_rows)
        + """

Джерело: eda_grade_by_education.csv; рівень1 — початкова освіта,4 — вища. У повній таблиці й графіку збережено також рівні2/3. IQR описує розкид, не невизначеність середнього. Відмінності груп не є оцінкою контролювання age/sex/school/guardian.

## Поєднання Medu×Fedu

| Предмет | Непорожні комбінації | Усі комбінації | Найменший count |
|---|---:|---:|---:|
"""
        + "\n".join(cross_rows)
        + """

Джерело: eda_parent_cross.csv. Повна сітка збережена; нульова частота не приховується, якщо вона є. Наявність усіх комбінацій сама по собі не доводить добру точність майбутніх оцінок.

## Обмеження шкільних підгруп

Наступні підгрупи не проходять наперед заданий count-screen:

| Предмет | Школа | Батько/мати | N | Reference count | Target count |
|---|---|---|---:|---:|---:|
"""
        + ("\n".join(failed_rows) if failed_rows else "| — | — | — | — | — | — |")
        + """

Джерело: eda_group_screen.csv. Пороги беруться з analysis.toml; fail не видаляє дані. Pass теж не означає оцінюваність: ранг, залишкові df та leverage ще не перевірялися. Малі групи не об'єднували, базові категорії не змінювали.

## Межі інтерпретації та передача

G1/G2 показані лише для опису структури оцінок і не додані до точної моделі. Номінальні sex/school/guardian та технічні ID відсутні в Spearman-матриці. Failures лишається з описаною неоднозначністю джерела без перекодування.

Дві школи, самозвіти, невиміряні сімейні ресурси, здібності та можливий перетин учнів між предметами обмежують узагальнення. Регресії, тести гіпотез, VIF, залишки та причинні механізми не оцінювалися. Потреби змінювати протокол за EDA не заявляємо.

П'ять фігур у outputs/figures/eda_* відтворюють відповідні CSV. Незалежний аудит і візуальна перевірка описані у reviews/P04_eda_review.md. Рішення про перехід до P05 — у K1_readiness.md; відкрита бібліографічна вимога P02 й невідомий авторський SE залишаються явними.
"""
    )
    destination.write_text(text, encoding="utf-8")


def run_eda(root: Path = ROOT) -> dict:
    """Produce all P04 artifacts only from current, hash-verified P03 inputs."""
    root = Path(root)
    metadata_path = root / "outputs/logs/eda_run.json"
    tables_dir, figures_dir = root / "outputs/tables", root / "outputs/figures"
    record = {"status": "running", "created_at_utc": datetime.now(UTC).isoformat()}
    _json(metadata_path, record)
    try:
        inputs = load_eda_inputs(root)
        git = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        record.update(
            {
                "git_commit": git.stdout.strip() if git.returncode == 0 else None,
                "git_dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
                "python": platform.python_version(),
                "versions": {
                    name: version(name) for name in ("pandas", "numpy", "matplotlib", "seaborn")
                },
                "p03_data_run_sha256": digest(root / "outputs/logs/data_run.json"),
                "inputs": {
                    str(path.relative_to(root)): digest(path)
                    for path in (root / "data/processed").glob("student_*.csv")
                },
                "protocol_inputs": {name: digest(root / name) for name in P03_INPUTS},
                "source_hashes": {
                    name: digest(root / name)
                    for name in (
                        "src/parentedu/eda.py",
                        "src/parentedu/reporting.py",
                        "src/parentedu/eda_workflow.py",
                        "notebooks/02_eda.ipynb",
                    )
                },
            }
        )
        tables = build_eda_tables(
            inputs["layers"], schema=inputs["schema"], config=inputs["config"]
        )
        _require(set(tables) == set(TABLE_NAMES), "Incomplete EDA table set.")
        tables_dir.mkdir(parents=True, exist_ok=True)
        csv_paths = {}
        for name in TABLE_NAMES:
            path = tables_dir / f"eda_{name}.csv"
            tables[name].to_csv(path, index=False, lineterminator="\n", float_format="%.12g")
            csv_paths[name] = path
        figures = _render(tables_dir, figures_dir)
        _require(len(figures) == 10, "Incomplete PNG/SVG figure set.")
        findings_path = root / "docs/eda_findings.md"
        write_eda_findings(tables_dir, findings_path)
        all_outputs = [*csv_paths.values(), *figures.values(), findings_path]
        record.update(
            {
                "status": "ready",
                "completed_at_utc": datetime.now(UTC).isoformat(),
                "outputs": {str(path.relative_to(root)): digest(path) for path in all_outputs},
                "counts": {s: len(inputs["layers"]["replication"][s]) for s in ("mat", "por")},
            }
        )
        _json(metadata_path, record)
        return {"tables": tables, "csv_paths": csv_paths, "figures": figures, "metadata": record}
    except Exception as error:
        record.update({"status": "failed", "error_type": type(error).__name__, "error": str(error)})
        _json(metadata_path, record)
        raise
