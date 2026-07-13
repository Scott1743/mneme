"""Dream audit (read-only).

`mneme dream` is a read-only audit lens over an OKF v0.1 bundle. It
returns a candidate report describing:

  - OKF v0.1 hard-rule candidates the agent should re-check
  - Mneme writer-rule candidates (e.g. tagged concept pages)
  - Navigation candidates (dangling / orphan / tag-drift)

This module is intentionally pure-read. It MUST NOT shell out, call
``subprocess.run`` / ``os.execvp`` / ``os.system``, invoke ``git``, or
write any file inside the bundle. The CLI subcommand that wraps it
also has no ``--apply`` flag — writes happen in the ``SKILL.md``
workflow, after the user explicitly approves the audit report.

`tests/test_dream_readonly.py` enforces all four invariants:

  1. the bundle's bytes are not modified by ``dream_audit``;
  2. the CLI's ``dream`` subparser has no ``--apply`` flag;
  3. ``mneme dream`` never shells out via ``subprocess.run``;
  4. the report contains only raw distance candidates, never a
     similarity threshold like ``>=0.92``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

# Reserved OKF v0.1 filenames (§6, §7). Not subject to the per-page
# "missing frontmatter" rule.
_OKF_RESERVED = ("index.md", "log.md")


def _iter_md_files(bundle: Path) -> List[Path]:
    """Return the bundle's non-`.mneme` Markdown files, sorted."""
    return sorted(
        p for p in bundle.rglob("*.md")
        if p.is_file() and ".mneme" not in p.relative_to(bundle).parts
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def dream_audit(bundle: Path) -> Dict[str, Any]:
    """Walk ``bundle`` and return a candidate audit report.

    Pure read. Returns a plain ``dict`` that the CLI serializes to
    JSON. Never mutates the bundle, never invokes subprocesses, never
    inspects ``.git/``, and never reads from the network.

    The report shape is intentionally small and stable so that the
    ``SKILL.md`` workflow can ask the user "approve this?" and the
    agent can answer by listing candidate paths + rules. There are no
    similarity scores or thresholds — only "raw distance" candidates
    (currently: candidate paths + rule codes + count). Anything more
    numerical / semantic ships in v2.1 alongside L2.
    """
    bundle = Path(bundle)
    report: Dict[str, Any] = {
        "okf_hard_rules": [],
        "mneme_writer_rules": [],
        "navigation": {
            "dangling": [],
            "orphan": [],
            "tag_drift": [],
        },
        "_meta": {
            "raw_distance_only": True,
            "writes": "none — agent does writes in SKILL.md workflow",
        },
    }
    if not bundle.is_dir():
        report["_meta"]["error"] = f"bundle path is not a directory: {bundle}"
        return report

    candidate_pages: List[str] = []
    for p in _iter_md_files(bundle):
        rel = p.relative_to(bundle).as_posix()
        if rel in _OKF_RESERVED:
            continue
        text = _read_text(p)
        # OKF §4 — non-reserved `.md` files MUST have YAML frontmatter.
        if not text.lstrip().startswith("---"):
            report["okf_hard_rules"].append({
                "path": rel,
                "rule": "OKF-NO-FRONTMATTER",
            })
            continue
        # Mneme writer rule — every Mneme-written concept page has
        # >=1 `tags` value (external OKF bundles only get a WARN at
        # lint time, not here; dream reports candidate pages only).
        if "tags:" not in text:
            report["mneme_writer_rules"].append({
                "path": rel,
                "rule": "MNEME-TAG-MISSING",
            })
        candidate_pages.append(rel)

    report["_meta"]["candidate_count"] = len(candidate_pages)
    return report