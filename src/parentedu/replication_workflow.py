"""P05 orchestration with content-based preflight and explicit run status."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from parentedu.eda_workflow import P03_INPUTS, digest, load_eda_inputs
from parentedu.environment import check_environment
from parentedu.paths import ROOT

P04_SOURCES = (
    "src/parentedu/eda.py",
    "src/parentedu/reporting.py",
    "src/parentedu/eda_workflow.py",
    "notebooks/02_eda.ipynb",
)
P05_SOURCES = (
    "src/parentedu/models.py",
    "src/parentedu/replication.py",
    "src/parentedu/replication_workflow.py",
    "src/parentedu/replication_reporting.py",
    "notebooks/03_replication.ipynb",
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _record(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def load_replication_inputs(root=ROOT):
    """Verify all P04 evidence and K1 before fitting; reuse P03 validation."""
    from parentedu.replication import validate_references

    root = Path(root)
    eda = json.loads((root / "outputs/logs/eda_run.json").read_text(encoding="utf-8"))
    _require(eda.get("status") == "ready", "P04 status is not ready; run notebook02.")
    _require(
        eda.get("p03_data_run_sha256") == digest(root / "outputs/logs/data_run.json"),
        "Stale P04 provenance: P03 metadata changed; run notebook02.",
    )
    for name in P04_SOURCES:
        _require(
            eda.get("source_hashes", {}).get(name) == digest(root / name),
            f"Stale P04 source: {name}; run notebook02.",
        )
    for name in P03_INPUTS:
        _require(
            eda.get("protocol_inputs", {}).get(name) == digest(root / name),
            f"Stale P04 protocol input: {name}.",
        )
    expected_inputs = {
        f"student_{subject}_{layer}.csv"
        for subject in ("mat", "por")
        for layer in ("validated", "replication")
    }
    recorded_inputs = eda.get("inputs", {})
    _require(
        {Path(n).name for n in recorded_inputs} == expected_inputs,
        "Incomplete P04 processed input hashes.",
    )
    for group in ("inputs", "outputs"):
        mapping = eda.get(group, {})
        _require(bool(mapping), f"Missing P04 {group} hashes.")
        if group == "outputs":
            _require(len(mapping) == 19, "Incomplete P04 output hashes.")
        for name, expected in mapping.items():
            path = (root / name).resolve()
            _require(path.is_relative_to(root.resolve()), "Invalid P04 evidence path.")
            _require(digest(path) == expected, f"Stale P04 {group}: {name}.")
    k1 = (root / "docs/K1_readiness.md").read_text(encoding="utf-8")
    _require("технічну контрольну точку пройдено" in k1, "K1 is not passed.")
    review = root / "docs/reviews/P04_eda_review.md"
    _require("PASS" in review.read_text(encoding="utf-8"), "P04 audit is not passed.")
    inputs = load_eda_inputs(root)
    references = validate_references(root / "data/reference", inputs["config"])
    return {**inputs, "references": references, "p04_metadata": eda}


def _build(frames, config):
    from parentedu.models import build_model_tables

    return build_model_tables(frames, config)


def _compare(coefficients, models, references, config):
    from parentedu.replication import compare_replication

    return compare_replication(coefficients, models, references, config)


def _render(rows, directory):
    from parentedu.replication_reporting import render_replication_figures

    return render_replication_figures(rows, directory)


def _markdown(frame):
    """Small Markdown export without an optional tabulate dependency."""

    def cell(value):
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value).replace("|", "\\|").replace("\n", " ")

    rows = [[cell(v) for v in row] for row in frame.itertuples(index=False, name=None)]
    return "\n".join(
        [
            "| " + " | ".join(map(str, frame.columns)) + " |",
            "| " + " | ".join(["---"] * len(frame.columns)) + " |",
            *["| " + " | ".join(row) + " |" for row in rows],
        ]
    )


def write_replication_findings(tables_dir, destination):
    """Generate claims from full precision exports, keeping verdict types separate."""
    tables_dir = Path(tables_dir)
    verdicts = pd.read_csv(tables_dir / "replication_verdicts.csv")
    tests = pd.read_csv(tables_dir / "replication_hypotheses.csv")
    comparison = pd.read_csv(tables_dir / "replication_comparison.csv")
    se = pd.read_csv(tables_dir / "replication_se_comparison.csv")
    diagnostics = pd.read_csv(tables_dir / "replication_diagnostics.csv")
    global_row = verdicts.loc[verdicts["model_id"].eq("global")].iloc[0]
    model_rows = verdicts.loc[~verdicts["model_id"].eq("global")]
    complete = int(model_rows["verdict"].eq("complete_match").sum())
    text = "# Результати реплікації таблиці 8 (P05)\n\n"
    text += f"Повністю збігаються {complete} із {len(model_rows)} моделей; {int(global_row['matched_cells'])} із {int(global_row['total_cells'])} числових перевірок пройдено. Глобальний вердикт: **{global_row['verdict']}**.\n\n"
    text += "Згенеровано з outputs/tables/replication_*.csv. Предмети аналізуються окремо; основний inference — HC3, use_t=false. Підготовлені N390/637 і нулі G3 збережено.\n\n"
    text += "## Числовий вердикт\n\n" + _markdown(verdicts) + "\n\n"
    text += "SE не входять до числового вердикту. Порівняно всі 68 estimate, 8 adjusted R² та 8 N. Допуски задано до оцінювання, без попереднього округлення власних чисел.\n\n"
    failures = comparison.loc[~comparison["matches"]]
    text += "### Журнал розбіжностей\n\n"
    text += (
        "Усі числові клітинки пройшли задані допуски.\n\n"
        if failures.empty
        else _markdown(failures) + "\n\n"
    )
    text += "При незбігу перевірено джерельні хеші, sample/рядки, reference-категорії, константу, набір термів і точність друку. Якщо відмінність лишається, її позначаємо невирішеною; це не автоматичний доказ помилки статті. Варіанти для підбору збігу не запускалися.\n\n"
    guardian = failures.loc[failures["model_id"].eq("M10") & failures["metric"].eq("estimate")]
    if set(guardian["term"]) == {"guardian_mother", "guardian_father"} and len(guardian) == 2:
        g = guardian.set_index("term")
        swapped_match = all(
            abs(float(g.loc[a, "replicated_value"]) - float(g.loc[b, "original_value"]))
            <= float(g.loc[b, "tolerance"])
            for a, b in (
                ("guardian_mother", "guardian_father"),
                ("guardian_father", "guardian_mother"),
            )
        )
        if swapped_match:
            text += "Дві розбіжності M10 мають структуру можливої перестановки підписів guardian_mother/guardian_father: кожна наша оцінка потрапляє в допуск числа, надрукованого в іншому рядку. Це діагностичне спостереження, а не встановлена причина: авторський код не надано. Еталони й кодування не виправляли; обидві клітинки залишаються mismatch, M10 — partial_match.\n\n"
    text += "## Авторський SE/inference\n\n"
    text += "Метод авторського covariance залишається **not_identified**. HC3, nonrobust та HC1 — наші заздалегідь обрані варіанти; навіть числовий збіг SE не встановлює авторський метод. Точні авторські p/CI не відновлюємо із зірочок або округлених клітинок.\n\n"
    text += (
        _markdown(se.groupby("covariance_type")["matches"].agg(["sum", "count"]).reset_index())
        + "\n\n"
    )
    text += "## H1/H2 — власні тести\n\n" + _markdown(tests) + "\n\n"
    text += "Holm виконано окремо для двох тестів H1 та двох H2. CI — звичайні 95% normal інтервали, не одночасні й не Holm-adjusted. H2 — прямий контраст із повною коваріацією; різниця значущості окремих коефіцієнтів не замінює його.\n\n"
    for family in ("H1", "H2"):
        group = tests.loc[tests["family"].eq(family)]
        both = group["verdict"].eq("expected_supported").all() and len(group) == 2
        text += (
            f"{family}: "
            + (
                "очікування підтримано в обох предметах"
                if both
                else "узагальненого підтвердження очікування для двох предметів немає"
            )
            + ".\n\n"
        )
        descriptions = {
            "expected_supported": "очікування підтримано",
            "opposite_evidence": "значущі свідчення проти очікування",
            "insufficient_evidence": "недостатньо доказів",
        }
        for row in group.itertuples():
            text += f"- {row.subject}: {descriptions[row.verdict]}; оцінка {row.estimate:.3f}, 95% CI [{row.ci_low:.3f}; {row.ci_high:.3f}], p_Holm={row.p_holm:.4f}.\n"
        text += "\n"
    text += "## Діагностика та межі\n\n" + _markdown(diagnostics) + "\n\n"
    text += "VIF наведено окремо в replication_vif.csv. Пороги VIF>5, Cook>4/N і leverage>2p/N — сигнали огляду; жоден рядок не видаляли й моделі після видалення не переоцінювали. Чотири фігури residuals-vs-fitted/Q–Q у PNG/SVG описують усі вісім моделей.\n\n"
    text += "Це умовні асоціації в тих самих даних, на яких побудовано статтю, без причинного висновку. Дві школи, самозвіти, невиміряні ресурси/здібності, кореляція освіти батьків і перетин учнів між предметами обмежують узагальнення. Inference умовний щодо специфікації, обраної оригінальною роботою.\n\n"
    text += "R1–R5, H3 зі studytime і плацебо залишаються для P06. Бібліографічна вимога про 3–5 citing/checking робіт лишається відкритою. Незалежний аудит: reviews/P05_replication_review.md; рішення K2: K2_replication.md.\n"
    Path(destination).write_text(text, encoding="utf-8")


def run_replication(root=ROOT):
    root = Path(root)
    marker = root / "outputs/logs/replication_run.json"
    record = {"status": "running", "created_at_utc": datetime.now(UTC).isoformat()}
    _record(marker, record)
    try:
        environment = check_environment()
        inputs = load_replication_inputs(root)
        config = inputs["config"]
        record.update(
            {
                "environment": environment,
                "git_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                "git_dirty": bool(
                    subprocess.check_output(
                        ["git", "status", "--porcelain"], cwd=root, text=True
                    ).strip()
                ),
                "source_hashes": {name: digest(root / name) for name in P05_SOURCES},
                "input_hashes": {
                    str(p.relative_to(root)): digest(p)
                    for p in [
                        root / "outputs/logs/data_run.json",
                        root / "outputs/logs/eda_run.json",
                        root / "docs/K1_readiness.md",
                        root / "docs/reviews/P04_eda_review.md",
                        *[root / name for name in P03_INPUTS],
                        *[p for p in sorted((root / "data/reference").rglob("*")) if p.is_file()],
                        *sorted((root / "data/processed").glob("student_*.csv")),
                    ]
                },
                "inference": config["inference"],
            }
        )
        built = _build(inputs["layers"]["replication"], config)
        compared = _compare(built["coefficients"], built["models"], inputs["references"], config)
        tables = {
            name: built[name]
            for name in ("coefficients", "models", "diagnostics", "vif", "hypotheses")
        }
        tables.update(compared)
        _require(len(tables) == 8, "Incomplete replication table set.")
        directory = root / "outputs/tables"
        directory.mkdir(parents=True, exist_ok=True)
        paths = {}
        for name, frame in tables.items():
            path = directory / f"replication_{name}.csv"
            frame.to_csv(path, index=False, lineterminator="\n", float_format="%.17g")
            paths[name] = path
        local = root / "data/processed/replication_diagnostics.csv"
        built["row_diagnostics"].to_csv(
            local, index=False, lineterminator="\n", float_format="%.17g"
        )
        figures = _render(built["row_diagnostics"], root / "outputs/figures")
        _require(len(figures) == 8, "Incomplete replication figure set.")
        findings = root / "docs/replication_findings.md"
        write_replication_findings(directory, findings)
        record.update(
            {
                "status": "ready",
                "completed_at_utc": datetime.now(UTC).isoformat(),
                "outputs": {
                    str(p.relative_to(root)): digest(p)
                    for p in [*paths.values(), *figures.values(), findings, local]
                },
                "counts": {s: len(f) for s, f in inputs["layers"]["replication"].items()},
            }
        )
        _record(marker, record)
        return {"tables": tables, "figures": figures, "metadata": record}
    except Exception as error:
        record.update({"status": "failed", "error_type": type(error).__name__, "error": str(error)})
        _record(marker, record)
        raise
