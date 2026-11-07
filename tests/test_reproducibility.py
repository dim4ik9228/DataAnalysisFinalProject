"""Fresh phase evidence and fail-fast behavior, without fitting models."""

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from parentedu import reproducibility as r


def phase(tmp_path, when=None):
    when = when or datetime.now(UTC)
    data = {
        "status": "prepared",
        "created_at_utc": when.isoformat(),
        "completed_at_utc": when.isoformat(),
        "outputs": {},
    }
    path = tmp_path / "outputs/logs/data_run.json"
    r.write_json(path, data)
    return when, path


def test_stale_ready_marker_is_rejected(tmp_path):
    when, _ = phase(tmp_path, datetime.now(UTC) - timedelta(days=1))
    start = (when + timedelta(hours=1)).isoformat()
    with pytest.raises(ValueError, match="Stale phase marker"):
        r.validate_phase(tmp_path, "data", "outputs/logs/data_run.json", "prepared", start, r.now())


def test_phase_output_corruption_rejected(tmp_path):
    when, marker = phase(tmp_path)
    output = tmp_path / "answer.csv"
    output.write_text("original")
    record = json.loads(marker.read_text())
    record["outputs"] = {"answer.csv": r.digest(output)}
    r.write_json(marker, record)
    output.write_text("changed")
    with pytest.raises(ValueError, match="Changed evidence"):
        r.validate_phase(
            tmp_path, "data", "outputs/logs/data_run.json", "prepared", when.isoformat(), r.now()
        )


def test_paths_cannot_escape_project(tmp_path):
    with pytest.raises(ValueError, match="escapes project"):
        r.local_path(tmp_path, "../secret")


def test_analysis_only_is_never_full_ready(tmp_path):
    with pytest.raises(ValueError, match="ready full run"):
        r.validate_full_run(
            tmp_path, {"schema_version": 1, "status": "analysis_ready", "mode": "analysis-only"}
        )


@pytest.mark.parametrize(
    "exception", [RuntimeError("notebook failed"), subprocess.TimeoutExpired("notebook", 1)]
)
def test_pipeline_stops_and_replaces_ready(tmp_path, monkeypatch, exception):
    from parentedu import environment

    monkeypatch.setattr(environment, "check_environment", dict)
    monkeypatch.setattr(r, "source_hashes", lambda root: {})
    monkeypatch.setattr(
        r.subprocess, "check_output", lambda args, **kw: "commit" if "rev-parse" in args else ""
    )
    for name in r.FROZEN:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("frozen")
    baseline = tmp_path / "baseline"
    r.write_json(
        baseline / "baseline.json", {"files": {"docs/final_conclusions.md": "test"}, "frozen": {}}
    )
    r.write_json(tmp_path / "outputs/logs/full_run.json", {"status": "ready"})
    calls = []

    def command(args, root, logfile, timeout, env=None):
        calls.append(str(logfile))
        if str(logfile).endswith("environment.log"):
            raise exception

    monkeypatch.setattr(r, "command_step", command)
    with pytest.raises(type(exception)):
        r.run_project(tmp_path, baseline=baseline)
    record = json.loads((tmp_path / "outputs/logs/full_run.json").read_text())
    assert record["status"] == "failed"
    assert record["current_step"] == "environment"
    assert len(calls) == 2 and not record["phase_receipts"]


def test_reproduction_float_contract_and_sealed_bytes(tmp_path):
    root, baseline = tmp_path / "new", tmp_path / "baseline"
    for directory in (root, baseline):
        (directory / "outputs/tables").mkdir(parents=True)
    name = "outputs/tables/result.csv"
    (baseline / name).write_text("value,status\n1.0,available\n")
    (root / name).write_text("value,status\n1.00000000001,available\n")
    manifest = {"files": {name: r.digest(baseline / name)}, "frozen": {}}
    r.write_json(baseline / "baseline.json", manifest)
    assert r.compare_baseline(root, baseline)[0]["numeric_equal"]
    (root / name).write_text("value,status\n1.1,available\n")
    with pytest.raises(ValueError, match="Reproduction mismatch"):
        r.compare_baseline(root, baseline)


def test_environment_receipt_rejects_other_kernel(tmp_path):
    marker = "outputs/logs/environment.json"
    r.write_json(
        tmp_path / marker,
        {
            "checks_passed": True,
            "python_executable": str(tmp_path / "other/python.exe"),
            "package_path": str(tmp_path / "src/parentedu/__init__.py"),
            "created_at_utc": r.now(),
        },
    )
    with pytest.raises(ValueError, match="Wrong notebook interpreter"):
        r.validate_phase(tmp_path, "environment", marker, None, r.now(), r.now())


def test_new_executable_invalidates_ready_run(tmp_path, monkeypatch):
    for name in ("source.py", "added.py", "result.csv"):
        (tmp_path / name).write_text("content")
    hashes = {"source.py": r.digest(tmp_path / "source.py")}
    monkeypatch.setattr(
        r, "source_hashes", lambda root: {**hashes, "added.py": r.digest(tmp_path / "added.py")}
    )
    record = {
        "schema_version": 1,
        "status": "ready",
        "mode": "full",
        "run_id": "run",
        "tests_status": "PASS",
        "comparison_status": "PASS",
        "source_hashes": hashes,
        "input_hashes": {},
        "outputs": {"result.csv": r.digest(tmp_path / "result.csv")},
    }
    with pytest.raises(ValueError, match="source inventory"):
        r.validate_full_run(tmp_path, record)


def test_analysis_comparison_does_not_require_report_exports(tmp_path):
    root, baseline = tmp_path / "new", tmp_path / "baseline"
    root.mkdir()
    (baseline / "outputs/tables").mkdir(parents=True)
    name = "outputs/tables/report_values.csv"
    (baseline / name).write_text("value\n1\n")
    r.write_json(
        baseline / "baseline.json", {"files": {name: r.digest(baseline / name)}, "frozen": {}}
    )
    assert r.compare_baseline(root, baseline, analysis_only=True) == []
    with pytest.raises(ValueError, match="Missing regenerated"):
        r.compare_baseline(root, baseline)


def test_committed_review_bytes_match_existing_seal():
    import hashlib

    root = Path(__file__).resolve().parents[1]
    seal = json.loads((root / "docs/K3_conclusions.json").read_text(encoding="utf-8"))
    content = subprocess.check_output(
        ["git", "show", "HEAD:docs/reviews/P07_conclusions_review.md"], cwd=root
    )
    assert hashlib.sha256(content).hexdigest() == seal["review_sha256"]
