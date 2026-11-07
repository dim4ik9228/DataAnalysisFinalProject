"""Execute all notebooks and verify their generated evidence."""

import argparse
from pathlib import Path

from parentedu.reproducibility import run_project

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--analysis-only", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    result = run_project(
        baseline=args.baseline, analysis_only=args.analysis_only, timeout=args.timeout
    )
    print(result["status"], result["run_id"])
