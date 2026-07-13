#!/usr/bin/env python3
"""OKF v0.1 conformance validator CLI. Zero-dependency (stdlib)."""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    # Allow `python3 src/mneme/validate_okf.py <bundle>` to run as a
    # standalone script in dev. Inside the package, use `mneme lint
    # <bundle>` instead.
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mneme.okflib import Report, validate_bundle


def print_report(report: Report) -> int:
    """Print a validation report to stdout. Returns the would-be process
    exit code: 0 if no errors, 1 if any errors were found."""
    for v in report.errors:
        print(f"ERROR  {v.path}: [{v.rule}] {v.detail}")
    for v in report.warnings:
        print(f"WARN   {v.path}: [{v.rule}] {v.detail}")
    print(f"\n{len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    return 1 if report.errors else 0


def main(argv):
    if len(argv) != 2:
        print("usage: validate_okf.py <bundle_path>", file=sys.stderr)
        return 2
    return print_report(validate_bundle(argv[1]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
