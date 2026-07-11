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

# Acceptable freeze markers.
# - `0.2.1rc1` is the v0.2.1 freeze pre-release.
# - `0.3.0` is the milestone release (Phase 2 install/path done).
# - `0.3.0.1` is the console-entry-point hotfix (PEP 440 post-release).
# - `0.3.0.dev<N>` covers PEP 440 dev releases during 0.3 development.
ACCEPTABLE = {"0.2.1rc1", "0.3.0", "0.3.0.1"}
ACCEPTABLE_PREFIX = ("0.3.0.dev",)  # PEP 440 dev releases during 0.3 development


def test_version_is_pre_1_freeze():
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "pyproject.toml missing top-level `version = ...` line"
    version = m.group(1).strip()
    assert version in ACCEPTABLE or version.startswith(ACCEPTABLE_PREFIX), (
        f"pyproject.toml version {version!r} is not a documented freeze "
        f"marker. PR1 expects '0.2.1rc1'; v0.3.0 milestone is '0.3.0'; "
        f"hotfix post-release is '0.3.0.1'."
    )
    assert not version.startswith("1."), (
        f"version {version!r} crosses 1.0.0 — freeze guard refuses to allow it"
    )
