"""Build P08 Quarto materials from audited CSVs, never from model fitting."""

import argparse
import json
import os
import re
import shutil
import subprocess
import tomllib
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from plotly.offline import get_plotlyjs

from parentedu.conclusions_workflow import SOURCES as P07_SOURCES
from parentedu.conclusions_workflow import check_audit_seal
from parentedu.eda_workflow import digest
from parentedu.paths import ROOT
from parentedu.presentation_reporting import (
    collect_report_values,
    create_report_figures,
    format_value,
)

VERSION = "1.11.9"
ARCHIVE_SHA256 = "eda220a2f39c392f622049de013ddf7b4dfdf019ba877f251be14ce43e5734d1"
URL = f"https://github.com/quarto-dev/quarto-cli/releases/download/v{VERSION}/quarto-{VERSION}-win.zip"
TOKENS = re.compile(r"\{\{(v|meta|f|table):([^}]+)\}\}")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def record(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def verify_readiness(root=ROOT):
    root = Path(root)
    path = root / "outputs/logs/conclusions_run.json"
    meta = json.loads(path.read_text(encoding="utf-8"))
    require(
        meta.get("status") == "ready" and meta.get("audit_status") == "PASS", "P07/K3 is not ready."
    )
    require(set(meta.get("source_hashes", {})) == set(P07_SOURCES), "Incomplete P07 source hashes.")
    require(
        len(meta.get("outputs", {})) == 6 and bool(meta.get("input_hashes")),
        "Incomplete P07 evidence.",
    )
    for group in ("source_hashes", "input_hashes", "outputs"):
        for name, expected in meta[group].items():
            p = (root / name).resolve()
            require(p.is_relative_to(root.resolve()), "Evidence path escapes project.")
            require(digest(p) == expected, f"Stale P07 evidence: {name}")
    require(check_audit_seal(root, meta["outputs"]) == "PASS", "K3 research audit is not PASS.")
    return meta


def setup_quarto(root):
    cache = root / "build/toolchain"
    executable = cache / "quarto/bin/quarto.exe"
    if not executable.exists():
        cache.mkdir(parents=True, exist_ok=True)
        archive = cache / f"quarto-{VERSION}-win.zip"
        if not archive.exists():
            request = urllib.request.Request(URL, headers={"User-Agent": "parentedu-course-report"})
            with (
                urllib.request.urlopen(request, timeout=90) as response,
                archive.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
        require(digest(archive) == ARCHIVE_SHA256, "Quarto archive checksum mismatch.")
        destination = cache / "quarto"
        with zipfile.ZipFile(archive) as archive_file:
            for item in archive_file.infolist():
                require(
                    (destination / item.filename).resolve().is_relative_to(destination.resolve()),
                    "Unsafe tool archive path.",
                )
            archive_file.extractall(destination)
    version = subprocess.check_output([str(executable), "--version"], text=True).strip()
    require(version == VERSION, "Unexpected Quarto version.")
    return executable


def md_table(frame):
    def cell(v):
        if pd.isna(v):
            return "—"
        if isinstance(v, float):
            return f"{v:.3f}"
        return str(v).replace("|", "\\|")

    return "\n".join(
        [
            "| " + " | ".join(map(str, frame.columns)) + " |",
            "| " + " | ".join(["---"] * len(frame.columns)) + " |",
            *[
                "| " + " | ".join(cell(v) for v in row) + " |"
                for row in frame.itertuples(index=False, name=None)
            ],
        ]
    )


def tables(root):
    model = pd.read_csv(root / "outputs/tables/replication_models.csv")
    model = model[["subject", "model_id", "nobs", "rank", "adjusted_r2"]].rename(
        columns={
            "subject": "Предмет",
            "model_id": "Модель",
            "nobs": "N",
            "rank": "Параметрів",
            "adjusted_r2": "Adjusted R²",
        }
    )
    hyp = pd.read_csv(root / "outputs/tables/final_hypotheses.csv")
    hyp = hyp[["subject", "family", "estimate", "ci_low", "ci_high", "p_holm", "status"]].rename(
        columns={
            "subject": "Предмет",
            "family": "Гіпотеза",
            "estimate": "Оцінка",
            "ci_low": "CI нижня",
            "ci_high": "CI верхня",
            "p_holm": "p Holm",
            "status": "Вердикт",
        }
    )
    hyp["Вердикт"] = hyp["Вердикт"].replace(
        {
            "expected_supported": "Підтримано",
            "insufficient_evidence": "Невизначено",
            "descriptive_decrease": "Описове",
        }
    )
    hyp = hyp.rename(columns={"CI нижня": "CI низ", "CI верхня": "CI верх"})
    hyp["p Holm"] = hyp["p Holm"].map(lambda v: format_value(v, "p_holm"))
    se = (
        pd.read_csv(root / "outputs/tables/replication_se_comparison.csv")
        .groupby("covariance_type")["matches"]
        .agg(["sum", "count"])
        .reset_index()
    )
    se.columns = ["Наш метод SE", "Збігів", "Клітинок"]
    coefficients = pd.read_csv(root / "outputs/tables/replication_coefficients.csv")
    full_models = [md_table(model)]
    for subject, label in (("mat", "Математика"), ("por", "Португальська")):
        part = coefficients.loc[
            (coefficients.subject == subject)
            & (coefficients.covariance_type == "HC3")
            & (coefficients.variant == "baseline")
        ].copy()
        part["beta_se"] = part.apply(lambda r: f"{r.estimate:.3f} ({r.std_error:.3f})", axis=1)
        wide = part.pivot(index="term", columns="model_id", values="beta_se")
        order = list(dict.fromkeys(part.term))
        wide = wide.reindex(order).fillna("—")
        wide = (
            wide[sorted(wide.columns, key=lambda c: int(c[1:]))]
            .reset_index()
            .rename(columns={"term": "Терм"})
        )
        wide["Терм"] = wide["Терм"].replace(
            {
                "intercept": "Константа",
                "age": "Вік",
                "sex_F": "Стать F",
                "school_GP": "Школа GP",
                "guardian_mother": "Опікун: мати",
                "guardian_father": "Опікун: батько",
            }
        )
        full_models.extend([f"### {label}: коефіцієнт (HC3 SE)", md_table(wide)])
    return {"models": "\n\n".join(full_models), "hypotheses": md_table(hyp), "se": md_table(se)}


def substitute(source, values, metadata, figures, table_fragments, mode, usage):
    col = "display_slide" if mode == "slides" else "display_report"
    lookup = values.set_index("value_id")

    def token(match):
        kind, key = match.group(1), match.group(2)
        usage.append((kind, key))
        if kind == "v":
            require(key in lookup.index, f"Missing report value: {key}")
            return str(lookup.loc[key, col])
        if kind == "meta":
            require(key in metadata, f"Missing personal metadata: {key}")
            return str(metadata[key])
        if kind == "table":
            require(key in table_fragments, f"Unknown table fragment: {key}")
            return table_fragments[key]
        require(key in figures, f"Unknown figure: {key}")
        if mode == "slides":
            return "\n```{=html}\n" + figures[key]["html"].read_text(encoding="utf-8") + "\n```\n"
        return f"\n![](assets/{figures[key]['svg'].name}){{width=95%}}\n"

    text = TOKENS.sub(token, source)
    require(not TOKENS.search(text), "Unresolved report token.")
    return text


def build(root=ROOT, render=True):
    root = Path(root)
    marker = root / "outputs/logs/reports_run.json"
    meta = {"status": "running", "created_at_utc": datetime.now(UTC).isoformat()}
    record(marker, meta)
    try:
        p07 = verify_readiness(root)
        personal = tomllib.loads((root / "reports/metadata.toml").read_text(encoding="utf-8"))
        require(
            all(personal.get(n) for n in ("author", "group", "date")), "Author/group/date required."
        )
        values = collect_report_values(root)
        values.to_csv(root / "outputs/tables/report_values.csv", index=False, lineterminator="\n")
        assets = root / "reports/assets"
        figures = create_report_figures(root, assets)
        work = root / "build/p08"
        work.mkdir(parents=True, exist_ok=True)
        (assets / "plotly.min.js").write_text(get_plotlyjs(), encoding="utf-8")
        shutil.copytree(assets, work / "assets", dirs_exist_ok=True)
        parts = tables(root)
        mapping = []
        for name, mode in (("report", "report"), ("slides", "slides")):
            source = (root / f"reports/{name}.qmd").read_text(encoding="utf-8")
            usage = []
            generated = substitute(source, values, personal, figures, parts, mode, usage)
            if name == "slides":
                # A custom first slide is already in the source; suppress an automatic title slide.
                generated = re.sub(r"^title:.*\n", "", generated, count=1, flags=re.MULTILINE)
                script_path = (assets / "plotly.min.js").as_posix()
                header = (
                    "theme: [simple, slides.scss]\n    html-math-method: mathml\n    pdf-separate-fragments: false\n    pdf-max-pages-per-slide: 1\n    include-in-header:\n      - text: "
                    + json.dumps('<script src="' + script_path + '"></script>')
                )
                generated = generated.replace("theme: [simple, slides.scss]", header)
                matches = list(re.finditer(r"^## .*?\{#([a-z]\d{2})[^}]*\}", source, re.MULTILINE))
                require(len(matches) == 16, "Expected twelve main and four backup slides.")
                for i, item in enumerate(matches):
                    fragment = source[
                        item.start() : matches[i + 1].start()
                        if i + 1 < len(matches)
                        else len(source)
                    ]
                    for kind, key in TOKENS.findall(fragment):
                        mapping.append(
                            {
                                "artifact": "slides",
                                "section_id": item.group(1),
                                "kind": kind,
                                "value_or_figure": key,
                            }
                        )
                notes = []
                for block in re.finditer(r"::: \{\.notes\}\n(.*?)\n:::", generated, re.DOTALL):
                    notes.append(block.group(1).strip())
                require(len(notes) == 16, "Missing slide speaker notes.")
                (root / "reports/speaker_notes.md").write_text(
                    "# Нотатки доповідача\n\n"
                    "Основні s01–s12: бюджет 720 с (12 хв), без фактичної репетиції. "
                    "b01–b04 — резерв поза бюджетом.\n\n"
                    + "\n\n---\n\n".join(
                        f"## {item.group(1)}\n\n{note}"
                        for item, note in zip(matches, notes, strict=True)
                    )
                    + "\n",
                    encoding="utf-8",
                )
            else:
                generated = generated.replace(
                    "fontsize: 17px", "fontsize: 17px\n    html-math-method: mathml"
                )
                headings = list(re.finditer(r"^## (.+)$", source, re.MULTILINE))
                for i, heading in enumerate(headings):
                    fragment = source[
                        heading.start() : headings[i + 1].start()
                        if i + 1 < len(headings)
                        else len(source)
                    ]
                    for kind, key in TOKENS.findall(fragment):
                        mapping.append(
                            {
                                "artifact": "report",
                                "section_id": f"r{i + 1:02d}",
                                "section_title": heading.group(1),
                                "kind": kind,
                                "value_or_figure": key,
                            }
                        )
                for kind, key in TOKENS.findall(source[: headings[0].start()]):
                    mapping.append(
                        {
                            "artifact": "report",
                            "section_id": "title",
                            "kind": kind,
                            "value_or_figure": key,
                        }
                    )
            (work / f"{name}.qmd").write_text(generated, encoding="utf-8")
        source_lookup = values.set_index("value_id")
        fragment_sources = {
            "models": "outputs/tables/replication_models.csv;outputs/tables/replication_coefficients.csv",
            "hypotheses": "outputs/tables/final_hypotheses.csv",
            "se": "outputs/tables/replication_se_comparison.csv",
            "education": "outputs/tables/eda_category_counts.csv",
            "h1": "outputs/tables/final_hypotheses.csv",
            "h2": "outputs/tables/final_hypotheses.csv",
            "h3": "outputs/tables/final_hypotheses.csv",
            "robustness": "outputs/tables/final_robustness.csv",
            "placebo": "outputs/tables/robustness_placebo.csv",
        }
        for row in mapping:
            key = row["value_or_figure"]
            if row["kind"] == "v":
                row.update(
                    {
                        field: source_lookup.loc[key, field]
                        for field in (
                            "claim_id",
                            "source_table",
                            "source_hash",
                            "row_key_json",
                            "metric",
                        )
                    }
                )
            elif row["kind"] in {"table", "f"}:
                row["source_table"] = fragment_sources[key]
                row["source_hash"] = ";".join(
                    digest(root / p) for p in fragment_sources[key].split(";")
                )
                row["claim_id"] = {
                    "h1": "H1_mat;H1_por",
                    "h2": "H2_mat;H2_por",
                    "h3": "H3_mat;H3_por",
                    "robustness": "robustness_direction",
                    "se": "author_inference",
                    "models": "numeric_replication",
                    "education": "scope_limits",
                    "placebo": "placebo_mat;placebo_por",
                    "hypotheses": "H1_mat;H1_por;H2_mat;H2_por;H3_mat;H3_por",
                }[key]
        pd.DataFrame(mapping).to_csv(
            root / "reports/content_map.csv", index=False, lineterminator="\n"
        )
        for filename in ("slides.scss", "references.bib"):
            shutil.copyfile(root / "reports" / filename, work / filename)
        shutil.copyfile(root / "reports/_quarto.yml", work / "_quarto.yml")
        output = root / "reports/rendered"
        output.mkdir(parents=True, exist_ok=True)
        meta.update(
            {
                "git_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                "git_dirty": bool(
                    subprocess.check_output(
                        ["git", "status", "--porcelain"], cwd=root, text=True
                    ).strip()
                ),
                "k3_output_hashes": p07["outputs"],
                "input_hashes": {
                    str(p.relative_to(root)): digest(p)
                    for p in [root / name for name in sorted(set(values.source_table))]
                },
                "source_hashes": {
                    str(p.relative_to(root)): digest(p)
                    for p in [
                        root / "scripts/build_reports.py",
                        root / "scripts/render_report_browser.mjs",
                        root / "scripts/validate_report_pdfs.py",
                        root / "src/parentedu/presentation_reporting.py",
                        *[
                            root / "reports" / n
                            for n in (
                                "report.qmd",
                                "slides.qmd",
                                "slides.scss",
                                "references.bib",
                                "metadata.toml",
                                "_quarto.yml",
                            )
                        ],
                    ]
                },
            }
        )
        if render:
            quarto = setup_quarto(root)
            env = os.environ.copy()
            import matplotlib

            env["TYPST_FONT_PATHS"] = str(Path(matplotlib.get_data_path()) / "fonts/ttf")
            for file, fmt in (
                ("report.qmd", "html"),
                ("report.qmd", "typst"),
                ("slides.qmd", "revealjs"),
            ):
                subprocess.run(
                    [
                        str(quarto),
                        "render",
                        file,
                        "--to",
                        fmt,
                        "--output-dir",
                        str(output),
                        "--no-execute",
                    ],
                    cwd=work,
                    env=env,
                    check=True,
                    timeout=180,
                )
            runtime = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies"
            node = runtime / "node/bin/node.exe"
            modules = runtime / "node/node_modules"
            browser = Path(
                os.environ.get(
                    "REPORT_BROWSER", r"C:/Program Files/Google/Chrome/Application/chrome.exe"
                )
            )
            subprocess.run(
                [
                    str(node),
                    str(root / "scripts/render_report_browser.mjs"),
                    "--root",
                    str(root),
                    "--modules",
                    str(modules),
                    "--browser",
                    str(browser),
                ],
                cwd=root,
                check=True,
                timeout=180,
            )
            subprocess.run(
                [
                    str(runtime / "python/python.exe"),
                    str(root / "scripts/validate_report_pdfs.py"),
                    "--root",
                    str(root),
                ],
                check=True,
                cwd=root,
                timeout=60,
            )
            browser_checks = json.loads(
                (work / "browser_validation.json").read_text(encoding="utf-8")
            )
            record(
                root / "reports/toolchain_manifest.json",
                {
                    "quarto_version": VERSION,
                    "source_url": URL,
                    "archive_sha256": ARCHIVE_SHA256,
                    "browser": "Chromium via installed Chrome",
                    "browser_version": browser_checks["browser_version"],
                    "pdf_metadata_date": "2026-11-06 (project date, normalized)",
                    "pdf_engine": "Quarto Typst",
                    "typst_version": subprocess.check_output(
                        [str(quarto.parent / "tools/x86_64/typst.exe"), "--version"], text=True
                    ).strip(),
                    "node_version": subprocess.check_output(
                        [str(node), "--version"], text=True
                    ).strip(),
                    "playwright_version": subprocess.check_output(
                        [str(node), "-p", "require('playwright/package.json').version"],
                        cwd=modules,
                        text=True,
                    ).strip(),
                    "document_packages": subprocess.check_output(
                        [
                            str(runtime / "python/python.exe"),
                            "-c",
                            "import pypdf; print('pypdf ' + pypdf.__version__)",
                        ],
                        text=True,
                    ).strip(),
                    "math": "native MathML offline",
                    "browser_automation": "bundled Playwright",
                    "python_packages": "unchanged uv.lock",
                },
            )
        outputs = [
            root / "outputs/tables/report_values.csv",
            root / "reports/content_map.csv",
            root / "reports/speaker_notes.md",
            *[p for p in assets.iterdir() if p.is_file()],
        ]
        if render:
            outputs.extend(
                output / p for p in ("report.html", "report.pdf", "slides.html", "slides.pdf")
            )
            outputs.append(root / "reports/toolchain_manifest.json")
        meta.update(
            {
                "status": "ready" if render else "data_prepared",
                "completed_at_utc": datetime.now(UTC).isoformat(),
                "outputs": {str(p.relative_to(root)): digest(p) for p in outputs},
                "value_count": len(values),
                "course_submission_status": "open",
            }
        )
        record(marker, meta)
        return meta
    except Exception as error:
        meta.update({"status": "failed", "error_type": type(error).__name__, "error": str(error)})
        record(marker, meta)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-render", action="store_true")
    build(render=not parser.parse_args().skip_render)
