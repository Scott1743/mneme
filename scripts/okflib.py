"""Zero-dependency (Python stdlib only) OKF v0.1 library.

Minimal YAML-subset frontmatter parser: sufficient for OKF's required
fields (type) and common metadata (key: value, key: [a, b], quoted
strings, # comments). NOT a full YAML parser — OKF conformance only
requires `type`; consumers needing full YAML may use PyYAML separately.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

RESERVED = ("index.md", "log.md")
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?(.*)\Z", re.S)


@dataclass
class Violation:
    path: str
    rule: str
    severity: str  # "error" | "warning"
    detail: str


@dataclass
class Report:
    errors: List[Violation] = field(default_factory=list)
    warnings: List[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_frontmatter(text: str) -> Optional[Tuple[Dict, str]]:
    """Return (metadata_dict, body) or None if no frontmatter block.

    Minimal YAML-subset parser. Handles:
      key: value
      key: [a, b, c]
      key: "quoted"  /  key: 'quoted'
      # comment lines
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    raw, body = m.group(1), m.group(2)
    meta: Dict = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            meta[key] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
        elif len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
            meta[key] = val[1:-1]
        else:
            meta[key] = val
    return meta, body


def list_concepts(bundle_path) -> List[str]:
    """Concept IDs (file path without .md) for all non-reserved .md files."""
    root = Path(bundle_path)
    ids = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        if os.path.basename(rel) in RESERVED:
            continue
        ids.append(rel[:-3])
    return ids


def read_concept(bundle_path, concept_id: str) -> Optional[Tuple[Dict, str]]:
    """Return (metadata, body) for a concept ID, or None if missing."""
    p = Path(bundle_path) / (concept_id + ".md")
    if not p.exists():
        return None
    return parse_frontmatter(p.read_text(encoding="utf-8"))
