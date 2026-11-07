"""Bootstrap Windows renderer independently of Codex and the analysis environment."""

import argparse
import hashlib
import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

NODE_VERSION = "v22.15.0"
NODE_SHA256 = "06067d4f0d463f90ed803d5eca5b039a05dec5d70fc7b7cc254803a59bd0e27c"
NODE_URL = f"https://nodejs.org/dist/{NODE_VERSION}/node-{NODE_VERSION}-win-x64.zip"
PLAYWRIGHT_VERSION = "1.62.1"
PYPDF_VERSION = "6.21.4"


def checked_version(command, expected, cwd=None):
    value = subprocess.check_output(command, text=True, cwd=cwd).strip()
    if value != expected:
        raise ValueError(f"Expected {expected}, got {value}: {command[0]}")
    return value


def setup_node(root):
    override = os.environ.get("REPORT_NODE")
    node = (
        Path(override)
        if override
        else root / f"build/toolchain/node/node-{NODE_VERSION}-win-x64/node.exe"
    )
    if not node.is_file():
        if override:
            raise FileNotFoundError(node)
        node.parent.parent.mkdir(parents=True, exist_ok=True)
        archive = node.parent.parent / f"node-{NODE_VERSION}-win-x64.zip"
        if not archive.exists():
            with (
                urllib.request.urlopen(NODE_URL, timeout=120) as response,
                archive.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != NODE_SHA256:
            raise ValueError("Node archive SHA256 mismatch; remove archive and retry.")
        destination = node.parent.parent.resolve()
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                if not (destination / member.filename).resolve().is_relative_to(destination):
                    raise ValueError("Unsafe Node archive path")
            bundle.extractall(destination)
    checked_version([str(node), "--version"], NODE_VERSION)
    return node.resolve()


def setup(root):
    tool = root / "tools/reporting"
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("Install uv and put it on PATH before renderer setup.")
    subprocess.run([uv, "sync", "--locked", "--project", str(tool)], check=True)
    node = setup_node(root)
    npm = node.parent / "node_modules/npm/bin/npm-cli.js"
    env = os.environ.copy()
    env["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
    subprocess.run(
        [str(node), str(npm), "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=tool,
        env=env,
        check=True,
    )
    checked_version(
        [str(node), "-p", "require('playwright/package.json').version"],
        PLAYWRIGHT_VERSION,
        cwd=tool,
    )
    return node


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    options = parser.parse_args()
    setup(options.root.resolve())
