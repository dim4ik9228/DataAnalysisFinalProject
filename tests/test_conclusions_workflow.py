"""P07 protects source evidence and ready state without any model fits."""

import json
from unittest.mock import Mock

import pandas as pd
import pytest

import parentedu.conclusions_workflow as workflow


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    def put(name, text="fixture"):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    put("data/reference/table8_coefficients.csv")
    for names in workflow._p05_expected_paths(tmp_path).values():
        for n in names:
            put(n)
    put("outputs/logs/data_run.json", '{"status":"prepared"}')
    put("outputs/logs/eda_run.json", '{"status":"ready"}')
    record = {"status": "ready", "git_commit": "older-p05-head"}
    for group, names in workflow._p05_expected_paths(tmp_path).items():
        record[group] = {n: workflow.digest(tmp_path / n) for n in names}
    put("outputs/logs/replication_run.json", json.dumps(record))
    for names in workflow._p06_expected_paths(tmp_path).values():
        for n in names:
            if not (tmp_path / n).exists():
                put(n)
    put("docs/reviews/P05_replication_review.md", "PASS")
    # Re-pin evidence after fixture reviewer text, just as a successful P05 run would.
    record["input_hashes"] = {
        n: workflow.digest(tmp_path / n)
        for n in workflow._p05_expected_paths(tmp_path)["input_hashes"]
    }
    put("outputs/logs/replication_run.json", json.dumps(record))
    second = {"status": "ready", "git_commit": "older-p06-head"}
    for group, names in workflow._p06_expected_paths(tmp_path).items():
        second[group] = {n: workflow.digest(tmp_path / n) for n in names}
    put("outputs/logs/robustness_run.json", json.dumps(second))
    for n in workflow.SOURCES:
        put(n)
    put("docs/reviews/P06_robustness_review.md", "PASS")
    for n in (
        "docs/P06_handoff.md",
        "docs/literature.csv",
        "docs/literature_review.md",
        "docs/course_requirements.md",
        "docs/literature_followup.csv",
        "docs/literature_followup.md",
    ):
        put(n)
    summary = {"status": "unresolved", "verified_direct_count": 1, "required_min": 3}
    put("docs/evidence/literature_followup/summary.json", json.dumps(summary))
    put("docs/evidence/literature_followup/note.txt", "primary source note")
    entries = [
        {"file": n, "sha256": workflow.digest(tmp_path / "docs/evidence/literature_followup" / n)}
        for n in ("summary.json", "note.txt")
    ]
    put("docs/evidence/literature_followup/manifest.json", json.dumps(entries))
    monkeypatch.setattr(workflow, "check_environment", Mock(return_value={"checks_passed": True}))
    monkeypatch.setattr(
        workflow.subprocess,
        "check_output",
        lambda cmd, **kw: "test-head" if "rev-parse" in cmd else "",
    )
    return tmp_path


def test_upstream_older_commits_and_open_bibliography_are_valid(workspace):
    result = workflow.load_conclusion_inputs(workspace)
    assert result["p05"]["git_commit"] == "older-p05-head"
    assert result["literature"]["status"] == "unresolved"
    assert "docs/K3_conclusions.md" not in result["input_hashes"]


@pytest.mark.parametrize(
    "name",
    [
        "src/parentedu/models.py",
        "src/parentedu/robustness.py",
        "outputs/tables/replication_hypotheses.csv",
        "outputs/tables/robustness_summary.csv",
        "data/processed/robustness_noise.csv",
        "configs/analysis.toml",
        "docs/evidence/literature_followup/note.txt",
    ],
)
def test_stale_evidence_stops_before_synthesis(workspace, monkeypatch, name):
    p = workspace / name
    p.write_bytes(p.read_bytes() + b"changed")
    build = Mock(side_effect=AssertionError("Do not synthesize stale evidence"))
    monkeypatch.setattr(workflow, "_build", build)
    marker = workspace / "outputs/logs/conclusions_run.json"
    marker.write_text('{"status":"ready"}')
    with pytest.raises(ValueError, match="Stale|Changed"):
        workflow.run_conclusions(workspace)
    build.assert_not_called()
    assert json.loads(marker.read_text())["status"] == "failed"


@pytest.mark.parametrize("name", ["replication", "robustness"])
@pytest.mark.parametrize("state", ["failed", "running"])
def test_unready_phase_rejected(workspace, name, state):
    p = workspace / f"outputs/logs/{name}_run.json"
    record = json.loads(p.read_text())
    record["status"] = state
    p.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="not ready|Stale"):
        workflow.load_conclusion_inputs(workspace)


def test_missing_dependency_does_not_fall_back_to_handoff(workspace):
    (workspace / "outputs/tables/robustness_h3.csv").unlink()
    with pytest.raises(FileNotFoundError):
        workflow.load_conclusion_inputs(workspace)


@pytest.mark.parametrize("stage", ["environment", "preflight", "synthesis", "export", "text"])
def test_failure_after_ready_cannot_leave_ready(workspace, monkeypatch, stage):
    marker = workspace / "outputs/logs/conclusions_run.json"
    marker.write_text('{"status":"ready"}')

    def fail(*args, **kwargs):
        assert json.loads(marker.read_text())["status"] == "running"
        raise ValueError(stage + " failed")

    frames = {n: pd.DataFrame({"synthetic": [1]}) for n in workflow.FINAL_TABLES}
    monkeypatch.setattr(workflow, "_build", Mock(return_value=frames))
    targets = {
        "environment": "check_environment",
        "preflight": "load_conclusion_inputs",
        "synthesis": "_build",
        "text": "write_conclusions",
    }
    if stage == "export":
        monkeypatch.setattr(pd.DataFrame, "to_csv", fail)
    else:
        monkeypatch.setattr(workflow, targets[stage], fail)
    with pytest.raises(ValueError, match=stage + " failed"):
        workflow.run_conclusions(workspace)
    assert json.loads(marker.read_text())["status"] == "failed"


def test_every_rendered_claim_needs_evidence(tmp_path):
    pd.DataFrame({"claim_id": ["H1_mat"], "text_uk": ["Не вигадувати доказів"]}).to_csv(
        tmp_path / "final_claims.csv", index=False
    )
    pd.DataFrame(columns=["claim_id", "source_table"]).to_csv(
        tmp_path / "final_claim_evidence.csv", index=False
    )
    with pytest.raises(ValueError, match="coverage mismatch"):
        workflow.write_conclusions(tmp_path, tmp_path / "text.md")


def test_optional_seal_does_not_make_k3_a_preflight_dependency(tmp_path):
    assert (
        workflow.check_audit_seal(tmp_path, {"outputs/tables/final_claims.csv": "hash"})
        == "not_recorded"
    )


@pytest.mark.parametrize("change", ["none", "output", "review"])
def test_audited_outputs_and_review_must_match_seal(tmp_path, change):
    review = tmp_path / "docs/reviews/P07_conclusions_review.md"
    review.parent.mkdir(parents=True)
    review.write_text("PASS")
    output = {"outputs/tables/final_claims.csv": "hash"}
    seal = {
        "research_verdict": "PASS",
        "audited_outputs": output,
        "review_sha256": workflow.digest(review),
    }
    (tmp_path / "docs/K3_conclusions.json").write_text(json.dumps(seal))
    if change == "output":
        output = {"outputs/tables/final_claims.csv": "changed"}
    if change == "review":
        review.write_text("changed")
    if change == "none":
        assert workflow.check_audit_seal(tmp_path, output) == "PASS"
    else:
        with pytest.raises(ValueError, match="K3 audit is stale"):
            workflow.check_audit_seal(tmp_path, output)
