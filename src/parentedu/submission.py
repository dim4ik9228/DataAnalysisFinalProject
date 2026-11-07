"""Build and independently verify an allowlisted review-candidate archive."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from parentedu.paths import ROOT

MANIFEST = "package_manifest.json"
ROOT_FILES = {"README.md", "AGENTS.md", "pyproject.toml", "uv.lock", ".python-version"}
SOURCE_SUFFIXES = {
    ".py",
    ".mjs",
    ".toml",
    ".json",
    ".lock",
    ".md",
    ".txt",
    ".csv",
    ".ipynb",
    ".yml",
    ".yaml",
    ".qmd",
    ".scss",
    ".bib",
    ".xml",
    ".html",
}
TABLE_FILES = {
    "data_quality.csv",
    "sample_flow.csv",
    "replication_vif.csv",
    "replication_coefficients.csv",
    "replication_diagnostics.csv",
    "eda_numeric_summary.csv",
    "original_vs_ours_data.csv",
    "final_verdicts.csv",
    "robustness_h3.csv",
    "eda_category_counts.csv",
    "final_claim_evidence.csv",
    "robustness_coefficients.csv",
    "final_hypotheses.csv",
    "robustness_diagnostics.csv",
    "robustness_specifications.csv",
    "final_claims.csv",
    "robustness_vif.csv",
    "eda_parent_cross.csv",
    "robustness_placebo.csv",
    "robustness_baseline_check.csv",
    "replication_hypotheses.csv",
    "replication_se_comparison.csv",
    "replication_comparison.csv",
    "final_robustness.csv",
    "eda_correlations.csv",
    "replication_verdicts.csv",
    "eda_group_screen.csv",
    "eda_grade_by_education.csv",
    "robustness_summary.csv",
    "replication_models.csv",
    "eda_grade_counts.csv",
    "eda_sample_overview.csv",
    "report_values.csv",
}
FORBIDDEN_PARTS = {
    ".git",
    ".codex",
    ".venv",
    "__pycache__",
    "node_modules",
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
    "raw",
    "processed",
    "debug",
}
HOST_PATH = re.compile(r"[A-Za-z]:[\\/][^\s\"'<>]*|/(?:Users|home)/[^\s\"'<>]*")
STUDENT_COLUMNS = {
    "school",
    "sex",
    "age",
    "address",
    "famsize",
    "Pstatus",
    "Medu",
    "Fedu",
    "Mjob",
    "Fjob",
    "reason",
    "guardian",
    "G1",
    "G2",
    "G3",
}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _path(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError(f"Unsafe package path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in {"", ".", ".."} for p in name.split("/")):
        raise ValueError(f"Unsafe package path: {name!r}")
    if any(p.lower() in FORBIDDEN_PARTS or p.lower().startswith(".env") for p in path.parts):
        raise ValueError(f"Forbidden package path: {name}")
    return path


def _allowed(name):
    p = _path(name)
    if name in ROOT_FILES:
        return True
    if p.parts[0] in {"src", "scripts", "configs", "tests", "tools", "notebooks", "docs"}:
        return p.suffix in SOURCE_SUFFIXES
    if name.startswith("data/reference/"):
        return p.suffix in SOURCE_SUFFIXES
    if p.parts[0] == "reports":
        return p.suffix in SOURCE_SUFFIXES | {".pdf", ".svg", ".js"} and not any(
            part.lower() in {"qa", "drafts"} for part in p.parts
        )
    if name.startswith("outputs/tables/"):
        return len(p.parts) == 3 and p.name in TABLE_FILES
    if name.startswith("outputs/figures/"):
        return p.suffix in {".png", ".svg"}
    if name.startswith("outputs/executed/"):
        return p.suffix == ".ipynb"
    return False


def _read(root, name):
    _path(name)
    file = root / name
    if file.is_symlink() or not file.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Package input escapes project: {name}")
    return file.read_bytes()


def _notebook(data):
    """Preserve results; remove host metadata and redact absolute host paths in text."""
    notebook = json.loads(data)
    notebook["metadata"].pop("widgets", None)
    if notebook["cells"]:
        first = notebook["cells"][0]
        source = first.get("source", "")
        source = "".join(source) if isinstance(source, list) else source
        if (
            source.startswith("import sys, pathlib, parentedu\n")
            and "Fresh checkout kernel verified" in source
            and "assert pathlib.Path(sys.executable)" in source
        ):
            notebook["cells"].pop(0)
    for cell in notebook["cells"]:
        cell["metadata"] = {}
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                raise ValueError("Executed notebook contains an error")
            content = output.get("data", {})
            html = "".join(content.get("text/html", []))
            plain = "".join(content.get("text/plain", [])) + "".join(output.get("text", []))
            # A student-level display has several identifying/source columns together.
            if (
                len({c for c in STUDENT_COLUMNS if f">{c}<" in html}) >= 6
                or len(STUDENT_COLUMNS.intersection(plain.split())) >= 6
            ):
                raise ValueError("Executed notebook contains student-level debug rows")
            output.pop("metadata", None)

    def clean(value):
        if isinstance(value, str):
            return HOST_PATH.sub("<local-path>", value)
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        return value

    # Sources remain exact: only output and metadata text may be sanitized.
    notebook["metadata"] = clean(notebook.get("metadata", {}))
    for cell in notebook["cells"]:
        if "outputs" in cell:
            cell["outputs"] = clean(cell["outputs"])
    return (json.dumps(notebook, ensure_ascii=False, indent=1) + "\n").encode()


def verify_package(path):
    """Unpack into a fresh directory, reject unsafe/duplicate entries and verify every hash."""
    path = Path(path)
    with zipfile.ZipFile(path) as archive, TemporaryDirectory() as temporary:
        names = archive.namelist()
        if len(names) != len({n.casefold() for n in names}):
            raise ValueError("Duplicate archive paths")
        for name in names:
            _path(name)
            if (
                name not in {MANIFEST, "PACKAGE_README.md"}
                and not _allowed(name)
                and name != "outputs/logs/full_run.json"
            ):
                raise ValueError(f"File outside package allowlist: {name}")
            info = archive.getinfo(name)
            if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"Nonregular archive entry: {name}")
        manifest = json.loads(archive.read(MANIFEST))
        rows = manifest["files"]
        listed = [r["path"] for r in rows]
        if len(listed) != len(set(listed)) or set(listed) != set(names) - {MANIFEST}:
            raise ValueError("Manifest does not enumerate exactly the payload")
        archive.extractall(temporary)
        for row in rows:
            content = (Path(temporary) / row["path"]).read_bytes()
            if len(content) != row["size"] or _sha(content) != row["sha256"]:
                raise ValueError(f"Package hash mismatch: {row['path']}")
    return manifest


def build_package(root=ROOT, run_record=None, destination=None):
    """Package only a current, fully validated run; return ZIP and detached checksum paths."""
    from parentedu.reproducibility import validate_full_run

    root = Path(root).resolve()
    run_path = Path(run_record or root / "outputs/logs/full_run.json")
    if not run_path.is_absolute():
        run_path = root / run_path
    record = json.loads(run_path.read_text(encoding="utf-8"))
    validate_full_run(root, record)
    tracked = (
        subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True)
        .stdout.decode()
        .split("\0")
    )
    names = {n for n in tracked if n and _safe_allowed(n)}
    # Generated research artifacts must be proven by this run, even when tracked.
    verified = set(record["outputs"])
    names = {
        n for n in names if not n.startswith(("outputs/", "reports/rendered/")) or n in verified
    }
    names.update(n for n in verified if _safe_allowed(n))
    names.update(n for n in record["source_hashes"] if _safe_allowed(n))
    for name in (
        "docs/K4_readiness.md",
        "docs/K4_readiness.json",
        "docs/submission_checklist.md",
        "docs/reviews/P09_reproducibility_review.md",
    ):
        if (root / name).is_file():
            names.add(name)
    run_name = "outputs/logs/full_run.json"
    payload = {n: _read(root, n) for n in sorted(names)}
    payload[run_name] = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode()
    for group in ("source_hashes", "input_hashes", "outputs"):
        for name, expected in record[group].items():
            if name in payload and _sha(payload[name]) != expected:
                raise ValueError(f"Changed package input after validation: {name}")
    transformations = {}
    for name in list(payload):
        if name.startswith("outputs/executed/"):
            original = payload[name]
            payload[name] = _notebook(original)
            transformations[name] = {
                "original_sha256": _sha(original),
                "operation": "remove runner guard; sanitize metadata/output host paths",
            }
    payload["PACKAGE_README.md"] = (
        "# Комплект для перевірки\n\n"
        "Review candidate; course_submission_status: open. ZIP не означає готовності до здачі.\n"
        "Інструкція запуску — README.md; відкриті вимоги — docs/submission_checklist.md.\n"
        "Сирі й підготовлені учнівські рядки не включено; відновіть UCI за pinned manifest.\n"
        "Виконані notebooks: результати збережено; runner guard видалено; локальні шляхи в outputs/metadata приховано.\n"
        "package_manifest.json перелічує payload; зовнішній .sha256 перевіряє ZIP.\n"
    ).encode()
    manifest = {
        "schema_version": 1,
        "package_status": "review_candidate",
        "course_submission_status": "open",
        "run_id": record["run_id"],
        "transformations": transformations,
        "files": [
            {"path": n, "size": len(d), "sha256": _sha(d)} for n, d in sorted(payload.items())
        ],
    }
    destination = Path(destination or root / "dist/submission-review-candidate.zip")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in payload.items():
            archive.writestr(name, content)
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    verify_package(destination)
    checksum = destination.with_suffix(destination.suffix + ".sha256")
    checksum.write_text(f"{_sha(destination.read_bytes())}  {destination.name}\n", encoding="utf-8")
    return destination, checksum


def _safe_allowed(name):
    try:
        return _allowed(name)
    except ValueError:
        return False
