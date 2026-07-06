"""Plain helper functions used by mneme.py. No Strands @tool decorators.

(Old tools.py mixed these plain helpers with @tool-decorated wrappers.
The @tool wrappers were removed when independent agents were deleted in v2.1;
the helpers are still needed by mneme.py CLI dispatch.)
"""
from __future__ import annotations

import os
import re
from pathlib import Path


def slug_from_path(path) -> str:
    base = Path(path).stem
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")


def resolve_bundle(config_path=None):
    if config_path is None:
        config_path = Path.home() / ".config" / "mneme" / "config.toml"
    config_path = Path(config_path)
    if config_path.exists():
        for line in config_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("bundle_path"):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return Path(val)
    env = os.environ.get("MNEME_BUNDLE")
    if env:
        return Path(env)
    import okflib
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        idx = d / "index.md"
        if idx.exists():
            parsed = okflib.parse_frontmatter(idx.read_text(encoding="utf-8"))
            if parsed and parsed[0].get("okf_version"):
                return d
    wiki = Path.cwd() / "wiki"
    return wiki if wiki.exists() else None
