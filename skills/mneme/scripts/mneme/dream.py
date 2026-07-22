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
from typing import Any, Dict

from . import okflib


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

    concepts = okflib.list_concepts(bundle)
    diagnostics = okflib.lint_bundle(bundle, require_tags=True)["diagnostics"]
    invalid_paths = set()
    for diagnostic in diagnostics:
        item = {
            "path": diagnostic["path"],
            "rule": diagnostic["code"],
            "detail": diagnostic["detail"],
        }
        if diagnostic["code"] == "MNEME-TAG-MISSING":
            report["mneme_writer_rules"].append(item)
        elif diagnostic["severity"] == "ERROR":
            report["okf_hard_rules"].append(item)
            invalid_paths.add(diagnostic["path"])

    report["_meta"]["candidate_count"] = len(concepts)
    report["_meta"]["valid_candidate_count"] = sum(
        1 for concept in concepts if f"{concept}.md" not in invalid_paths
    )
    return report
