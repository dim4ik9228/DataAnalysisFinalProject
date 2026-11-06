"""Protect P05 preflight and failure markers independently of numerical fitting."""

import json
import tomllib
from unittest.mock import Mock

import pandas as pd
import pytest

import parentedu.replication as comparison
import parentedu.replication_workflow as workflow
from parentedu.paths import ROOT


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    def put(name, content="fixture"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    for name in (*workflow.P03_INPUTS, *workflow.P04_SOURCES, *workflow.P05_SOURCES):
        put(name)
    put("docs/K1_readiness.md", "технічну контрольну точку пройдено")
    put("docs/reviews/P04_eda_review.md", "PASS")
    put("outputs/logs/data_run.json", '{"status":"prepared"}')
    put("data/reference/sources/manifest.json", "[]")
    paths = [
        put(f"data/processed/student_{s}_{layer}.csv")
        for s in ("mat", "por")
        for layer in ("validated", "replication")
    ]
    outputs = [put(f"outputs/tables/evidence_{i}.csv") for i in range(19)]
    record = {
        "status": "ready",
        "git_commit": "older-p04-head",
        "p03_data_run_sha256": workflow.digest(tmp_path / "outputs/logs/data_run.json"),
        "source_hashes": {n: workflow.digest(tmp_path / n) for n in workflow.P04_SOURCES},
        "protocol_inputs": {n: workflow.digest(tmp_path / n) for n in workflow.P03_INPUTS},
        "inputs": {str(p.relative_to(tmp_path)): workflow.digest(p) for p in paths},
        "outputs": {str(p.relative_to(tmp_path)): workflow.digest(p) for p in outputs},
    }
    put("outputs/logs/eda_run.json", json.dumps(record))
    config = tomllib.loads((ROOT / "configs/analysis.toml").read_text(encoding="utf-8"))
    read = Mock(
        return_value={
            "config": config,
            "layers": {"replication": {"mat": pd.DataFrame(), "por": pd.DataFrame()}},
        }
    )
    monkeypatch.setattr(workflow, "load_eda_inputs", read)
    monkeypatch.setattr(comparison, "validate_references", Mock(return_value={}))
    monkeypatch.setattr(workflow, "check_environment", Mock(return_value={"checks_passed": True}))
    monkeypatch.setattr(
        workflow.subprocess,
        "check_output",
        lambda command, **kwargs: "fixture-head" if "rev-parse" in command else "",
    )
    return tmp_path, read


def test_current_hashes_allow_older_p04_commit(workspace):
    root, read = workspace
    result = workflow.load_replication_inputs(root)
    assert result["p04_metadata"]["git_commit"] == "older-p04-head"
    read.assert_called_once_with(root)


@pytest.mark.parametrize(
    "name",
    [
        "src/parentedu/eda.py",
        "configs/analysis.toml",
        "outputs/tables/evidence_0.csv",
        "data/processed/student_por_replication.csv",
        "outputs/logs/data_run.json",
    ],
)
def test_stale_p04_content_stops_before_data_or_fit(workspace, name):
    root, read = workspace
    path = root / name
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Stale"):
        workflow.load_replication_inputs(root)
    read.assert_not_called()


def test_missing_p04_evidence_is_not_ignored(workspace):
    root, read = workspace
    (root / "outputs/tables/evidence_0.csv").unlink()
    with pytest.raises(FileNotFoundError):
        workflow.load_replication_inputs(root)
    read.assert_not_called()


@pytest.mark.parametrize("status", ["failed", "running"])
def test_unready_p04_rejected(workspace, status):
    root, read = workspace
    path = root / "outputs/logs/eda_run.json"
    record = json.loads(path.read_text())
    record["status"] = status
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="not ready"):
        workflow.load_replication_inputs(root)
    read.assert_not_called()


@pytest.mark.parametrize(
    "stage", ["environment", "preflight", "fit", "compare", "export", "render", "findings"]
)
def test_any_failure_invalidates_previous_ready(workspace, monkeypatch, stage):
    root, _ = workspace
    marker = root / "outputs/logs/replication_run.json"
    marker.write_text('{"status":"ready"}')

    def fail(*args, **kwargs):
        assert json.loads(marker.read_text())["status"] == "running"
        raise RuntimeError(f"{stage} failed")

    built = {
        name: pd.DataFrame({"synthetic": [1]})
        for name in (
            "coefficients",
            "models",
            "diagnostics",
            "vif",
            "hypotheses",
            "row_diagnostics",
        )
    }
    monkeypatch.setattr(workflow, "_build", Mock(return_value=built))
    monkeypatch.setattr(
        workflow,
        "_compare",
        Mock(
            return_value={
                n: pd.DataFrame({"synthetic": [1]})
                for n in ("comparison", "se_comparison", "verdicts")
            }
        ),
    )
    monkeypatch.setattr(
        workflow, "_render", Mock(return_value={str(i): root / f"{i}.png" for i in range(8)})
    )
    target = {
        "environment": "check_environment",
        "preflight": "load_replication_inputs",
        "fit": "_build",
        "compare": "_compare",
        "render": "_render",
        "findings": "write_replication_findings",
    }
    if stage == "export":
        monkeypatch.setattr(pd.DataFrame, "to_csv", fail)
    else:
        monkeypatch.setattr(workflow, target[stage], fail)
    with pytest.raises(RuntimeError, match=f"{stage} failed"):
        workflow.run_replication(root)
    record = json.loads(marker.read_text())
    assert record["status"] == "failed"
    assert record["error_type"] == "RuntimeError"


@pytest.mark.parametrize("issue", ["failed_p03", "stale", "missing", "failed_p04"])
def test_real_preflight_failure_after_ready_never_calls_fit(workspace, monkeypatch, issue):
    root, read = workspace
    marker = root / "outputs/logs/replication_run.json"
    marker.write_text('{"status":"ready"}')
    if issue == "failed_p03":
        read.side_effect = ValueError("P03 data status is not prepared")
    elif issue == "stale":
        (root / "data/processed/student_mat_replication.csv").write_text("changed")
    elif issue == "missing":
        (root / "data/processed/student_mat_replication.csv").unlink()
    else:
        path = root / "outputs/logs/eda_run.json"
        record = json.loads(path.read_text())
        record["status"] = "failed"
        path.write_text(json.dumps(record))
    fit = Mock(side_effect=AssertionError("No fitting after failed preflight"))
    monkeypatch.setattr(workflow, "_build", fit)
    with pytest.raises((ValueError, FileNotFoundError)):
        workflow.run_replication(root)
    assert json.loads(marker.read_text())["status"] == "failed"
    fit.assert_not_called()
