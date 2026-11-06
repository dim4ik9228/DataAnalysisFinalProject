"""P06 provenance checks, baseline validation and reproducible exports."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from parentedu.eda_workflow import digest
from parentedu.environment import check_environment
from parentedu.paths import ROOT
from parentedu.replication_workflow import (
    P03_INPUTS,
    P05_SOURCES,
    _markdown,
    load_replication_inputs,
)

SOURCES = (
    "src/parentedu/robustness.py",
    "src/parentedu/robustness_baseline.py",
    "src/parentedu/robustness_workflow.py",
    "src/parentedu/robustness_reporting.py",
    "notebooks/04_robustness.ipynb",
)
TABLES = (
    "baseline_check",
    "specifications",
    "coefficients",
    "summary",
    "diagnostics",
    "vif",
    "h3",
    "placebo",
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _record(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _p05_expected_paths(root):
    inputs = {
        "outputs/logs/data_run.json",
        "outputs/logs/eda_run.json",
        "docs/K1_readiness.md",
        "docs/reviews/P04_eda_review.md",
        *P03_INPUTS,
        *[
            p.relative_to(root).as_posix()
            for p in (root / "data/reference").rglob("*")
            if p.is_file()
        ],
        *[
            f"data/processed/student_{subject}_{layer}.csv"
            for subject in ("mat", "por")
            for layer in ("validated", "replication")
        ],
    }
    outputs = {
        *[
            f"outputs/tables/replication_{name}.csv"
            for name in (
                "coefficients",
                "models",
                "comparison",
                "se_comparison",
                "verdicts",
                "hypotheses",
                "diagnostics",
                "vif",
            )
        ],
        *[
            f"outputs/figures/replication_{subject}_{kind}.{ext}"
            for subject in ("mat", "por")
            for kind in ("residual_fitted", "qq")
            for ext in ("png", "svg")
        ],
        "docs/replication_findings.md",
        "data/processed/replication_diagnostics.csv",
    }
    return {"source_hashes": set(P05_SOURCES), "input_hashes": inputs, "outputs": outputs}


def load_robustness_inputs(root=ROOT):
    root = Path(root)
    p05 = json.loads((root / "outputs/logs/replication_run.json").read_text(encoding="utf-8"))
    _require(p05.get("status") == "ready", "P05 is not ready; run notebook03.")
    for group, expected_paths in _p05_expected_paths(root).items():
        hashes = p05.get(group, {})
        normalized = {Path(name).as_posix(): value for name, value in hashes.items()}
        _require(set(normalized) == expected_paths, f"Incomplete P05 {group} hashes.")
        for name, expected in hashes.items():
            path = (root / name).resolve()
            _require(path.is_relative_to(root.resolve()), "Invalid P05 evidence path.")
            _require(digest(path) == expected, f"Stale P05 {group}: {name}.")
    _require(
        "P05 виконано" in (root / "docs/K2_replication.md").read_text(encoding="utf-8"),
        "K2 not passed.",
    )
    _require(
        "PASS" in (root / "docs/reviews/P05_replication_review.md").read_text(encoding="utf-8"),
        "P05 audit not passed.",
    )
    inputs = load_replication_inputs(root)
    return {**inputs, "p05_metadata": p05}


def _baseline(frames, config, table_dir):
    from parentedu.robustness_baseline import check_baseline

    return check_baseline(frames, config, table_dir)


def _build(layers, config):
    from parentedu.robustness import build_robustness_tables

    return build_robustness_tables(layers, config)


def _render(tables_dir, figures_dir):
    from parentedu.robustness_reporting import render_robustness_figures

    return render_robustness_figures(tables_dir, figures_dir)


def _table(frame):
    return _markdown(frame.astype(object).where(frame.notna(), "—"))


def write_robustness_findings(tables_dir, destination):
    tables_dir = Path(tables_dir)
    tables = {
        name: pd.read_csv(tables_dir / f"robustness_{name}.csv", keep_default_na=True)
        for name in TABLES
    }
    specs, summary, h3, placebo = (
        tables[n] for n in ("specifications", "summary", "h3", "placebo")
    )
    text = "# Стійкість оцінок, studytime та плацебо (P06)\n\n"
    candidates = summary.loc[
        summary["variant"].isin(["R1", "R2", "R4", "R5"])
        & summary["parent"].eq("Medu")
        & summary["status"].eq("available")
    ]
    text += f"Додатний знак Medu_4 збережено у {int(candidates['estimate'].gt(0).sum())}/{len(candidates)} оцінюваних categorical-варіантах стійкості. Величини й точність відрізняються; це не вимога значущості в кожній підгрупі.\n\n"

    text += "Усі результати нижче згенеровано з outputs/tables/robustness_*.csv. HC3/use_t=false, 95% normal CI. Усі p/CI P06 описові або перевірки чутливості; CI не одночасні. Варіанти не накопичуються; H1/H2 і числовий вердикт P05 залишаються незмінними.\n\n"
    text += "## Повнота варіантів та відмови\n\n"
    text += (
        _table(
            specs[
                [
                    c
                    for c in (
                        "subject",
                        "base_model_id",
                        "variant",
                        "school",
                        "nobs",
                        "model_status",
                        "reason",
                        "input_layer",
                    )
                    if c in specs
                ]
            ]
        )
        + "\n\n"
    )
    text += "Відмова not_estimable — видимий результат перевірки оцінюваності, не нульова beta. Шкільні пороги N>=50, count1/count4>=5, повний ранг, df>0, leverage<0.999999 незмінні; mat/MS N46 не оцінюємо.\n\n"
    text += "## Освіта батьків: categorical-контрасти\n\n"
    text += (
        _table(
            summary.loc[
                summary["variant"].ne("R3"),
                [
                    c
                    for c in (
                        "subject",
                        "variant",
                        "school",
                        "parent",
                        "nobs",
                        "estimate",
                        "ci_low",
                        "ci_high",
                        "delta_beta",
                        "status",
                        "reason",
                    )
                    if c in summary
                ],
            ]
        )
        + "\n\n"
    )
    text += "R1 повертає освіту0; R2 виключає лише G3=0; R4 аналізує школи окремо; R5 додає studytime. Зміна beta описова: зміна вибірки може змінювати склад порівнюваних груп. Стійкість оцінюємо за знаком, величиною та CI, без вимоги p<0.05 у всіх варіантах. Неперетин або перекриття CI не є тестом різниці.\n\n"
    text += (
        "## R3: інша одиниця вимірювання\n\n"
        + _table(summary.loc[summary["variant"].eq("R3")])
        + "\n\n"
    )
    text += "Ordinal beta описує зміну на один рівень за припущення однакового приросту. Це інший estimand; його величину не прирівнюємо до вища-vs-початкова й не множимо на3 як заміну categorical-контрасту. Delta_beta до baseline тут NA.\n\n"
    text += "## H3: додавання studytime\n\n" + _table(h3) + "\n\n"
    for row in h3.itertuples():
        change = (
            "зменшилася"
            if row.delta_abs < 0
            else "збільшилася"
            if row.delta_abs > 0
            else "не змінилася"
        )
        text += f"- {row.subject}: Medu_4 {row.beta_base:.3f} → {row.beta_augmented:.3f}; delta_abs={row.delta_abs:.3f}, абсолютна оцінка {change}.\n"
    text += "\nH3 описове: p-value або CI для delta_abs не обчислювали. CI окремих beta — невизначеність цих оцінок. Studytime — категорії, не точні години; зміна після контролювання не доводить медіацію або причинний механізм.\n\n"
    text += "## Noise-плацебо\n\n" + _table(placebo) + "\n\n"
    text += "На предмет рівно один noise-вектор N(0,1) у baseline-порядку: default_rng(seed+101) mat і seed+102 por. Шум не перегенеровували залежно від p; випадкова значущість можлива. Raw p описовий, не нова сім'я H1/H2. Плацебо не є permutation p-value або доказом відсутності confounding.\n\n"
    diagnostic = tables["diagnostics"]
    core = [
        c
        for c in (
            "subject",
            "variant",
            "school",
            "nobs",
            "rank",
            "df_resid",
            "max_leverage",
            "max_vif",
            "cooks_flag_count",
            "leverage_flag_count",
            "model_status",
            "reason",
        )
        if c in diagnostic
    ]
    text += "## Діагностика та межі\n\n" + _table(diagnostic[core]) + "\n\n"
    count_columns = [c for c in diagnostic if c.startswith(("Medu_", "Fedu_")) and c.endswith("_n")]
    text += (
        "### Частоти освіти в R1/R4\n\n"
        + _table(
            diagnostic.loc[
                diagnostic["variant"].isin(["R1", "R4"]),
                ["subject", "variant", "school", "nobs", *count_columns],
            ]
        )
        + "\n\n"
    )

    high_vif = diagnostic.loc[diagnostic["max_vif"].gt(5)]
    for row in high_vif.itertuples():
        text += f"Діагностичний сигнал: {row.subject}, {row.variant}, школа {row.school}: max VIF={row.max_vif:.3f}>5. Точність окремих умовних оцінок обмежена; регресори не вилучали.\n\n"
    max_h = diagnostic.loc[diagnostic["max_leverage"].idxmax()]
    text += f"Найбільший leverage {max_h['max_leverage']:.3f} у {max_h['subject']}/{max_h['variant']}; технічна межа не порушена. Рідкісні категорії R1 і впливові записи потребують обережної інтерпретації.\n\n"
    text += "VIF за термами — robustness_vif.csv. Cook/leverage/VIF-прапорці не видаляють записи. Baseline звірено з P05 на atol=rtol=1e-10; усі baseline_check мають matches=true. Три фігури у PNG/SVG показують різні estimands окремо й залишають видимими відмови.\n\n"
    text += "Самозвіти, дві школи, невиміряні здібності/ресурси, можливий перетин предметів та оригінальний відбір моделі обмежують узагальнення. Немає причинного ефекту або доказу відсутності асоціації з незначущості. Guardian-розбіжність M10, невідомий авторський SE й бібліографічна вимога курсу лишаються відкритими. Передача P07: P06_handoff.md; аудит: reviews/P06_robustness_review.md. K3 ще не пройдена.\n"
    Path(destination).write_text(text, encoding="utf-8")


def run_robustness(root=ROOT):
    root = Path(root)
    marker = root / "outputs/logs/robustness_run.json"
    record = {"status": "running", "created_at_utc": datetime.now(UTC).isoformat()}
    _record(marker, record)
    try:
        environment = check_environment()
        inputs = load_robustness_inputs(root)
        names = {
            "outputs/logs/replication_run.json",
            "docs/K2_replication.md",
            "docs/reviews/P05_replication_review.md",
        }
        for mapping in _p05_expected_paths(root).values():
            names.update(mapping)
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
                "source_hashes": {n: digest(root / n) for n in SOURCES},
                "input_hashes": {n: digest(root / n) for n in sorted(names)},
                "inference": inputs["config"]["inference"],
                "robustness": inputs["config"]["robustness"],
                "placebo": inputs["config"]["placebo"],
                "seed": inputs["config"]["project"]["seed"],
            }
        )
        directory = root / "outputs/tables"
        baseline = _baseline(inputs["layers"]["replication"], inputs["config"], directory)
        _require(not baseline.empty and baseline["matches"].all(), "Baseline differs from P05.")
        built = _build(inputs["layers"], inputs["config"])
        tables = {
            "baseline_check": baseline,
            **{n: built[n] for n in TABLES if n != "baseline_check"},
        }
        _require(len(tables["specifications"]) == 16, "Incomplete robustness candidate set.")
        _require(len(tables["h3"]) == 2 and len(tables["placebo"]) == 2, "Incomplete H3/placebo.")
        directory.mkdir(parents=True, exist_ok=True)
        paths = []
        for name, frame in tables.items():
            p = directory / f"robustness_{name}.csv"
            frame.to_csv(p, index=False, lineterminator="\n", float_format="%.17g")
            paths.append(p)
        for name in ("membership", "row_diagnostics", "noise"):
            p = root / f"data/processed/robustness_{name}.csv"
            built[name].to_csv(p, index=False, lineterminator="\n", float_format="%.17g")
            paths.append(p)
        figures = _render(directory, root / "outputs/figures")
        _require(len(figures) == 6, "Incomplete robustness figure set.")
        findings = root / "docs/robustness_findings.md"
        write_robustness_findings(directory, findings)
        record.update(
            {
                "status": "ready",
                "completed_at_utc": datetime.now(UTC).isoformat(),
                "outputs": {
                    str(p.relative_to(root)): digest(p)
                    for p in [*paths, *figures.values(), findings]
                },
                "candidate_counts": tables["specifications"]["model_status"]
                .value_counts()
                .to_dict(),
            }
        )
        _record(marker, record)
        return {"tables": tables, "figures": figures, "metadata": record}
    except Exception as error:
        record.update({"status": "failed", "error_type": type(error).__name__, "error": str(error)})
        _record(marker, record)
        raise
