"""Offline invariants for source acquisition and schema validation."""

import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from parentedu import data


def valid_frame() -> pd.DataFrame:
    schema = data.load_schema()
    record = {}
    for column in schema["columns"]:
        record[column["name"]] = column["allowed"][0] if "allowed" in column else column["min"]
    record["G3"] = 0
    return pd.DataFrame([record, record.copy()])


def zip_bytes(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def source_bundle() -> bytes:
    inner = zip_bytes({name: f"source-{name}".encode() for name in data.SOURCE_FILES})
    return zip_bytes({"student.zip": inner, ".student.zip_old": b"do not select old"})


def fake_download(monkeypatch, content: bytes):
    calls = []

    def download(url: str, target: Path) -> str:
        calls.append(url)
        target.write_bytes(content)
        return url

    monkeypatch.setattr(data, "_download", download)
    return calls


def test_read_preserves_zero_grades_duplicates_and_stable_record_ids(tmp_path):
    source = tmp_path / "student-mat.csv"
    valid_frame().to_csv(source, sep=";", index=False)
    actual, quality = data.read_student_csv(source, "mat")
    assert len(actual) == 2
    assert actual.G3.tolist() == [0, 0]
    assert actual.record_id.tolist() == ["mat:000001", "mat:000002"]
    assert actual.source_row.tolist() == [1, 2]
    assert actual.source_file.tolist() == [source.name, source.name]
    assert quality.loc[quality["check"].eq("exact_duplicate_excess"), "value"].item() == 1
    assert quality.loc[quality["check"].eq("zero_G3"), "value"].item() == 2
    assert str(actual.Medu.dtype) == "int64"


@pytest.mark.parametrize(
    ("column", "bad", "issue_type"),
    [
        ("Medu", "", "missing"),
        ("age", None, "missing"),
        ("Medu", "1.0", "type"),
        ("Medu", 5, "domain"),
        ("school", "unknown", "domain"),
        ("G3", -1, "domain"),
    ],
)
def test_invalid_values_fail_with_row_and_field(column, bad, issue_type):
    frame = valid_frame().astype(object)
    frame.loc[1, column] = bad
    with pytest.raises(data.DataValidationError) as caught:
        data.validate_frame(frame, subject="por")
    assert any(
        issue["subject"] == "por"
        and issue["source_row"] == 2
        and issue["column"] == column
        and issue["issue_type"] == issue_type
        for issue in caught.value.issues
    )
    # Validation never modifies the caller's input into a repaired table.
    assert frame.loc[1, column] is bad or frame.loc[1, column] == bad


def test_bad_header_and_wrong_width_fail_before_coercion(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("school;school\nGP;GP\n", encoding="utf-8")
    with pytest.raises(data.DataValidationError) as caught:
        data.read_student_csv(path, "mat")
    assert caught.value.issues[0]["issue_type"] == "header"
    frame = valid_frame()
    frame.to_csv(path, sep=";", index=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("one;two\n")
    with pytest.raises(data.DataValidationError) as caught:
        data.read_student_csv(path, "mat")
    assert any(issue["issue_type"] == "row_width" for issue in caught.value.issues)


def test_bootstrap_is_explicit(tmp_path, monkeypatch):
    calls = fake_download(monkeypatch, source_bundle())
    with pytest.raises(FileNotFoundError):
        data.acquire_data(tmp_path / "raw", tmp_path / "provenance.json")
    assert calls == []


def test_valid_cache_is_network_free_and_preserves_acquisition_date(tmp_path, monkeypatch):
    calls = fake_download(monkeypatch, source_bundle())
    raw, pin = tmp_path / "raw", tmp_path / "provenance.json"
    first = data.acquire_data(raw, pin, allow_bootstrap=True)
    tracked_bytes = pin.read_bytes()
    local_bytes = (raw / "data_manifest.json").read_bytes()
    second = data.acquire_data(raw, pin)
    assert len(calls) == 1
    assert not first["cache_hit"] and second["cache_hit"]
    assert second["retrieved_at_utc"] == first["retrieved_at_utc"]
    assert pin.read_bytes() == tracked_bytes
    assert (raw / "data_manifest.json").read_bytes() == local_bytes
    assert set(first["files"]) == set(data.CACHE_FILES)
    assert (raw / "student-mat.csv").read_bytes() == b"source-student-mat.csv"


def test_corrupt_cache_fails_without_network_or_overwriting_pin(tmp_path, monkeypatch):
    calls = fake_download(monkeypatch, source_bundle())
    raw, pin = tmp_path / "raw", tmp_path / "provenance.json"
    data.acquire_data(raw, pin, allow_bootstrap=True)
    tracked_bytes = pin.read_bytes()
    (raw / "student-mat.csv").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="mismatch"):
        data.acquire_data(raw, pin)
    assert len(calls) == 1
    assert pin.read_bytes() == tracked_bytes
    assert (raw / "student-mat.csv").read_bytes() == b"corrupt"


def test_clean_checkout_download_must_match_tracked_hashes(tmp_path, monkeypatch):
    content = source_bundle()
    calls = fake_download(monkeypatch, content)
    pin = tmp_path / "provenance.json"
    data.acquire_data(tmp_path / "first", pin, allow_bootstrap=True)
    tracked_bytes = pin.read_bytes()
    result = data.acquire_data(tmp_path / "second", pin)
    assert not result["cache_hit"] and len(calls) == 2
    assert pin.read_bytes() == tracked_bytes
    fake_download(monkeypatch, source_bundle() + b"changed archive bytes")
    with pytest.raises(ValueError, match="mismatch"):
        data.acquire_data(tmp_path / "wrong", pin)
    assert pin.read_bytes() == tracked_bytes
    assert list((tmp_path / "wrong").iterdir()) == []


def test_incomplete_cache_is_not_repaired_silently(tmp_path, monkeypatch):
    calls = fake_download(monkeypatch, source_bundle())
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "student-mat.csv").write_bytes(b"partial")
    with pytest.raises(ValueError, match="Incomplete"):
        data.acquire_data(raw, tmp_path / "pin.json", allow_bootstrap=True)
    assert calls == []
    assert (raw / "student-mat.csv").read_bytes() == b"partial"


@pytest.mark.parametrize(
    "content", [b"<html>error</html>", zip_bytes({".student.zip_old": b"old"})]
)
def test_invalid_download_never_promoted(tmp_path, monkeypatch, content):
    fake_download(monkeypatch, content)
    raw, pin = tmp_path / "raw", tmp_path / "pin.json"
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        data.acquire_data(raw, pin, allow_bootstrap=True)
    assert not pin.exists()
    assert list(raw.iterdir()) == []


def test_interrupted_download_cleans_stage_and_preserves_pin(tmp_path, monkeypatch):
    fake_download(monkeypatch, source_bundle())
    pin = tmp_path / "pin.json"
    data.acquire_data(tmp_path / "first", pin, allow_bootstrap=True)
    tracked_bytes = pin.read_bytes()

    def interrupt(url, target):
        target.write_bytes(b"partial")
        raise OSError("connection interrupted")

    monkeypatch.setattr(data, "_download", interrupt)
    with pytest.raises(OSError, match="interrupted"):
        data.acquire_data(tmp_path / "second", pin)
    assert pin.read_bytes() == tracked_bytes
    assert list((tmp_path / "second").iterdir()) == []


@pytest.mark.parametrize("mode", ["invalid_utf8", "broken_quote", "header_only"])
def test_unreadable_or_empty_source_has_structured_diagnostics(tmp_path, mode):
    path = tmp_path / "bad.csv"
    if mode == "invalid_utf8":
        path.write_bytes(b"\xff\xfe")
    elif mode == "broken_quote":
        path.write_text('"unclosed', encoding="utf-8")
    else:
        valid_frame().iloc[:0].to_csv(path, sep=";", index=False)
    with pytest.raises(data.DataValidationError) as caught:
        data.read_student_csv(path, "mat")
    expected_kind = "empty_data" if mode == "header_only" else "parse"
    assert any(issue["issue_type"] == expected_kind for issue in caught.value.issues)
