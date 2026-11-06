"""Checks for presentation formatting, provenance and aggregate chart data."""

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from parentedu.presentation_reporting import (
    collect_report_values,
    create_report_figures,
    format_value,
)

ROOT = Path(__file__).resolve().parents[1]


def test_formatting_preserves_small_p_and_missing_values():
    assert format_value(1.23456) == "1.235"
    assert format_value(1.23456, decimals=2) == "1.23"
    assert format_value(1e-12, "p_value") == "1e-12"
    assert format_value(0, "p_value") != "0"
    assert format_value(float("nan")) == "—"
    assert format_value("") == "—"
    assert format_value("NA") == "—"
    assert format_value(390.0, "nobs") == "390"
    assert format_value("not_estimable") == "not_estimable"


def test_report_values_preserve_audited_sources():
    values = collect_report_values(ROOT).set_index("value_id")
    assert values.index.is_unique
    h1 = values.loc["H1_mat.estimate"]
    source = ROOT / h1.source_table
    assert h1.source_hash == hashlib.sha256(source.read_bytes()).hexdigest()
    key = json.loads(h1.row_key_json)
    data = pd.read_csv(source)
    for field, expected in key.items():
        data = data.loc[data[field] == expected]
    assert len(data) == 1
    assert float(h1.raw_value) == data.iloc[0][h1.metric]
    assert h1.display_report == "2.993"
    assert h1.display_slide == "2.99"
    assert float(values.loc["R2_mat.nobs", "raw_value"]) == 352
    assert float(values.loc["candidate.refused", "raw_value"]) == 1
    assert values.loc["literature.status", "raw_value"] == "unresolved"


def test_modified_source_rejected(tmp_path):
    # Synthetic source corruption is detected using the frozen evidence hash.
    target = tmp_path / "outputs/tables"
    target.mkdir(parents=True)
    for name in ["final_claim_evidence.csv", "final_claims.csv", "replication_verdicts.csv"]:
        shutil.copyfile(ROOT / "outputs/tables" / name, target / name)
    with (target / "replication_verdicts.csv").open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="Stale evidence"):
        collect_report_values(tmp_path)


def test_chart_ci_data_and_refusal_are_preserved(tmp_path):
    tables = tmp_path / "outputs/tables"
    tables.mkdir(parents=True)
    for name in [
        "final_hypotheses",
        "final_robustness",
        "robustness_placebo",
        "eda_category_counts",
    ]:
        shutil.copyfile(ROOT / f"outputs/tables/{name}.csv", tables / f"{name}.csv")
    assets = create_report_figures(tmp_path, tmp_path / "assets")
    assert set(assets) == {"h1", "h2", "robustness", "h3", "placebo", "education"}
    data = json.loads(assets["h1"]["json"].read_text(encoding="utf-8"))
    row = (
        pd.read_csv(tables / "final_hypotheses.csv")
        .query("family == 'H1' and subject == 'mat'")
        .iloc[0]
    )
    trace = data["data"][0]
    assert trace["x"][0] == row.estimate
    assert trace["error_x"]["array"][0] == pytest.approx(row.ci_high - row.estimate)
    assert trace["error_x"]["arrayminus"][0] == pytest.approx(row.estimate - row.ci_low)
    robust = json.loads(assets["robustness"]["json"].read_text(encoding="utf-8"))
    assert any(a["text"] == "Не оцінено" for a in robust["layout"]["annotations"])
    assert all(t["x"][0] is not None for t in robust["data"])
    html = assets["h1"]["html"].read_text(encoding="utf-8")
    assert "<html>" not in html
    assert "cdn.plot.ly" not in html
