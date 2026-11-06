"""P04 must refuse stale inputs and invalidate a previous successful run."""

import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

from parentedu import eda_workflow as workflow
from parentedu.data import load_schema


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def workspace(tmp_path):
    for directory in (
        "configs",
        "docs",
        "src/parentedu",
        "notebooks",
        "data/processed",
        "outputs/logs",
    ):
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    schema_source = (workflow.ROOT / "configs/data_schema.toml").read_text(encoding="utf-8")
    schema_source = schema_source.replace("mat = 395, por = 649", "mat = 2, por = 2")
    (tmp_path / "configs/data_schema.toml").write_text(schema_source, encoding="utf-8")
    (tmp_path / "configs/analysis.toml").write_text(
        "[expected_sample]\nmat=2\npor=2\n", encoding="utf-8"
    )
    for name in ("docs/replication_protocol.md", "uv.lock", *workflow.P03_SOURCES):
        (tmp_path / name).write_text("synthetic source\n", encoding="utf-8")
    (tmp_path / "docs/data_provenance.json").write_text('{"synthetic":true}', encoding="utf-8")
    schema = load_schema(tmp_path / "configs/data_schema.toml")
    outputs = {}
    for subject in ("mat", "por"):
        record = {
            spec["name"]: spec["allowed"][0] if "allowed" in spec else spec["min"]
            for spec in schema["columns"]
        }
        frame = pd.DataFrame([record.copy(), record.copy()])
        frame["Medu"], frame["Fedu"], frame["G3"] = [1, 4], [1, 4], [0, 12]
        frame["subject"] = subject
        frame["source_file"] = f"student-{subject}.csv"
        frame["source_row"] = [1, 2]
        frame["record_id"] = [f"{subject}:000001", f"{subject}:000002"]
        for layer in ("validated", "replication"):
            path = tmp_path / f"data/processed/student_{subject}_{layer}.csv"
            frame.to_csv(path, index=False)
            outputs[str(path)] = sha(path)
    metadata = {
        "status": "prepared",
        "git_commit": "older-p03-head",
        "inputs": {name: sha(tmp_path / name) for name in workflow.P03_INPUTS},
        "source_hashes": {name: sha(tmp_path / name) for name in workflow.P03_SOURCES},
        "provenance_sha256": sha(tmp_path / "docs/data_provenance.json"),
        "outputs": outputs,
    }
    (tmp_path / "outputs/logs/data_run.json").write_text(json.dumps(metadata), encoding="utf-8")
    return tmp_path


def test_valid_inputs_allow_different_head_and_preserve_zero_grades(workspace):
    inputs = workflow.load_eda_inputs(workspace)
    assert inputs["p03_metadata"]["git_commit"] == "older-p03-head"
    assert inputs["layers"]["replication"]["mat"].G3.tolist() == [0, 12]


@pytest.mark.parametrize(
    "name",
    [
        "configs/analysis.toml",
        "configs/data_schema.toml",
        "src/parentedu/data.py",
        "data/processed/student_mat_replication.csv",
    ],
)
def test_stale_content_is_rejected_before_statistics(workspace, name, monkeypatch):
    path = workspace / name
    path.write_bytes(path.read_bytes() + b"changed")
    read = Mock(side_effect=AssertionError("Do not read stale processed content"))
    monkeypatch.setattr(workflow, "read_prepared_csv", read)
    with pytest.raises(ValueError, match="Stale|Changed"):
        workflow.load_eda_inputs(workspace)
    read.assert_not_called()


def test_failed_p03_status_is_rejected(workspace):
    path = workspace / "outputs/logs/data_run.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["status"] = "failed"
    path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="not prepared"):
        workflow.load_eda_inputs(workspace)


def test_failed_preflight_invalidates_ready_before_any_exports(workspace, monkeypatch):
    marker = workspace / "outputs/logs/eda_run.json"
    marker.write_text('{"status":"ready"}', encoding="utf-8")
    monkeypatch.setattr(workflow, "load_eda_inputs", Mock(side_effect=ValueError("stale input")))
    build = Mock()
    render = Mock()
    monkeypatch.setattr(workflow, "build_eda_tables", build)
    monkeypatch.setattr(workflow, "_render", render)
    with pytest.raises(ValueError, match="stale input"):
        workflow.run_eda(workspace)
    assert json.loads(marker.read_text(encoding="utf-8"))["status"] == "failed"
    build.assert_not_called()
    render.assert_not_called()
    assert not list(workspace.glob("outputs/tables/eda_*.csv"))


def test_failed_render_cannot_leave_previous_ready_marker(workspace, monkeypatch):
    marker = workspace / "outputs/logs/eda_run.json"
    marker.write_text('{"status":"ready"}', encoding="utf-8")
    for name in (
        "src/parentedu/eda.py",
        "src/parentedu/reporting.py",
        "src/parentedu/eda_workflow.py",
        "notebooks/02_eda.ipynb",
    ):
        (workspace / name).write_text("synthetic code", encoding="utf-8")
    tables = {name: pd.DataFrame({"synthetic": [1]}) for name in workflow.TABLE_NAMES}
    monkeypatch.setattr(workflow, "build_eda_tables", Mock(return_value=tables))
    monkeypatch.setattr(workflow, "_render", Mock(side_effect=RuntimeError("render failed")))
    with pytest.raises(RuntimeError, match="render failed"):
        workflow.run_eda(workspace)
    record = json.loads(marker.read_text(encoding="utf-8"))
    assert record["status"] == "failed" and record["error_type"] == "RuntimeError"
