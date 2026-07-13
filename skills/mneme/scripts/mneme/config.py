"""TOML config read/write for mneme.

`read_config(path)` returns a `dict` from the config file. `write_config(path,
data)` writes a dict back as TOML. Both use stdlib (or stdlib-equivalent)
TOML where possible:

- Read: ``tomllib`` on Python 3.11+; ``tomli`` (from the ``toml10`` extras)
  on 3.10. We try the fallback lazily because tomllib is bytecode-stable
  and not all installs share a .pth with tomli.
- Write: in-house hand-rolled writer (~60 lines, see ``toml_writer.py``).
  Replaces ``tomli_w`` so the OKF core stays zero-third-party-dep per
  ``CLAUDE.md`` §"分层依赖". The writer covers exactly the types mneme
  writes (``str`` / ``int`` / ``float`` / ``bool`` / ``list``); unknown
  types raise ``TypeError`` rather than emit invalid TOML.

A round-trip is the contract of ``read_config ∘ write_config``: any value
written through ``write_config`` must read back equal.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

if sys.version_info >= (3, 11):
    import tomllib as _toml_read  # type: ignore[import-not-found]
else:  # pragma: no cover — fallback path on Python 3.10
    try:
        import tomli as _toml_read  # type: ignore[import-nottyped]
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Reading mneme config on Python 3.10 requires the 'toml10' "
            "extras: `pip install 'mneme[toml10]'`."
        ) from exc

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
