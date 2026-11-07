"""Run the frozen notebook pipeline and validate fresh, content-bound receipts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from parentedu.eda_workflow import digest
from parentedu.paths import ROOT

PHASES = (
    ("environment", "00_project_setup.ipynb", "environment.json", None),
    ("data", "01_data.ipynb", "data_run.json", "prepared"),
    ("eda", "02_eda.ipynb", "eda_run.json", "ready"),
    ("replication", "03_replication.ipynb", "replication_run.json", "ready"),
    ("robustness", "04_robustness.ipynb", "robustness_run.json", "ready"),
    ("conclusions", "05_conclusions.ipynb", "conclusions_run.json", "ready"),
)
FROZEN = (
    "docs/K3_conclusions.json",
    "docs/reviews/P07_conclusions_review.md",
    "uv.lock",
    "configs/analysis.toml",
    "docs/replication_protocol.md",
)


def now():
    return datetime.now(UTC).isoformat()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def local_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(root), f"Path escapes project: {relative}")
    return path


def verify_hashes(root, hashes):
    for relative, expected in hashes.items():
        path = local_path(root, relative)
        require(path.is_file() and digest(path) == expected, f"Changed evidence: {relative}")


def source_hashes(root):
    root = Path(root)
    paths = []
    for directory, suffix in (
        ("src", ".py"),
        ("scripts", ".py"),
        ("scripts", ".mjs"),
        ("notebooks", ".ipynb"),
        ("configs", ".toml"),
        ("tests", ".py"),
    ):
        paths.extend((root / directory).rglob("*" + suffix))
    paths.extend(root / n for n in ("pyproject.toml", "uv.lock", ".python-version"))
    for name in (
        "report.qmd",
        "slides.qmd",
        "slides.scss",
        "references.bib",
        "metadata.toml",
        "_quarto.yml",
    ):
        paths.append(root / "reports" / name)
    for name in (
        "pyproject.toml",
        "uv.lock",
        "package.json",
        "package-lock.json",
        "setup.py",
        ".python-version",
    ):
        path = root / "tools/reporting" / name
        if path.exists():
            paths.append(path)
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(set(paths))}


def capture_baseline(root, destination):
    """Use committed aggregates as expectations, never as pipeline inputs."""
    root, destination = Path(root), Path(destination)
    names = subprocess.check_output(
        ["git", "ls-files", "outputs/tables", "docs"], cwd=root, text=True
    ).splitlines()
    names = [
        n
        for n in names
        if (n.startswith("outputs/tables/") and n.endswith(".csv"))
        or n
        in {
            "docs/final_conclusions.md",
            "docs/eda_findings.md",
            "docs/replication_findings.md",
            "docs/robustness_findings.md",
        }
    ]
    manifest = {
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "files": {},
        "frozen": {n: digest(root / n) for n in FROZEN},
    }
    for name in names:
        content = subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=root)
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest["files"][name] = digest(path)
    write_json(destination / "baseline.json", manifest)
    return manifest


def compare_baseline(root, baseline):
    import numpy as np
    import pandas as pd

    root, baseline = Path(root), Path(baseline)
    manifest = json.loads((baseline / "baseline.json").read_text(encoding="utf-8"))
    verify_hashes(baseline, manifest["files"])
    verify_hashes(root, manifest["frozen"])
    records = []
    for name, original_hash in manifest["files"].items():
        actual = local_path(root, name)
        require(actual.is_file(), f"Missing regenerated output: {name}")
        exact = digest(actual) == original_hash
        equal = exact
        if not exact and name.endswith(".csv"):
            old, new = pd.read_csv(baseline / name), pd.read_csv(actual)
            equal = list(old.columns) == list(new.columns) and old.shape == new.shape
            if equal:
                for col in old:
                    a, b = old[col], new[col]
                    if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
                        equal = bool(np.allclose(a, b, atol=1e-10, rtol=1e-10, equal_nan=True))
                    else:
                        equal = a.fillna("<NA>").equals(b.fillna("<NA>"))
                    if not equal:
                        break
        # The existing K3 seal requires exact bytes, including CSV provenance text.
        sealed = name.startswith("outputs/tables/final_") or name == "docs/final_conclusions.md"
        require(equal and (exact or not sealed), f"Reproduction mismatch: {name}")
        records.append(
            {
                "path": name,
                "byte_equal": exact,
                "numeric_equal": equal,
                "baseline_sha256": original_hash,
                "actual_sha256": digest(actual),
            }
        )
    return records


def validate_phase(root, phase, marker, expected, started, ended):
    record = json.loads(local_path(root, marker).read_text(encoding="utf-8"))
    if expected is None:
        require(record.get("checks_passed") is True, "Environment checks failed")
        prefix = Path(record["python_executable"]).resolve()
        require(
            prefix.is_relative_to((Path(root) / ".venv").resolve()), "Wrong notebook interpreter"
        )
        require(
            Path(record["package_path"]).resolve()
            == (Path(root) / "src/parentedu/__init__.py").resolve(),
            "Wrong editable package",
        )
    else:
        require(record.get("status") == expected, f"Phase {phase} is not ready")
    for field in ("created_at_utc", "completed_at_utc"):
        if field in record:
            require(
                datetime.fromisoformat(started)
                <= datetime.fromisoformat(record[field])
                <= datetime.fromisoformat(ended),
                f"Stale phase marker: {phase} {field}",
            )
    require("created_at_utc" in record, "Phase marker lacks creation time")
    for group in ("source_hashes", "input_hashes", "inputs", "protocol_inputs", "outputs"):
        verify_hashes(root, record.get(group, {}))
    return {
        "phase": phase,
        "started_at_utc": started,
        "ended_at_utc": ended,
        "marker_path": marker,
        "marker_sha256": digest(local_path(root, marker)),
        "output_hashes": {Path(n).as_posix(): h for n, h in record.get("outputs", {}).items()},
    }


def validate_full_run(root, record):
    require(
        record.get("schema_version") == 1
        and record.get("status") == "ready"
        and record.get("mode") == "full",
        "A ready full run is required",
    )
    require(
        record.get("comparison_status") == "PASS" and record.get("tests_status") == "PASS",
        "Full-run comparisons/tests not passed",
    )
    require(bool(record.get("run_id")), "Missing run identity")
    require(
        bool(record.get("source_hashes")) and bool(record.get("outputs")), "Missing run evidence"
    )
    for group in ("source_hashes", "input_hashes", "outputs"):
        verify_hashes(root, record[group])
    require(
        source_hashes(Path(root)) == record["source_hashes"], "Changed executable source inventory"
    )
    receipts = record.get("phase_receipts", [])
    require(
        [r["phase"] for r in receipts] == [p[0] for p in PHASES] + ["reports"],
        "Incomplete phase receipts",
    )
    for receipt in receipts:
        require(
            digest(local_path(root, receipt["marker_path"])) == receipt["marker_sha256"],
            "Changed phase receipt",
        )
        require(
            datetime.fromisoformat(record["created_at_utc"])
            <= datetime.fromisoformat(receipt["started_at_utc"])
            <= datetime.fromisoformat(receipt["ended_at_utc"])
            <= datetime.fromisoformat(record["completed_at_utc"]),
            "Receipt outside current run",
        )
        expected = (
            None
            if receipt["phase"] == "environment"
            else "prepared"
            if receipt["phase"] == "data"
            else "ready"
        )
        validate_phase(
            root,
            receipt["phase"],
            receipt["marker_path"],
            expected,
            receipt["started_at_utc"],
            receipt["ended_at_utc"],
        )
    verify_hashes(
        root,
        {
            "docs/K3_conclusions.json": record["k3"]["seal_sha256"],
            "docs/reviews/P07_conclusions_review.md": record["k3"]["review_sha256"],
        },
    )
    from parentedu.conclusions_workflow import check_audit_seal

    final = json.loads(
        (Path(root) / "outputs/logs/conclusions_run.json").read_text(encoding="utf-8")
    )
    require(
        final["audit_status"] == "PASS"
        and check_audit_seal(Path(root), final["outputs"]) == "PASS",
        "K3 not passed",
    )
    return True


def command_step(command, root, logfile, timeout, env=None):
    Path(logfile).parent.mkdir(parents=True, exist_ok=True)
    with Path(logfile).open("w", encoding="utf-8") as stream:
        subprocess.run(
            command,
            cwd=root,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=timeout,
        )


def run_project(root=ROOT, baseline=None, analysis_only=False, timeout=600):
    root = Path(root).resolve()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    marker = root / "outputs/logs/full_run.json"
    run_dir = root / "outputs/logs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": 1,
        "run_id": run_id,
        "status": "running",
        "mode": "analysis-only" if analysis_only else "full",
        "created_at_utc": now(),
        "phase_receipts": [],
        "course_submission_status": "open",
    }
    write_json(marker, record)
    try:
        from parentedu.environment import check_environment

        check_environment()
        record["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        record["git_dirty_start"] = bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()
        )
        record["source_hashes"] = source_hashes(root)
        record["input_hashes"] = {n: digest(root / n) for n in FROZEN}
        record["k3"] = {
            "seal_sha256": digest(root / FROZEN[0]),
            "review_sha256": digest(root / FROZEN[1]),
        }
        baseline = Path(baseline) if baseline else root / "build/p09/baseline"
        if not (baseline / "baseline.json").exists():
            capture_baseline(root, baseline)
        record["baseline_manifest_sha256"] = digest(baseline / "baseline.json")
        env = os.environ.copy()
        env["JUPYTER_PATH"] = str(root / ".venv/share/jupyter")
        env["PYTHONUTF8"] = "1"
        executed = root / "outputs/executed" / run_id
        executed.mkdir(parents=True, exist_ok=True)
        command_step(
            [
                sys.executable,
                "-m",
                "ipykernel",
                "install",
                "--prefix",
                str(root / ".venv"),
                "--name",
                "parentedu-replication",
            ],
            root,
            run_dir / "kernel.log",
            60,
            env,
        )
        for phase, notebook, logname, expected in PHASES:
            record["current_step"] = phase
            write_json(marker, record)
            start = now()
            target = executed / notebook.replace(".ipynb", ".executed.ipynb")
            command_step(
                [
                    sys.executable,
                    str(root / "scripts/execute_notebook.py"),
                    str(root / "notebooks" / notebook),
                    str(target),
                ],
                root,
                run_dir / f"{phase}.log",
                timeout,
                env,
            )
            receipt = validate_phase(root, phase, f"outputs/logs/{logname}", expected, start, now())
            receipt["executed_notebook"] = target.relative_to(root).as_posix()
            receipt["executed_sha256"] = digest(target)
            record["phase_receipts"].append(receipt)
        if not analysis_only:
            record["current_step"] = "reports"
            write_json(marker, record)
            start = now()
            command_step(
                [sys.executable, str(root / "scripts/build_reports.py")],
                root,
                run_dir / "reports.log",
                timeout,
                env,
            )
            record["phase_receipts"].append(
                validate_phase(
                    root, "reports", "outputs/logs/reports_run.json", "ready", start, now()
                )
            )
        # Tests reading report_values/content_map need full generated outputs first.
        record["current_step"] = "checks"
        write_json(marker, record)
        for name, cmd in (
            ("protocol", [sys.executable, "scripts/validate_protocol.py"]),
            ("ruff", [sys.executable, "-m", "ruff", "check", "src", "scripts", "tests"]),
            ("lock", ["uv", "lock", "--check"]),
            ("pytest", [sys.executable, "-m", "pytest", "-q"]),
        ):
            command_step(cmd, root, run_dir / f"{name}.log", timeout, env)
        record["tests_status"] = "PASS"
        comparisons = compare_baseline(root, baseline)
        comparison_path = run_dir / "comparison.json"
        write_json(
            comparison_path, {"status": "PASS", "atol": 1e-10, "rtol": 1e-10, "files": comparisons}
        )
        record["comparison_status"] = "PASS"
        record["outputs"] = {comparison_path.relative_to(root).as_posix(): digest(comparison_path)}
        for receipt in record["phase_receipts"]:
            record["outputs"].update(receipt["output_hashes"])
            if "executed_notebook" in receipt:
                record["outputs"][receipt["executed_notebook"]] = receipt["executed_sha256"]
        for p in run_dir.glob("*.log"):
            record["outputs"][p.relative_to(root).as_posix()] = digest(p)
        raw = json.loads((root / "outputs/logs/data_run.json").read_text(encoding="utf-8"))
        record["acquisition"] = {
            "cache_hit": raw["cache_hit"],
            "acquired_at_utc": raw["acquired_at_utc"],
            "provenance_sha256": raw["provenance_sha256"],
        }
        record["status"] = "analysis_ready" if analysis_only else "ready"
        record["completed_at_utc"] = now()
        record["git_dirty_end"] = bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()
        )
        verify_hashes(root, record["source_hashes"])
        if not analysis_only:
            validate_full_run(root, record)
        write_json(marker, record)
        write_json(run_dir / "full_run.json", record)
        return record
    except BaseException as error:
        record.update(
            status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
            completed_at_utc=now(),
            error_type=type(error).__name__,
            error=str(error),
        )
        write_json(marker, record)
        write_json(run_dir / "full_run.json", record)
        raise
