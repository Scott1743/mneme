"""Skill entry shim: ``python3 mneme.py <subcmd> [args]``.

Used by skill.sh users after installing the skill at
``~/.claude/skills/mneme/``. Resolves the ``mneme`` package directory
next to this shim and dispatches to ``mneme.cli.main``.

The shim is named ``mneme.py`` and sits alongside the ``mneme/``
package; Python's import system prefers the package over a same-named
module, so ``from mneme.cli import main`` resolves correctly.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

from mneme.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))