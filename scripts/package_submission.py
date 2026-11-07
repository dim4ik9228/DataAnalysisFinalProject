"""Build a verified review-candidate submission archive."""

import argparse
from pathlib import Path

from parentedu.paths import ROOT
from parentedu.submission import build_package, verify_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-record", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path, help="Only unpack and verify an existing ZIP")
    args = parser.parse_args()
    if args.verify:
        verify_package(args.verify)
        print("Package hashes and allowlist verified")
    else:
        archive, checksum = build_package(ROOT, args.run_record, args.output)
        print(f"Review candidate: {archive}\nSHA-256: {checksum}")


if __name__ == "__main__":
    main()
