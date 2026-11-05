"""Acquire immutable UCI source bytes and validate the documented student schema."""

import csv
import hashlib
import io
import json
import os
import re
import tempfile
import tomllib
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from parentedu.paths import DATA_RAW, ROOT

SOURCE_URL = "https://archive.ics.uci.edu/dataset/320/student+performance"
DOWNLOAD_URL = "https://archive.ics.uci.edu/static/public/320/student+performance.zip"
SCHEMA_PATH = ROOT / "configs/data_schema.toml"
PROVENANCE_PATH = ROOT / "docs/data_provenance.json"
SOURCE_FILES = ("student-mat.csv", "student-por.csv", "student.txt")
CACHE_FILES = ("student-performance.zip", "student.zip", *SOURCE_FILES)


class DataValidationError(ValueError):
    """Invalid data with machine-readable diagnostics and no silent repairs."""

    def __init__(self, issues: list[dict]):
        self.issues = issues
        super().__init__(f"Student data validation failed ({len(issues)} issues)")


def load_schema(path: Path = SCHEMA_PATH) -> dict:
    with Path(path).open("rb") as handle:
        return tomllib.load(handle)


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _file_info(path: Path) -> dict:
    content = path.read_bytes()
    return {"sha256": _hash(content), "bytes": len(content)}


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _download(url: str, target: Path) -> str:
    """Stream a bounded response; urllib keeps TLS verification enabled."""
    request = urllib.request.Request(url, headers={"User-Agent": "parentedu-replication/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as handle:
        total = 0
        while chunk := response.read(65536):
            total += len(chunk)
            if total > 10_000_000:
                raise ValueError("Unexpectedly large UCI archive")
            handle.write(chunk)
        return response.geturl()


def _read_unique(archive: zipfile.ZipFile, name: str) -> bytes:
    matches = [item for item in archive.infolist() if item.filename == name]
    if len(matches) != 1:
        raise ValueError(f"Archive must contain one exact member: {name}")
    if matches[0].file_size > 5_000_000:
        raise ValueError(f"Unexpectedly large source member: {name}")
    return archive.read(matches[0])


def _unpack(source: Path, stage: Path) -> None:
    # Only exact known names are read: old files and paths from ZIP never become output paths.
    with zipfile.ZipFile(source) as outer:
        inner = _read_unique(outer, "student.zip")
    (stage / "student.zip").write_bytes(inner)
    with zipfile.ZipFile(io.BytesIO(inner)) as archive:
        for name in SOURCE_FILES:
            (stage / name).write_bytes(_read_unique(archive, name))


def _verify_files(directory: Path, manifest: dict) -> None:
    if set(manifest.get("files", {})) != set(CACHE_FILES):
        raise ValueError("Provenance must describe the exact five source files")
    for name in CACHE_FILES:
        path = directory / name
        if not path.is_file() or _file_info(path) != manifest["files"][name]:
            raise ValueError(f"Source hash/size mismatch: {name}")


def acquire_data(
    raw_dir: Path = DATA_RAW,
    provenance_path: Path = PROVENANCE_PATH,
    *,
    allow_bootstrap: bool = False,
) -> dict:
    """Verify cached sources or atomically acquire the version pinned in tracked provenance.

    Bootstrap is explicit and only creates provenance when it does not exist.
    Existing source files are never repaired, replaced or silently accepted on mismatch.
    """
    raw_dir, provenance_path = Path(raw_dir), Path(provenance_path)
    raw_dir.mkdir(parents=True, exist_ok=True)
    pinned = (
        json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance_path.exists()
        else None
    )
    if pinned is None and not allow_bootstrap:
        raise FileNotFoundError("Pinned provenance missing; explicit first acquisition is required")
    manifest_path = raw_dir / "data_manifest.json"
    if manifest_path.exists():
        if pinned is None:
            raise ValueError("Cache exists without tracked provenance")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _verify_files(raw_dir, pinned)
        _verify_files(raw_dir, manifest)
        if manifest["files"] != pinned["files"]:
            raise ValueError("Local acquisition manifest differs from pinned source version")
        return {**manifest, "cache_hit": True}
    if any(path.name != ".gitkeep" for path in raw_dir.iterdir()):
        raise ValueError("Incomplete or unmanifested raw cache; investigate before acquisition")
    with tempfile.TemporaryDirectory(prefix=".acquire-", dir=raw_dir) as temporary:
        stage = Path(temporary)
        final_url = _download(DOWNLOAD_URL, stage / "student-performance.zip")
        _unpack(stage / "student-performance.zip", stage)
        manifest = {
            "source_url": SOURCE_URL,
            "download_url": DOWNLOAD_URL,
            "final_url": final_url,
            "doi": "10.24432/C5TG7T",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "retrieved_at_utc": datetime.now(UTC).isoformat(),
            "archive_member": "student.zip",
            "files": {name: _file_info(stage / name) for name in CACHE_FILES},
        }
        if pinned is not None:
            _verify_files(stage, pinned)
        for name in CACHE_FILES:
            os.replace(stage / name, raw_dir / name)
        if pinned is None:
            _write_json(provenance_path, manifest)
        _write_json(manifest_path, manifest)
    return {**manifest, "cache_hit": False}


def validate_frame(
    frame: pd.DataFrame, schema: dict | None = None, subject: str = ""
) -> pd.DataFrame:
    """Validate exactly the original columns and return typed copies without dropping rows."""
    schema = load_schema() if schema is None else schema
    names = [column["name"] for column in schema["columns"]]
    issues = []

    def issue(row: int | None, column: str, kind: str, detail: str) -> None:
        issues.append(
            {
                "subject": subject,
                "source_row": row,
                "column": column,
                "issue_type": kind,
                "detail": detail,
            }
        )

    if list(frame.columns) != names:
        issue(None, "", "schema", "Original column names/order differ from data_schema.toml")
        raise DataValidationError(issues)
    typed = frame.copy()
    for column in schema["columns"]:
        name = column["name"]
        converted = []
        for ordinal, value in enumerate(frame[name].tolist(), start=1):
            if pd.isna(value) or value == "":
                issue(ordinal, name, "missing", "Empty/missing source value")
                converted.append(None)
                continue
            if column["dtype"] == "integer":
                text = str(value)
                if not re.fullmatch(r"[+-]?\d+", text):
                    issue(ordinal, name, "type", "Expected an integer code")
                    converted.append(None)
                    continue
                value = int(text)
                valid = (
                    ("allowed" not in column or value in column["allowed"])
                    and ("min" not in column or value >= column["min"])
                    and ("max" not in column or value <= column["max"])
                )
            else:
                valid = isinstance(value, str) and value in column["allowed"]
            if not valid:
                issue(ordinal, name, "domain", "Value outside documented codes/range")
            converted.append(value)
        if not any(item["column"] == name for item in issues):
            typed[name] = pd.Series(
                converted,
                index=frame.index,
                dtype=("int64" if column["dtype"] == "integer" else "object"),
            )
    if issues:
        raise DataValidationError(issues)
    return typed


def read_student_csv(
    path: Path, subject: str, schema: dict | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read exact semicolon CSV and append stable record-level provenance."""
    if subject not in ("mat", "por"):
        raise ValueError("Subject must be mat or por")
    schema = load_schema() if schema is None else schema
    path = Path(path)
    try:
        with path.open(encoding=schema["dataset"]["encoding"], newline="") as handle:
            records = list(
                csv.reader(handle, delimiter=schema["dataset"]["delimiter"], strict=True)
            )
    except (UnicodeDecodeError, csv.Error) as error:
        raise DataValidationError(
            [
                {
                    "subject": subject,
                    "source_row": None,
                    "column": "",
                    "issue_type": "parse",
                    "detail": str(error),
                }
            ]
        ) from error
    expected = [column["name"] for column in schema["columns"]]
    issues = []
    if not records or records[0] != expected:
        issues.append(
            {
                "subject": subject,
                "source_row": None,
                "column": "",
                "issue_type": "header",
                "detail": "Missing, duplicated or unexpected header",
            }
        )
    for ordinal, record in enumerate(records[1:], start=1):
        if len(record) != len(expected):
            issues.append(
                {
                    "subject": subject,
                    "source_row": ordinal,
                    "column": "",
                    "issue_type": "row_width",
                    "detail": "Unexpected source field count",
                }
            )
    if len(records) == 1:
        issues.append(
            {
                "subject": subject,
                "source_row": None,
                "column": "",
                "issue_type": "empty_data",
                "detail": "Header without student records",
            }
        )
    if issues:
        raise DataValidationError(issues)
    frame = validate_frame(pd.DataFrame(records[1:], columns=expected), schema, subject)
    quality = []
    for name in expected:
        quality.append(
            {"subject": subject, "column": name, "check": "missing", "value": 0, "status": "pass"}
        )
        values = sorted(frame[name].unique().tolist())
        quality.append(
            {
                "subject": subject,
                "column": name,
                "check": "observed_values",
                "value": json.dumps(values, ensure_ascii=False),
                "status": "info",
            }
        )
    for check, value in (
        ("nobs", len(frame)),
        ("exact_duplicate_excess", int(frame.duplicated().sum())),
        ("zero_G3", int(frame["G3"].eq(0).sum())),
    ):
        quality.append(
            {"subject": subject, "column": "", "check": check, "value": value, "status": "info"}
        )
    frame["subject"] = subject
    frame["source_file"] = path.name
    frame["source_row"] = range(1, len(frame) + 1)
    frame["record_id"] = [f"{subject}:{index:06d}" for index in frame["source_row"]]
    return frame, pd.DataFrame(quality)
