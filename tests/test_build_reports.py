"""Report preflight fails closed; template substitutions preserve audited values."""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_reports", ROOT / "scripts/build_reports.py")
reports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reports)


def test_unknown_values_stop_generation():
    values = pd.DataFrame(
        [{"value_id": "beta", "display_report": "1.234", "display_slide": "1.23"}]
    )
    assert reports.substitute("{{v:beta}}", values, {}, {}, {}, "slides", []) == "1.23"
    with pytest.raises(ValueError, match="Missing report value"):
        reports.substitute("{{v:unknown}}", values, {}, {}, {}, "report", [])


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    groups = {
        "source_hashes": reports.P07_SOURCES,
        "input_hashes": ["input.csv"],
        "outputs": [f"output{i}.csv" for i in range(6)],
    }
    metadata = {"status": "ready", "audit_status": "PASS"}
    for group, names in groups.items():
        metadata[group] = {}
        for name in names:
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("verified", encoding="utf-8")
            metadata[group][name] = reports.digest(path)
    marker = tmp_path / "outputs/logs/conclusions_run.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(metadata), encoding="utf-8")
    monkeypatch.setattr(reports, "check_audit_seal", lambda *a: "PASS")
    return tmp_path, metadata


def test_stale_upstream_blocks_report(evidence):
    root, metadata = evidence
    assert reports.verify_readiness(root)["status"] == "ready"
    (root / next(iter(metadata["input_hashes"]))).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Stale P07 evidence"):
        reports.verify_readiness(root)


def test_invalid_audit_seal_blocks_report(evidence, monkeypatch):
    root, _ = evidence
    monkeypatch.setattr(reports, "check_audit_seal", lambda *a: "FAIL")
    with pytest.raises(ValueError, match="K3 research audit"):
        reports.verify_readiness(root)


def test_failure_replaces_previous_ready_marker(tmp_path, monkeypatch):
    marker = tmp_path / "outputs/logs/reports_run.json"
    reports.record(marker, {"status": "ready"})

    def reject(root):
        assert json.loads(marker.read_text())["status"] == "running"
        raise ValueError("stale K3")

    monkeypatch.setattr(reports, "verify_readiness", reject)
    with pytest.raises(ValueError, match="stale K3"):
        reports.build(tmp_path)
    result = json.loads(marker.read_text())
    assert result["status"] == "failed" and result["error_type"] == "ValueError"


def test_content_map_has_valid_claims_and_sources():
    mapping = pd.read_csv(ROOT / "reports/content_map.csv").fillna("")
    claims = set(pd.read_csv(ROOT / "outputs/tables/final_claims.csv").claim_id)
    values = pd.read_csv(ROOT / "outputs/tables/report_values.csv").set_index("value_id")
    assert mapping.query("artifact == 'report'").section_id.nunique() > 5
    for row in mapping.itertuples():
        if row.kind == "meta":
            continue
        assert row.claim_id and set(row.claim_id.split(";")) <= claims
        for source, expected in zip(
            row.source_table.split(";"), row.source_hash.split(";"), strict=True
        ):
            assert reports.digest(ROOT / source) == expected
        if row.kind == "v":
            assert values.loc[row.value_or_figure, "claim_id"] == row.claim_id
