"""Synthesis invariants and token-level evidence provenance."""

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from parentedu.conclusions import build_conclusion_tables, format_value

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def inputs(tmp_path):
    tables = tmp_path / "outputs/tables"
    shutil.copytree(ROOT / "outputs/tables", tables)
    (tmp_path / "docs/evidence/literature_followup").mkdir(parents=True)
    for name in ("replication_protocol.md", "literature.csv"):
        shutil.copy(ROOT / "docs" / name, tmp_path / "docs" / name)
    (tmp_path / "docs/evidence/literature_followup/summary.json").write_text(
        json.dumps(
            {
                "status": "unresolved",
                "verified_direct_count": 0,
                "required_min": 3,
                "search_scope": "fixture bounded search",
            }
        ),
        encoding="utf-8",
    )
    return tables, tmp_path


def test_six_hypotheses_and_frozen_inference(inputs):
    tables, root = inputs
    result = build_conclusion_tables(tables, root)
    hypotheses = result["hypotheses"]
    assert len(hypotheses) == 6
    assert set(hypotheses.family) == {"H1", "H2", "H3"}
    h3 = hypotheses[hypotheses.family == "H3"]
    assert set(h3.status) == {"descriptive_decrease"}
    assert h3.p_delta.isna().all()
    assert h3.p_value.isna().all() and h3.p_holm.isna().all()
    source = pd.read_csv(tables / "replication_hypotheses.csv", dtype=str)
    for row in source.itertuples():
        target = hypotheses[
            (hypotheses.subject == row.subject) & (hypotheses.family == row.family)
        ].iloc[0]
        assert target.p_value == row.p_value and target.p_holm == row.p_holm
        assert target.status == row.verdict
    verdicts = result["verdicts"]
    assert len(verdicts) == 9
    assert set(verdicts.inference_status) == {"not_identified"}
    assert verdicts.loc[verdicts.model_id == "M10", "numeric_status"].item() == "partial_match"


def test_denominator_units_and_refusals(inputs):
    result = build_conclusion_tables(*inputs)
    rows = result["robustness"]
    assert len(rows) == 28
    selected = rows[rows.direction_denominator]
    assert len(selected) == 9 and (selected.estimate > 0).all()
    assert set(selected.variant) == {"R1", "R2", "R4", "R5"}
    refused = rows[rows.status == "not_estimable"]
    assert len(refused) == 2 and set(refused.nobs) == {46}
    assert refused.estimate.isna().all()
    ordinal = rows[rows.variant == "R3"]
    assert ordinal.delta_beta.isna().all()
    assert ordinal.unit.str.contains("per education level").all()


def test_every_claim_has_exact_raw_evidence(inputs):
    result = build_conclusion_tables(*inputs)
    evidence = result["claim_evidence"]
    assert set(result["claims"].claim_id) == set(evidence.claim_id)
    assert evidence.evidence_id.is_unique
    for row in evidence[evidence.source_kind == "csv"].itertuples():
        path = inputs[1] / row.source_table
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row.source_hash
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        for key, value in json.loads(row.row_key_json).items():
            frame = frame[frame[key] == value]
        assert len(frame) == 1
        assert frame.iloc[0][row.metric] == row.raw_value
    aggregate = evidence[
        (evidence.source_kind == "csv_aggregate") & (evidence.claim_id == "robustness_direction")
    ]
    assert set(aggregate.raw_value) == {"9"}
    assert aggregate.denominator_rule.str.contains("exclude baseline,R3,placebo,refusals").all()


@pytest.mark.parametrize(
    "table",
    [
        "replication_hypotheses",
        "replication_verdicts",
        "robustness_summary",
        "robustness_h3",
        "robustness_specifications",
    ],
)
@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_reject_incomplete_or_duplicate_keys(inputs, table, mutation):
    path = inputs[0] / f"{table}.csv"
    rows = pd.read_csv(path, keep_default_na=False)
    rows = rows.iloc[1:] if mutation == "missing" else pd.concat([rows, rows.iloc[:1]])
    rows.to_csv(path, index=False)
    with pytest.raises(ValueError):
        build_conclusion_tables(*inputs)


@pytest.mark.parametrize(
    "table,column",
    [
        ("robustness_h3", "beta_base"),
        ("replication_coefficients", "estimate"),
        ("robustness_baseline_check", "actual"),
    ],
)
def test_cross_table_conflicts(inputs, table, column):
    path = inputs[0] / f"{table}.csv"
    frame = pd.read_csv(path, keep_default_na=False)
    index = (
        frame.index[(frame.model_id == "M4") & (frame.term == "Medu_4")][0]
        if table == "replication_coefficients"
        else 0
    )
    frame.loc[index, column] = float(frame.loc[index, column]) + 1
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="conflict"):
        build_conclusion_tables(*inputs)


def test_boolean_false_is_not_truthy(inputs):
    path = inputs[0] / "robustness_baseline_check.csv"
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame.loc[0, "matches"] = "False"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="failed"):
        build_conclusion_tables(*inputs)


@pytest.mark.parametrize("value", ["0.000000000123456789", "1e-200", "0.0011384458680023099"])
def test_positive_small_p_never_zero(value):
    shown = format_value(value, "p_value")
    assert float(shown) > 0
    assert shown == f"{float(value):.6g}"


def test_protocol_interpretation_preserves_actual_source_excerpt(inputs):
    result = build_conclusion_tables(*inputs)
    proofs = result["claim_evidence"]
    for row in proofs[proofs.source_kind.eq("protocol_interpretation")].itertuples():
        source = (inputs[1] / row.source_table).read_text(encoding="utf-8")
        assert row.raw_value in source
        assert row.metric == "section_interpretation"
        assert json.loads(row.row_key_json)["section"] in source
    status = proofs[(proofs.claim_id == "numeric_replication") & (proofs.metric == "verdict")]
    assert status.raw_value.item() == "partial_match"
    author = proofs[(proofs.claim_id == "author_inference") & (proofs.metric == "original_method")]
    assert author.raw_value.item() == "not_identified"


def test_limitation_ids_resolve_to_real_registry_entries(inputs):
    registry = build_conclusion_tables(*inputs)["claims"]
    keys = set(registry.claim_id)
    for value in registry.limitation_ids:
        assert set(value.split(";")) <= keys
