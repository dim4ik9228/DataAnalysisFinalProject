"""A failed P03 invocation must never leave a current ready marker."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from parentedu import data_workflow as workflow
from parentedu.data import DataValidationError


def options(tmp_path: Path) -> dict:
    return {
        "raw_dir": tmp_path / "raw",
        "processed_dir": tmp_path / "processed",
        "tables_dir": tmp_path / "tables",
        "docs_dir": tmp_path / "docs",
        "metadata_path": tmp_path / "logs/data_run.json",
        "provenance_path": tmp_path / "docs/pinned.json",
    }


def test_input_preflight_failure_invalidates_previous_ready_marker(tmp_path, monkeypatch):
    opts = options(tmp_path)
    opts["metadata_path"].parent.mkdir(parents=True)
    opts["metadata_path"].write_text('{"status":"prepared"}', encoding="utf-8")
    acquire = Mock(side_effect=AssertionError("Network acquisition should not be reached"))
    monkeypatch.setattr(workflow, "acquire_data", acquire)

    def missing_input(_path):
        raise FileNotFoundError("Missing schema input")

    monkeypatch.setattr(workflow, "_digest", missing_input)
    with pytest.raises(FileNotFoundError, match="Missing schema"):
        workflow.run_data_preparation(**opts)
    metadata = json.loads(opts["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["error_type"] == "FileNotFoundError"
    acquire.assert_not_called()
    assert not list(opts["processed_dir"].glob("*.csv"))


def test_validation_failure_records_issues_but_does_not_export_samples(tmp_path, monkeypatch):
    opts = options(tmp_path)
    issue = {
        "subject": "mat",
        "source_row": 2,
        "column": "Medu",
        "issue_type": "domain",
        "detail": "Invalid synthetic value",
    }
    monkeypatch.setattr(workflow, "acquire_data", Mock(side_effect=DataValidationError([issue])))
    export = Mock()
    monkeypatch.setattr(workflow, "export_samples", export)
    with pytest.raises(DataValidationError):
        workflow.run_data_preparation(**opts)
    metadata = json.loads(opts["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    local = opts["metadata_path"].with_name("data_validation_issues.json")
    assert json.loads(local.read_text(encoding="utf-8"))["issues"] == [issue]
    summary = (opts["tables_dir"] / "data_quality.csv").read_text(encoding="utf-8")
    assert "failed" in summary and "domain" in summary
    assert "source_row" not in summary  # Row-level diagnostics stay local.
    export.assert_not_called()
    assert not list(opts["processed_dir"].glob("*.csv"))
