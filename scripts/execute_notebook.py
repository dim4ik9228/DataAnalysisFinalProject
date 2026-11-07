"""Execute one notebook in a fresh kernel from this checkout only."""

import sys
from pathlib import Path

import nbformat
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient

from parentedu.paths import ROOT


def execute(source, target):
    spec_manager = KernelSpecManager(kernel_dirs=[str(ROOT / ".venv/share/jupyter/kernels")])
    manager = KernelManager(kernel_name="parentedu-replication", kernel_spec_manager=spec_manager)
    if Path(manager.kernel_spec.argv[0]).resolve() != Path(sys.executable).resolve():
        raise ValueError("Kernel does not use the current checkout interpreter")
    notebook = nbformat.read(source, as_version=4)
    guard = nbformat.v4.new_code_cell(
        "import sys, pathlib, parentedu\n"
        f"assert pathlib.Path(sys.executable).resolve() == pathlib.Path({sys.executable!r}).resolve()\n"
        f"assert pathlib.Path(parentedu.__file__).resolve() == pathlib.Path({str(ROOT / 'src/parentedu/__init__.py')!r}).resolve()\n"
        "print('Fresh checkout kernel verified')"
    )
    notebook.cells.insert(0, guard)
    try:
        NotebookClient(
            notebook,
            km=manager,
            timeout=180,
            resources={"metadata": {"path": str(ROOT)}},
            record_timing=False,
        ).execute(cwd=str(ROOT))
    finally:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        nbformat.write(notebook, target)


if __name__ == "__main__":
    execute(Path(sys.argv[1]), Path(sys.argv[2]))
