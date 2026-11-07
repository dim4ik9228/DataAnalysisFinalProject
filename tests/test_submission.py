"""Content and security checks for submission archives."""

import hashlib
import json
import zipfile

import pytest

from parentedu.submission import MANIFEST, _allowed, _notebook, _path, verify_package


def archive(tmp_path, entries=None, rows=None):
    entries = entries or {"README.md": b"reproduce"}
    if rows is None:
        rows = [
            {"path": n, "size": len(d), "sha256": hashlib.sha256(d).hexdigest()}
            for n, d in entries.items()
        ]
    result = tmp_path / "candidate.zip"
    with zipfile.ZipFile(result, "w") as z:
        for name, content in entries.items():
            z.writestr(name, content)
        z.writestr(MANIFEST, json.dumps({"files": rows}))
    return result


def test_valid_archive_unpacked_and_verified(tmp_path):
    assert verify_package(archive(tmp_path))["files"][0]["size"] == 9


@pytest.mark.parametrize(
    "name",
    [
        "../README.md",
        "/README.md",
        "C:/secret",
        "a\\b",
        "src/.env",
        "tools/node_modules/a.js",
        "data/raw/a.csv",
    ],
)
def test_unsafe_paths(name):
    with pytest.raises(ValueError):
        _path(name)


def test_allowlist_excludes_binaries_and_raw():
    assert not _allowed("tools/reporting/chrome.exe")
    assert _allowed("tools/reporting/package-lock.json")
    assert not _allowed("reports/qa/check.png")


def test_changed_payload_rejected(tmp_path):
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_package(
            archive(tmp_path, rows=[{"path": "README.md", "size": 9, "sha256": "0" * 64}])
        )


def test_missing_payload_rejected(tmp_path):
    with pytest.raises(ValueError, match="enumerate exactly"):
        verify_package(archive(tmp_path, rows=[]))


def test_duplicate_payload_rejected(tmp_path):
    path = archive(tmp_path)
    with zipfile.ZipFile(path, "a") as z:
        z.writestr("readme.md", "case collision")
    with pytest.raises(ValueError, match="Duplicate"):
        verify_package(path)


def test_unlisted_private_file_rejected(tmp_path):
    with pytest.raises(ValueError, match="Forbidden"):
        verify_package(archive(tmp_path, {".env": b"secret"}))


def test_sanitize_notebook_preserves_source_and_values():
    source = "print(42)"
    book = {
        "metadata": {"path": "C:/Users/private/project"},
        "cells": [
            {
                "source": source,
                "metadata": {"execution": "local"},
                "outputs": [{"output_type": "stream", "text": ["C:/Users/private/project 42\n"]}],
            }
        ],
    }
    result = json.loads(_notebook(json.dumps(book).encode()))
    assert result["cells"][0]["source"] == source
    assert result["cells"][0]["outputs"][0]["text"] == ["<local-path> 42\n"]
    assert result["metadata"]["path"] == "<local-path>"


def test_student_debug_display_rejected():
    book = {
        "metadata": {},
        "cells": [
            {
                "metadata": {},
                "outputs": [
                    {"data": {"text/plain": ["school sex age Medu Fedu guardian G3\n0 GP F 18"]}}
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="student-level"):
        _notebook(json.dumps(book).encode())


@pytest.mark.parametrize("status", ["analysis_ready", "failed", "running", "interrupted"])
def test_package_uses_real_full_run_validator(tmp_path, status):
    from parentedu.submission import build_package

    path = tmp_path / "run.json"
    path.write_text(json.dumps({"schema_version": 1, "status": status, "mode": "full"}))
    with pytest.raises(ValueError, match="ready full run"):
        build_package(tmp_path, path)


def test_changed_source_rejected_by_real_validator(tmp_path):
    from parentedu.submission import build_package

    (tmp_path / "README.md").write_text("changed")
    record = {
        "schema_version": 1,
        "status": "ready",
        "mode": "full",
        "run_id": "test",
        "comparison_status": "PASS",
        "tests_status": "PASS",
        "source_hashes": {"README.md": "0" * 64},
        "outputs": {"a": "0" * 64},
    }
    path = tmp_path / "run.json"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Changed evidence"):
        build_package(tmp_path, path)


def test_runner_guard_removed_only_from_packaged_copy():
    guard = "import sys, pathlib, parentedu\nassert pathlib.Path(sys.executable)\nprint('Fresh checkout kernel verified')"
    book = {
        "metadata": {},
        "cells": [{"source": guard}, {"source": "print(42)", "metadata": {}, "outputs": []}],
    }
    result = json.loads(_notebook(json.dumps(book).encode()))
    assert len(result["cells"]) == 1
    assert result["cells"][0]["source"] == "print(42)"
    assert len(book["cells"]) == 2
