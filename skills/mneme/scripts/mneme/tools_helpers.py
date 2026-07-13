"""Plain helper functions used by the CLI dispatch and the host agent."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping


def slug_from_path(path) -> str:
    base = Path(path).stem
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")


def _read_bundle_path_from(path: Path) -> Path | None:
    """Read the sole resolver key from a Mneme TOML config."""
    try:
        from .config import read_config

        value = read_config(path).get("bundle_path")
    except (OSError, ImportError, ValueError):
        return None
    return Path(value) if isinstance(value, str) and value else None


def resolve_bundle(
    *,
    config_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> Path | None:
    """Resolve a bundle using Mneme's frozen precedence chain.

    Resolution order is ``MNEME_BUNDLE``, ``config.toml``'s
    ``bundle_path``, an ancestor containing ``index.md``, then ``./wiki``.
    """
    environment = os.environ if env is None else env
    start = Path.cwd() if cwd is None else Path(cwd)

    bundle_value = environment.get("MNEME_BUNDLE")
    if bundle_value:
        return Path(bundle_value)

    from .config import resolve_config_dir

    directory = (
        Path(config_dir)
        if config_dir is not None
        else resolve_config_dir(env=environment)
    )
    configured = _read_bundle_path_from(directory / "config.toml")
    if configured is not None:
        return configured

    current = start.resolve()
    for directory in (current, *current.parents):
        if (directory / "index.md").exists():
            return directory

    wiki = start / "wiki"
    return wiki if wiki.exists() else None
