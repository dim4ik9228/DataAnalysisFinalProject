"""Independent renderer preflight rejects missing tools and wrong versions."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("renderer_builder", ROOT / "scripts/build_reports.py")
reports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reports)


def test_missing_renderer_has_actionable_error(tmp_path, monkeypatch):
    for name in ("REPORT_PYTHON", "REPORT_NODE", "REPORT_NODE_MODULES", "REPORT_BROWSER"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="tools/reporting/setup.py"):
        reports.renderer_paths(tmp_path)


@pytest.fixture
def renderer(tmp_path, monkeypatch):
    for key in ("python", "node", "browser"):
        path = tmp_path / (key + ".exe")
        path.touch()
        monkeypatch.setenv("REPORT_" + key.upper(), str(path))
    modules = tmp_path / "modules"
    (modules / "playwright").mkdir(parents=True)
    (modules / "playwright/package.json").write_text(json.dumps({"version": "1.62.1"}))
    monkeypatch.setenv("REPORT_NODE_MODULES", str(modules))

    def output(command, **kwargs):
        if command[-1] == "--version":
            return "v22.15.0" if Path(command[0]).stem == "node" else "Python 3.12.10"
        return "pypdf 6.21.4"

    monkeypatch.setattr(reports.subprocess, "check_output", output)
    return tmp_path


def test_explicit_renderer_paths_are_validated(renderer):
    paths, versions = reports.renderer_paths(renderer)
    assert paths["modules"] == renderer / "modules"
    assert versions["playwright_version"] == "1.62.1"


def test_wrong_playwright_version_rejected(renderer):
    (renderer / "modules/playwright/package.json").write_text('{"version":"1.0.0"}')
    with pytest.raises(ValueError, match="requires 1.62.1"):
        reports.renderer_paths(renderer)
