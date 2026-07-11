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
# - `0.4.0` is the v0.4.0 release (Phase 3 end-to-end harness).
# - `0.3.0.dev<N>` / `0.4.0.dev<N>` cover PEP 440 dev releases.
ACCEPTABLE = {"0.2.1rc1", "0.3.0", "0.3.0.1", "0.4.0", "0.5.0"}
ACCEPTABLE_PREFIX = ("0.3.0.dev", "0.4.0.dev", "0.5.0.dev")
