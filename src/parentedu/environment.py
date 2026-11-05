"""Validate and record the local environment without running research analysis."""

import hashlib
import importlib
import json
import platform
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import parentedu
from parentedu.config import load_config
from parentedu.paths import ROOT

# Import the actual modules too: installed metadata alone does not verify usable binaries.
PACKAGES = {
    "jupyterlab": "jupyterlab",
    "ipykernel": "ipykernel",
    "nbconvert": "nbconvert",
    "nbformat": "nbformat",
    "pandas": "pandas",
    "numpy": "numpy",
    "scipy": "scipy.stats",
    "statsmodels": "statsmodels.api",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
    "plotly": "plotly.express",
    "parentedu-replication": "parentedu",
}


def _run(*command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )


def check_environment() -> dict:
    """Fail on a wrong interpreter, package location, configuration or stale lock."""
    expected_prefix = ROOT / ".venv"
    if Path(sys.prefix).resolve() != expected_prefix.resolve():
        raise RuntimeError("Select the project .venv kernel and restart it.")
    pinned_python = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    if platform.python_version() != pinned_python:
        raise RuntimeError(f"Python must match .python-version ({pinned_python}).")
    if Path(parentedu.__file__).resolve().parent != ROOT / "src" / "parentedu":
        raise RuntimeError("The editable parentedu package must come from this checkout.")
    config = load_config()
    seed = config["project"]["seed"]
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Seed must be an integer in [0, 2**32).")
    required = (
        "data/raw",
        "data/processed",
        "data/reference",
        "notebooks",
        "outputs/tables",
        "outputs/figures",
        "outputs/executed",
        "outputs/logs",
    )
    missing = [item for item in required if not (ROOT / item).is_dir()]
    if missing:
        raise FileNotFoundError(f"Missing project directories: {missing}")
    lock_path = ROOT / "uv.lock"
    with lock_path.open("rb") as handle:
        lock_version = tomllib.load(handle)["version"]
    locked = _run("uv", "lock", "--check")
    if locked.returncode:
        raise RuntimeError(f"uv.lock check failed: {locked.stderr.strip()}")
    versions = {}
    for distribution, module_name in PACKAGES.items():
        importlib.import_module(module_name)
        versions[distribution] = version(distribution)
    return {
        "checks_passed": True,
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "project_root": str(ROOT),
        "package_path": str(Path(parentedu.__file__).resolve()),
        "research_status": config["project"]["status"],
        "seed": seed,
        "packages": versions,
        "lock": {
            "version": lock_version,
            "sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
            "up_to_date": True,
        },
    }


def record_environment(checks: dict) -> Path:
    """Write local run metadata; exclude credentials and full environment variables."""
    uv = _run("uv", "--version")
    if uv.returncode:
        raise RuntimeError("Could not determine uv version.")
    status = _run("git", "status", "--porcelain")
    if status.returncode:
        raise RuntimeError("git status failed; check workspace permissions and Git context.")
    head = _run("git", "rev-parse", "--verify", "HEAD")
    if head.returncode == 0:
        commit = head.stdout.strip()
        commit_status = "present"
    else:
        symbolic = _run("git", "symbolic-ref", "-q", "HEAD")
        ref = symbolic.stdout.strip()
        ref_check = _run("git", "show-ref", "--verify", "--quiet", ref) if ref else None
        if symbolic.returncode or ref_check is None or ref_check.returncode != 1:
            raise RuntimeError("Could not distinguish an unborn Git branch from a Git error.")
        commit = None
        commit_status = "unborn_branch"
    record = {
        **checks,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "uv": uv.stdout.strip(),
        "git": {
            "commit": commit,
            "commit_status": commit_status,
            "dirty": bool(status.stdout.strip()),
        },
    }
    destination = ROOT / "outputs" / "logs" / "environment.json"
    destination.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination
