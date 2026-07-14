"""TOML config read/write for mneme.

Read uses stdlib `tomllib` (Python 3.11+). Write uses an in-house
~60-line hand-rolled writer (`toml_writer.py`) that handles exactly
the types mneme writes (str / int / float / bool / list).

Zero third-party deps; this module + the writer cover the full
mneme config round-trip with stdlib only.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Mapping

if sys.version_info < (3, 11):
    sys.stderr.write(
        "mneme requires Python 3.11 or newer (uses stdlib tomllib). "
        f"You have Python {sys.version_info.major}.{sys.version_info.minor}.\n"
    )
    sys.exit(1)

import tomllib as _toml_read  # type: ignore[import-not-found]

# In-house hand-rolled writer (replaces tomli_w as of v1.1.0).
from . import toml_writer as _toml_write  # noqa: E402


DEFAULT_RETRIEVAL_MODE = "fts5"
RETRIEVAL_MODES = frozenset({"fts5", "l2"})


class ConfigError(ValueError):
    """Raised when Mneme's own config contains an unsupported value."""


def resolve_config_dir(*, env: Mapping[str, str] | None = None) -> Path:
    """Return ``MNEME_CONFIG_DIR`` or the default ``~/.config/mneme``."""
    environment = os.environ if env is None else env
    configured = environment.get("MNEME_CONFIG_DIR")
    if configured:
        return Path(configured)
    home = environment.get("HOME")
    return (Path(home) if home else Path.home()) / ".config" / "mneme"


def read_config(path: Path) -> dict:
    """Load a TOML config file at `path`. Returns the parsed dict; empty
    dict for an empty file. Raises `OSError` if missing.

    The returned dict preserves TOML types. Quoted strings keep their
    quotes-trimmed value; multiline strings stay strings; integers stay
    integers; etc.
    """
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        return {}
    return _toml_read.loads(text)


def write_config(path: Path, data: Mapping[str, Any]) -> None:
    """Write a dict as TOML via the in-house ``toml_writer``.

    The output is one ``key = value`` per line, no section headers.
    Round-tripping through ``read_config`` yields the same dict.
    """
    _toml_write.write_config(Path(path), data)


def retrieval_mode(path: Path) -> str:
    """Return the persisted retrieval mode, defaulting to zero-dependency FTS5.

    Old configurations have no mode field and therefore retain their v2/v3.2
    behavior. An invalid explicit value is a local configuration error, not a
    property of the OKF bundle.
    """
    config_path = Path(path)
    if not config_path.is_file():
        return DEFAULT_RETRIEVAL_MODE
    mode = read_config(config_path).get("active_retrieval_mode", DEFAULT_RETRIEVAL_MODE)
    if not isinstance(mode, str) or mode not in RETRIEVAL_MODES:
        expected = ", ".join(sorted(RETRIEVAL_MODES))
        raise ConfigError(
            f"active_retrieval_mode must be one of {expected}; got {mode!r}"
        )
    return mode


def set_retrieval_mode(path: Path, mode: str) -> None:
    """Persist ``mode`` without discarding bundle_path or unknown config keys."""
    if mode not in RETRIEVAL_MODES:
        expected = ", ".join(sorted(RETRIEVAL_MODES))
        raise ConfigError(f"unsupported retrieval mode {mode!r}; expected {expected}")
    config_path = Path(path)
    current = read_config(config_path) if config_path.is_file() else {}
    current["active_retrieval_mode"] = mode
    config_path.parent.mkdir(parents=True, exist_ok=True)
    write_config(config_path, current)
