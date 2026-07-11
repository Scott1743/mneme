"""Zero-dependency (Python stdlib only) OKF v0.1 library.

The producer-side `parse_frontmatter()` is a deliberate subset parser (lists,
quoted strings, # comments). It will accept YAML that PyYAML rejects; that's
intentional, because we want base installs to round-trip human-written
fragments without pulling in a YAML dependency.

The verify-side, used by `validate_bundle()`, optionally adopts PyYAML when
the `mneme[validate]` extra is installed. With PyYAML the validator certifies
arbitrary OKF bundles; without it the validator falls back to the lenient
parser and emits a `strict-validation-disabled` warning so callers can see
they are operating in zero-dep mode.

OKF v0.1 conformance (SPEC §3–§9):
  §3: bundle structure
  §4: concept documents (require non-empty scalar `type`, valid frontmatter)
  §5: cross-references (broken links are warnings, not errors)
  §6: index.md (root may declare only `okf_version`; nested index.md must
      have no frontmatter at all)
  §7: log.md (date-prefixed headings, newest-first; missing log is a warning)
  §8: citations (consumer-side; not validator obligations)
  §9: tolerance — unknown `type` is a warning, broken links are warnings,
      one bad file must not hide valid concepts elsewhere.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

RESERVED = ("index.md", "log.md")
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?(.*)\Z", re.S)
_LINK_RE = re.compile(r"\]\((/[^\)]+\.md)\)")

# OKF §4.1 — `type` is `<Type name>` (scalar). Producer vocab is not
# centralized (per OKF §9 tolerance); we recognize the four most common
# values and warn on anything else.
KNOWN_TYPES = frozenset({"Concept", "Reference", "Summary", "Source"})

# OKF §4.1 — `timestamp` is recommended. ISO 8601 with optional time,
# timezone, fractional seconds. We accept the broad pattern; lenient
# parsing is intentional (matches the recommendation).
_ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"  # date
    r"(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$"  # optional time
)

# OKF §7 — log entries must be date-prefixed.
_LOG_HEADING_DATE_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})\b")

# Frontmatter keys OKF documents (SPEC §4.1). Anything outside this is
# warned as `unknown-key`; the validator preserves unknown keys but does
# not require them.
_KNOWN_FRONTMATTER_KEYS = frozenset(
    {"type", "title", "description", "tags", "timestamp", "resource", "okf_version"}
)

try:
    import yaml as _yaml  # type: ignore[import-untyped]

    HAS_YAML = True
except ImportError:  # pragma: no cover — runtime zero-dep path
    _yaml = None
    HAS_YAML = False


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


def _strict_meta(text: str) -> Tuple[Optional[Dict], List[str]]:
    """Return (parsed_frontmatter, error_messages) using the strictest
    parser available.

    - When PyYAML is installed: PyYAML parses the frontmatter block.
      Returns ({...}, []) on success; (None, [errors]) on parse failure;
      (None, []) when the file has no frontmatter block at all.
    - When PyYAML is NOT installed: falls back to the lenient parser and
      returns (parsed_dict, []). The producer-side parser cannot reject
      malformed YAML, so callers flag this with a `strict-validation-
      disabled` warning at the bundle level.

    The returned dict preserves YAML types (int stays int, list stays list)
    so callers can enforce scalar constraints on `type`.
    """
    if HAS_YAML:
        m = _FRONTMATTER_RE.match(text)
        if not m:
            return None, []
        raw_block = m.group(1)
        try:
            parsed = _yaml.safe_load(raw_block)
        except _yaml.YAMLError as exc:  # type: ignore[union-attr]
            mark = getattr(exc, "problem_mark", None)
            problem = getattr(exc, "problem", None) or str(exc)
            if mark is not None:
                return None, [f"{mark.line + 1}:{mark.column + 1}: {problem}"]
            return None, [problem]
        return parsed, []
    lenient = parse_frontmatter(text)
    if lenient is None:
        return None, []
    return lenient[0], []


def _verify_frontmatter_yaml(text: str) -> Optional[List[str]]:
    """Strict YAML verification of the frontmatter block (kept for the
    root-index reserved-file path that wants only error messages).

    Returns:
      - None if the file has no frontmatter block, or PyYAML is unavailable
      - empty list if PyYAML parsed the block successfully
      - non-empty list of "<line>:<col>: <problem>" strings on rejection
    """
    if not HAS_YAML:
        return None
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    raw_block = m.group(1)
    try:
        _yaml.safe_load(raw_block)
        return []
    except _yaml.YAMLError as exc:  # type: ignore[union-attr]
        msgs: List[str] = []
        mark = getattr(exc, "problem_mark", None)
        problem = getattr(exc, "problem", None) or str(exc)
        if mark is not None:
            msgs.append(f"{mark.line + 1}:{mark.column + 1}: {problem}")
        else:
            msgs.append(problem)
        return msgs


def list_concepts(bundle_path) -> List[str]:
    """Concept IDs (file path without .md) for all non-reserved .md files."""
    root = Path(bundle_path)
    ids = []
    for p in sorted(root.rglob("*.md")):
        if any(part == ".mneme" for part in p.relative_to(root).parts):
            continue
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


def _validate_reserved(rel: str, name: str, text: str, report: Report) -> None:
    """Validate reserved-name files per SPEC §6 and §7."""
    m = _FRONTMATTER_RE.match(text)
    has_fm = bool(m and m.group(1).strip())

    if name == "log.md":
        if not text.strip():
            report.warnings.append(
                Violation(rel, "bad-reserved", "warning", "log.md is empty")
            )
            return
        # Spec §7: each entry MUST start with a date prefix.
        # Root log: behavior depends on whether the file is at the root.
        # Nested log files: not mentioned; we treat them like root for now.
        _validate_log_body(rel, (m.group(2) if m else text), report)
        return

    if name == "index.md":
        # Nested index.md: must have no frontmatter at all (SPEC §6).
        nested = rel.count(os.sep) > 0 and rel != "index.md"
        # The path separator on POSIX is "/"; we standardized on as_posix()
        # in callers, so count "/" instead.
        if "/" in rel and rel != "index.md":
            if has_fm:
                report.errors.append(
                    Violation(
                        rel,
                        "nested-index-frontmatter",
                        "error",
                        (
                            "nested index.md must have no frontmatter; only "
                            "the bundle root index.md may declare okf_version"
                        ),
                    )
                )
            return
        # Root index.md: frontmatter must declare only `okf_version`.
        body = m.group(2) if m else text
        if not body.strip():
            report.warnings.append(
                Violation(rel, "bad-reserved-index", "warning", "index.md body is empty")
            )
        meta: Dict = {}
        if has_fm and m is not None:
            parsed = parse_frontmatter(text)
            meta = parsed[0] if parsed else {}
        # Missing okf_version is a warning regardless of whether the root
        # has any frontmatter at all (SPEC §6 says it's recommended but
        # not required).
        if "okf_version" not in meta:
            report.warnings.append(
                Violation(
                    rel,
                    "missing-okf-version",
                    "warning",
                    (
                        "root index.md does not declare okf_version "
                        "(recommended but not required)"
                    ),
                )
            )
        for key in meta.keys():
            if key != "okf_version":
                report.errors.append(
                    Violation(
                        rel,
                        "root-index-extra-key",
                        "error",
                        (
                            f"root index.md may only declare `okf_version`; "
                            f"got extra key `{key}`"
                        ),
                    )
                )
        # Strict YAML check on root index too.
        yaml_msgs = _verify_frontmatter_yaml(text)
        if yaml_msgs:
            for msg in yaml_msgs:
                report.errors.append(
                    Violation(rel, "malformed-yaml", "error", msg)
                )


def _validate_log_body(rel: str, body: str, report: Report) -> None:
    """SPEC §7: log entries MUST be date-prefixed (`## YYYY-MM-DD...`) and
    kept newest-first (each entry older than the one above it).

    H1 (`# ...`) resets the date sequence — files may start with an H1 like
    "# Directory Update Log" before the entries begin.
    """
    prev_date: Optional[str] = None
    for line in body.splitlines():
        # `## ` (with trailing space) marks a log entry; anything else
        # that's a heading is H1 and resets the sequence.
        if line.startswith("## "):
            m = _LOG_HEADING_DATE_RE.match(line)
            if not m:
                report.errors.append(
                    Violation(
                        rel,
                        "log-heading-format",
                        "error",
                        (
                            f"log heading `{line.strip()}` must start with "
                            f"a YYYY-MM-DD date prefix"
                        ),
                    )
                )
                continue
            date = m.group(1)
            if prev_date is not None and date > prev_date:
                report.errors.append(
                    Violation(
                        rel,
                        "log-not-newest-first",
                        "error",
                        (
                            f"log entry `{line.strip()}` is newer than the "
                            f"entry directly above it (SPEC §7 requires "
                            f"newest-first)"
                        ),
                    )
                )
                continue
            prev_date = date
        elif line.startswith("# ") and not line.startswith("## "):
            # H1 resets the date sequence so file-level `# Directory Update Log`
            # doesn't pollute a later entry comparison.
            prev_date = None


def _check_links(root: Path, report: Report) -> None:
    for p in sorted(root.rglob("*.md")):
        if any(part == ".mneme" for part in p.relative_to(root).parts):
            continue
        rel = p.relative_to(root).as_posix()
        if os.path.basename(rel) in RESERVED:
            continue
        text = p.read_text(encoding="utf-8")
        for m in _LINK_RE.finditer(text):
            target = m.group(1).lstrip("/")
            if not (root / target).exists():
                report.warnings.append(
                    Violation(rel, "broken-link", "warning", f"link target not found: {m.group(1)}")
                )


def _validate_concept(rel: str, text: str, report: Report) -> None:
    """SPEC §4 — concept page validation."""
    # Strictest parse path (PyYAML when installed). Falls through to the
    # lenient producer-side parser when PyYAML is not available.
    meta, yaml_errs = _strict_meta(text)
    if meta is None and not yaml_errs:
        # No frontmatter block at all.
        report.errors.append(
            Violation(rel, "no-frontmatter", "error", "missing YAML frontmatter block")
        )
        return
    # When PyYAML rejected the file, we still want to run other checks
    # against whatever the lenient parser can recover (SPEC §9 isolation:
    # one bad file must not hide issues in others, by analogy here we also
    # surface non-YAML issues on a YAML-broken file).
    for msg in yaml_errs:
        report.errors.append(
            Violation(rel, "malformed-yaml", "error", msg)
        )
    if meta is None:
        lenient = parse_frontmatter(text)
        if lenient is None:
            return
        meta = lenient[0]

    # §4.1 type field — non-empty scalar.
    t = meta.get("type")
    if t is None:
        report.errors.append(
            Violation(rel, "empty-type", "error", "frontmatter has no `type` field")
        )
    elif isinstance(t, str):
        if not t.strip():
            report.errors.append(
                Violation(rel, "empty-type", "error", "frontmatter has empty `type`")
            )
        elif t not in KNOWN_TYPES:
            # SPEC §9 tolerance: unknown `type` is a warning.
            report.warnings.append(
                Violation(
                    rel,
                    "unknown-type",
                    "warning",
                    f"unknown type `{t}` (known: {sorted(KNOWN_TYPES)})",
                )
            )
    else:
        # Non-scalar (list / int / bool / null): SPEC §4.1 wants a name.
        report.errors.append(
            Violation(
                rel,
                "type-not-scalar",
                "error",
                f"`type` must be a scalar; got {type(t).__name__}",
            )
        )

    # §4.1 unknown frontmatter keys (tolerated, but flagged so consumers
    # can choose to clean up).
    for key in meta.keys():
        if key not in _KNOWN_FRONTMATTER_KEYS:
            report.warnings.append(
                Violation(
                    rel,
                    "unknown-key",
                    "warning",
                    f"unknown frontmatter key `{key}`",
                )
            )

    # §4.1 timestamp soft tolerance.
    if "timestamp" not in meta:
        report.warnings.append(
            Violation(
                rel,
                "missing-timestamp",
                "warning",
                "`timestamp` field absent (SPEC §4.1 recommends it)",
            )
        )
    else:
        ts = meta["timestamp"]
        if isinstance(ts, str):
            if not ts.strip():
                report.warnings.append(
                    Violation(rel, "empty-timestamp", "warning", "`timestamp` is empty")
                )
            elif not _ISO8601_RE.match(ts):
                report.warnings.append(
                    Violation(
                        rel,
                        "bad-timestamp-format",
                        "warning",
                        f"`timestamp` `{ts}` is not in ISO 8601 format",
                    )
                )


def validate_bundle(bundle_path) -> Report:
    """Check OKF v0.1 §3–§9 hard rules + soft warnings."""
    root = Path(bundle_path)
    report = Report()
    if not root.is_dir():
        report.errors.append(
            Violation(str(root), "no-bundle", "error", "bundle path is not a directory")
        )
        return report

    if not HAS_YAML:
        report.warnings.append(
            Violation(
                ".",
                "strict-validation-disabled",
                "warning",
                (
                    "PyYAML not installed; OKF v0.1 strict YAML validation is "
                    "disabled. Install `mneme[validate]` for full conformance."
                ),
            )
        )

    for p in sorted(root.rglob("*.md")):
        parts = p.relative_to(root).parts
        if any(part == ".mneme" for part in parts):
            continue
        rel = p.relative_to(root).as_posix()
        name = os.path.basename(rel)
        text = p.read_text(encoding="utf-8")
        if name in RESERVED:
            _validate_reserved(rel, name, text, report)
            continue
        # Raw sources under sources/ are immutable inputs. They MUST NOT
        # have OKF frontmatter (they predate distillation) and the
        # validator must not flag them as concept violations.
        if "sources" in parts:
            continue
        _validate_concept(rel, text, report)

    _check_links(root, report)

    if not (root / "index.md").exists():
        report.warnings.append(
            Violation("index.md", "missing-index", "warning", "no root index.md")
        )
    if not (root / "log.md").exists():
        report.warnings.append(
            Violation("log.md", "missing-log", "warning", "no root log.md (optional per SPEC §7)")
        )

    return report
