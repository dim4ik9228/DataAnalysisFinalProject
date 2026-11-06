"""P07 synthesizes audited CSV evidence without fitting models or querying the web."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from parentedu.eda_workflow import digest
from parentedu.environment import check_environment
from parentedu.paths import ROOT
from parentedu.robustness_workflow import SOURCES as P06_SOURCES
from parentedu.robustness_workflow import TABLES as P06_TABLES
from parentedu.robustness_workflow import _p05_expected_paths

SOURCES = (
    "src/parentedu/conclusions.py",
    "src/parentedu/conclusions_workflow.py",
    "notebooks/05_conclusions.ipynb",
)
FINAL_TABLES = ("hypotheses", "verdicts", "robustness", "claims", "claim_evidence")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _record(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _p06_expected_paths(root):
    inputs = {
        "outputs/logs/replication_run.json",
        "docs/K2_replication.md",
        "docs/reviews/P05_replication_review.md",
    }
    for names in _p05_expected_paths(root).values():
        inputs.update(names)
    outputs = {
        *[f"outputs/tables/robustness_{name}.csv" for name in P06_TABLES],
        *[
            f"data/processed/robustness_{name}.csv"
            for name in ("membership", "row_diagnostics", "noise")
        ],
        *[
            f"outputs/figures/robustness_{name}.{ext}"
            for name in ("categorical", "ordinal", "h3")
            for ext in ("png", "svg")
        ],
        "docs/robustness_findings.md",
    }
    return {"source_hashes": set(P06_SOURCES), "input_hashes": inputs, "outputs": outputs}


def _verify_phase(root, name, expected):
    record = json.loads((root / f"outputs/logs/{name}_run.json").read_text(encoding="utf-8"))
    _require(
        record.get("status") == "ready", f"{name} is not ready; restore the preceding notebook."
    )
    for group, names in expected.items():
        hashes = record.get(group, {})
        normalized = {Path(n).as_posix(): value for n, value in hashes.items()}
        _require(set(normalized) == names, f"Incomplete {name} {group} manifest.")
        for relative, expected_hash in hashes.items():
            path = (root / relative).resolve()
            _require(path.is_relative_to(root.resolve()), "Evidence path escapes the project.")
            _require(digest(path) == expected_hash, f"Stale {name} evidence: {relative}.")
    return record


def load_conclusion_inputs(root=ROOT):
    """Check status and every recorded dependency before reading synthesis tables."""
    root = Path(root)
    p05 = _verify_phase(root, "replication", _p05_expected_paths(root))
    p06 = _verify_phase(root, "robustness", _p06_expected_paths(root))
    for name, status in (("data", "prepared"), ("eda", "ready")):
        record = json.loads((root / f"outputs/logs/{name}_run.json").read_text(encoding="utf-8"))
        _require(record.get("status") == status, f"{name} phase is not ready.")
    for path in ("docs/reviews/P05_replication_review.md", "docs/reviews/P06_robustness_review.md"):
        _require(
            "PASS" in (root / path).read_text(encoding="utf-8"), f"Missing passed audit: {path}"
        )
    followup = root / "docs/evidence/literature_followup"
    manifest = json.loads((followup / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest if isinstance(manifest, list) else manifest["files"]
    _require(bool(entries), "Empty literature evidence manifest.")
    for item in entries:
        path = (
            (root / item["path"]).resolve()
            if "path" in item
            else (followup / item["file"]).resolve()
        )
        _require(path.is_relative_to(followup.resolve()), "Invalid literature evidence path.")
        _require(
            digest(path) == item["sha256"],
            f"Changed literature evidence: {item.get('path', item.get('file'))}",
        )
    summary = json.loads((followup / "summary.json").read_text(encoding="utf-8"))
    _require(summary["status"] in ("met", "unresolved"), "Unknown bibliography status.")
    _require(
        summary["required_min"] == 3 and summary["verified_direct_count"] >= 0,
        "Invalid bibliography count.",
    )
    _require(
        summary["status"] != "met" or summary["verified_direct_count"] >= 3,
        "Bibliography marked met without enough verified direct works.",
    )
    names = {
        "outputs/logs/replication_run.json",
        "outputs/logs/robustness_run.json",
        "docs/P06_handoff.md",
        "docs/reviews/P06_robustness_review.md",
        "docs/replication_protocol.md",
        "docs/literature.csv",
        "docs/literature_review.md",
        "docs/course_requirements.md",
        "docs/literature_followup.csv",
        "docs/literature_followup.md",
    }
    for mapping in _p06_expected_paths(root).values():
        names.update(mapping)
    names.update(p.relative_to(root).as_posix() for p in followup.rglob("*") if p.is_file())
    return {
        "p05": p05,
        "p06": p06,
        "input_hashes": {n: digest(root / n) for n in sorted(names)},
        "literature": summary,
    }


def _build(root):
    from parentedu.conclusions import build_conclusion_tables

    return build_conclusion_tables(root / "outputs/tables", root)


def write_conclusions(table_dir, destination):
    """Render only registered claims; row-level proof remains in the evidence CSV."""
    table_dir = Path(table_dir)
    claims = pd.read_csv(table_dir / "final_claims.csv", keep_default_na=False)
    evidence = pd.read_csv(table_dir / "final_claim_evidence.csv", keep_default_na=False)
    _require(
        not claims.empty and not claims.claim_id.duplicated().any(), "Invalid final claim registry."
    )
    _require(set(evidence.claim_id) == set(claims.claim_id), "Claims/evidence coverage mismatch.")
    text = "# Підсумкові висновки дослідження\n\n"
    priority = {
        cid: i
        for i, cid in enumerate(
            (
                "H1_mat",
                "H1_por",
                "numeric_replication",
                "author_inference",
                "H2_mat",
                "H2_por",
                "H3_mat",
                "H3_por",
            )
        )
    }
    claims = claims.assign(_order=claims.claim_id.map(priority).fillna(100)).sort_values(
        "_order", kind="stable"
    )
    for row in claims.itertuples():
        text += f"### {row.claim_id}\n\n{row.text_uk}\n\n"
        sources = evidence.loc[evidence.claim_id.eq(row.claim_id), "source_table"].drop_duplicates()
        links = []
        for name in sources:
            path = Path(name)
            relative = (
                "../" + path.as_posix()
                if path.parts[0] != "docs"
                else Path(*path.parts[1:]).as_posix()
            )
            links.append(f"[{path.name}]({relative})")
        text += (
            "Джерела: "
            + ", ".join(links)
            + ". Ключі рядків, значення та правила агрегацій — [реєстр доказів](../outputs/tables/final_claim_evidence.csv).\n\n"
        )
    text += "Фінальні таблиці: [H1–H3](../outputs/tables/final_hypotheses.csv), [окремі вердикти](../outputs/tables/final_verdicts.csv), [стійкість](../outputs/tables/final_robustness.csv). Аудит тверджень — [P07](reviews/P07_conclusions_review.md); окреме рішення дослідницької готовності — [K3](K3_conclusions.md). K3 не означає готовності курсової до здачі: звіт, презентація та повний запуск належать наступним фазам.\n"
    Path(destination).write_text(text, encoding="utf-8")


def check_audit_seal(root, outputs):
    """A seal is optional for synthesis, and checks a completed audit after export."""
    path = root / "docs/K3_conclusions.json"
    if not path.exists():
        return "not_recorded"
    seal = json.loads(path.read_text(encoding="utf-8"))
    expected = {Path(n).as_posix(): value for n, value in seal["audited_outputs"].items()}
    actual = {Path(n).as_posix(): value for n, value in outputs.items()}
    _require(
        actual == expected,
        "K3 audit is stale: final outputs changed; request a new review before using K3.",
    )
    _require(
        digest(root / "docs/reviews/P07_conclusions_review.md") == seal["review_sha256"],
        "K3 audit is stale: review changed; reseal after review.",
    )
    return seal["research_verdict"]


def run_conclusions(root=ROOT):
    root = Path(root)
    marker = root / "outputs/logs/conclusions_run.json"
    record = {"status": "running", "created_at_utc": datetime.now(UTC).isoformat()}
    _record(marker, record)
    try:
        environment = check_environment()
        inputs = load_conclusion_inputs(root)
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
                "input_hashes": inputs["input_hashes"],
                "bibliography_status": inputs["literature"],
            }
        )
        tables = _build(root)
        _require(set(tables) == set(FINAL_TABLES), "Incomplete final table set.")
        directory = root / "outputs/tables"
        paths = []
        for name, frame in tables.items():
            path = directory / f"final_{name}.csv"
            frame.to_csv(path, index=False, lineterminator="\n", float_format="%.17g")
            paths.append(path)
        findings = root / "docs/final_conclusions.md"
        write_conclusions(directory, findings)
        output_hashes = {str(p.relative_to(root)): digest(p) for p in [*paths, findings]}
        record["audit_status"] = check_audit_seal(root, output_hashes)
        record.update(
            {
                "status": "ready",
                "completed_at_utc": datetime.now(UTC).isoformat(),
                "outputs": {str(p.relative_to(root)): digest(p) for p in [*paths, findings]},
                "claim_count": len(tables["claims"]),
                "evidence_count": len(tables["claim_evidence"]),
            }
        )
        _record(marker, record)
        return {"tables": tables, "metadata": record}
    except Exception as error:
        record.update({"status": "failed", "error_type": type(error).__name__, "error": str(error)})
        _record(marker, record)
        raise
