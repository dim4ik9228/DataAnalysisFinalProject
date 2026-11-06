"""P06 status/integrity protection before model fitting."""

import json
import tomllib
from unittest.mock import Mock

import pandas as pd
import pytest

import parentedu.robustness_workflow as workflow
from parentedu.paths import ROOT


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    def put(name, text="fixture"):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    put("data/reference/table8_coefficients.csv")
    for names in workflow._p05_expected_paths(tmp_path).values():
        for name in names:
            put(name)
    for name in workflow.SOURCES:
        put(name)
    put("docs/K2_replication.md", "P05 виконано; можна планувати P06")
    put("docs/reviews/P05_replication_review.md", "PASS")
    record = {"status": "ready", "git_commit": "older-p05-commit"}
    for group, names in workflow._p05_expected_paths(tmp_path).items():
        record[group] = {name: workflow.digest(tmp_path / name) for name in names}
    put("outputs/logs/replication_run.json", json.dumps(record))
    config = tomllib.loads((ROOT / "configs/analysis.toml").read_text(encoding="utf-8"))
    read = Mock(return_value={"config": config, "layers": {"replication": {}, "validated": {}}})
    monkeypatch.setattr(workflow, "load_replication_inputs", read)
    monkeypatch.setattr(workflow, "check_environment", Mock(return_value={"checks_passed": True}))
    monkeypatch.setattr(
        workflow.subprocess,
        "check_output",
        lambda cmd, **kw: "test-head" if "rev-parse" in cmd else "",
    )
    return tmp_path, read


def test_p05_partial_match_is_not_a_technical_blocker(workspace):
    root, read = workspace
    result = workflow.load_robustness_inputs(root)
    assert result["p05_metadata"]["git_commit"] == "older-p05-commit"
    read.assert_called_once_with(root)


@pytest.mark.parametrize(
    "name",
    [
        "src/parentedu/models.py",
        "outputs/tables/replication_coefficients.csv",
        "data/processed/student_mat_replication.csv",
        "data/reference/table8_coefficients.csv",
        "configs/analysis.toml",
        "outputs/logs/data_run.json",
        "outputs/logs/eda_run.json",
    ],
)
def test_stale_p05_dependency_rejected_before_read(workspace, name):
    root, read = workspace
    p = root / name
    p.write_bytes(p.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Stale"):
        workflow.load_robustness_inputs(root)
    read.assert_not_called()


def test_missing_p05_output_rejected(workspace):
    root, read = workspace
    (root / "outputs/tables/replication_models.csv").unlink()
    with pytest.raises(FileNotFoundError):
        workflow.load_robustness_inputs(root)
    read.assert_not_called()


@pytest.mark.parametrize("status", ["failed", "running"])
def test_unready_p05_rejected(workspace, status):
    root, read = workspace
    p = root / "outputs/logs/replication_run.json"
    record = json.loads(p.read_text())
    record["status"] = status
    p.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="not ready"):
        workflow.load_robustness_inputs(root)
    read.assert_not_called()


def test_incomplete_hash_manifest_rejected(workspace):
    root, read = workspace
    p = root / "outputs/logs/replication_run.json"
    record = json.loads(p.read_text())
    record["outputs"].pop(next(iter(record["outputs"])))
    p.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Incomplete"):
        workflow.load_robustness_inputs(root)
    read.assert_not_called()


@pytest.mark.parametrize(
    "stage", ["environment", "preflight", "baseline", "fit", "export", "render", "findings"]
)
def test_failure_after_ready_is_failed_including_preflight(workspace, monkeypatch, stage):
    root, _ = workspace
    marker = root / "outputs/logs/robustness_run.json"
    marker.write_text('{"status":"ready"}')

    def fail(*args, **kwargs):
        assert json.loads(marker.read_text())["status"] == "running"
        raise RuntimeError(stage + " failed")

    built = {
        n: pd.DataFrame({"synthetic": [1]})
        for n in (*workflow.TABLES, "membership", "row_diagnostics", "noise")
    }
    built["specifications"] = pd.DataFrame({"model_status": ["available"] * 15 + ["not_estimable"]})
    for n in ("h3", "placebo"):
        built[n] = pd.DataFrame({"synthetic": [1, 2]})
    monkeypatch.setattr(workflow, "_baseline", Mock(return_value=pd.DataFrame({"matches": [True]})))
    monkeypatch.setattr(workflow, "_build", Mock(return_value=built))
    monkeypatch.setattr(
        workflow, "_render", Mock(return_value={str(i): root / f"{i}.png" for i in range(6)})
    )
    targets = {
        "environment": "check_environment",
        "preflight": "load_robustness_inputs",
        "baseline": "_baseline",
        "fit": "_build",
        "render": "_render",
        "findings": "write_robustness_findings",
    }
    if stage == "export":
        monkeypatch.setattr(pd.DataFrame, "to_csv", fail)
    else:
        monkeypatch.setattr(workflow, targets[stage], fail)
    with pytest.raises(RuntimeError, match=stage + " failed"):
        workflow.run_robustness(root)
    assert json.loads(marker.read_text())["status"] == "failed"


def test_baseline_mismatch_prevents_any_variant_fit(workspace, monkeypatch):
    root, _ = workspace
    marker = root / "outputs/logs/robustness_run.json"
    marker.write_text('{"status":"ready"}')
    monkeypatch.setattr(
        workflow, "_baseline", Mock(return_value=pd.DataFrame({"matches": [False]}))
    )
    fit = Mock(side_effect=AssertionError("No variants after baseline mismatch"))
    monkeypatch.setattr(workflow, "_build", fit)
    with pytest.raises(ValueError, match="Baseline differs"):
        workflow.run_robustness(root)
    fit.assert_not_called()
    assert json.loads(marker.read_text())["status"] == "failed"


@pytest.mark.parametrize("lower", ["P03", "P04"])
def test_failed_lower_phase_prevents_baseline(workspace, monkeypatch, lower):
    root, read = workspace
    read.side_effect = ValueError(lower + " is failed")
    fit = Mock(side_effect=AssertionError("No fit after failed phase"))
    monkeypatch.setattr(workflow, "_baseline", fit)
    marker = root / "outputs/logs/robustness_run.json"
    marker.write_text('{"status":"ready"}')
    with pytest.raises(ValueError, match=lower):
        workflow.run_robustness(root)
    assert json.loads(marker.read_text())["status"] == "failed"
    fit.assert_not_called()
