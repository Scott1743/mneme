"""TOML config read/write for mneme.

Read uses stdlib `tomllib` (Python 3.11+). Write uses an in-house
~60-line hand-rolled writer (`toml_writer.py`) that handles exactly
the types mneme writes (str / int / float / bool / list).

Zero third-party deps; this module + the writer cover the full
mneme config round-trip with stdlib only.
"""
from __future__ import annotations

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