"""TOML config read/write for mneme.

`read_config(path)` returns a `dict` from the config file. `write_config(path,
data)` writes a dict back as TOML. Both use stdlib TOML where possible:

- Read: `tomllib` on Python 3.11+; `tomli` (from the `toml10` extras) on
  3.10. We try the fallback lazily because tomllib is bytecode-stable and
  not all installs share a .pth with tomli.
- Write: `tomli_w` (always required; declared in `dependencies`).

The reader preserves types — strings stay strings, numbers stay numbers,
booleans stay booleans, etc. — so that the `bundle_path` we read back is
identical to the one we wrote.

A round-trip is the contract of `read_config ∘ write_config`: any value
written through `write_config` must read back equal.
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

import tomli_w  # type: ignore[import-untyped]


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
    """Write a dict as TOML. Uses tomli_w for proper escaping of quotes,
    backslashes, and control characters.

    The output is canonical-ish but stable enough that a `read_config`
    round-trip on the same data yields an equal dict.
    """
    body = tomli_w.dumps(dict(data))
    Path(path).write_text(body, encoding="utf-8")
