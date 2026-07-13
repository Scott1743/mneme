"""Plain helper functions used by the CLI dispatch and the host agent."""
from __future__ import annotations

import os
import re
from pathlib import Path


def slug_from_path(path) -> str:
    base = Path(path).stem
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")


def resolve_bundle(config_path=None):
    """Walk the resolution chain documented in SKILL.md Step 0:

      1. `~/.config/mneme/config.toml` `bundle_path` (via mneme.config
         so the TOML reader can handle quotes / backslashes / non-ASCII)
      2. `MNEME_BUNDLE` env var
      3. Auto-discover: walk up from cwd for a root `index.md` whose
         frontmatter declares `okf_version`
      4. `./wiki` if it exists
    """
    if config_path is None:
        config_path = Path.home() / ".config" / "mneme" / "config.toml"
    config_path = Path(config_path)
    if config_path.exists():
        try:
            from .config import read_config
            data = read_config(config_path)
            val = data.get("bundle_path")
            if val:
                return Path(val)
        except (OSError, ImportError):
            # Missing file -> fall through; import failure is the
            # user's problem to address via `pip install pyyaml`.
            pass
    env = os.environ.get("MNEME_BUNDLE")
    if env:
        return Path(env)
    from . import okflib
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        idx = d / "index.md"
        if idx.exists():
            parsed = okflib.parse_frontmatter(idx.read_text(encoding="utf-8"))
            if parsed and parsed[0].get("okf_version"):
                return d
    wiki = Path.cwd() / "wiki"
    return wiki if wiki.exists() else None
