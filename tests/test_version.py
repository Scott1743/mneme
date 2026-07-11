"""Phase 0 freeze §3.4 — version pinning.

PR1 freezes the version to a clearly pre-1.0 marker. PR3 finalizes to 0.3.0.
The freeze isolates dangerous behavior we promised to keep until Phase 1
lands; bumping to anything that reads as a release candidate would mislead
users into installing an in-progress tree.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

# Acceptable freeze markers. PR1 expects `0.2.1rc1`. PR3 will set `0.3.0`.
# Both predate 1.0.0; either is acceptable evidence that freeze is in effect.
ACCEPTABLE = {"0.2.1rc1", "0.3.0"}
ACCEPTABLE_PREFIX = ("0.3.0.dev",)  # PEP 440 dev releases during 0.3 development


def test_version_is_pre_1_freeze():
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "pyproject.toml missing top-level `version = ...` line"
    version = m.group(1).strip()
    assert version in ACCEPTABLE or version.startswith(ACCEPTABLE_PREFIX), (
        f"pyproject.toml version {version!r} is not a documented freeze "
        f"marker. PR1 expects '0.2.1rc1'; PR3 finalizes '0.3.0'."
    )
    assert not version.startswith("1."), (
        f"version {version!r} crosses 1.0.0 — freeze guard refuses to allow it"
    )
