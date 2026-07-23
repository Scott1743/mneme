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

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable

from . import okflib


_TAG_BUDGET_MAX = 4
_ENTITY_BUDGET_MAX = 6
_RELATION_BUDGET_MAX = 5
_HEALTH_SAMPLE_LIMIT = 20


def _bounded_values(values: Iterable[str]) -> Dict[str, Any]:
    """Return a deterministic, bounded sample without hiding total size."""
    ordered = sorted(values)
    return {
        "values": ordered[:_HEALTH_SAMPLE_LIMIT],
        "total": len(ordered),
        "truncated": len(ordered) > _HEALTH_SAMPLE_LIMIT,
    }


def _bounded_items(items: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Bound structured findings while retaining their exact total."""
    return {
        "items": items[:_HEALTH_SAMPLE_LIMIT],
        "total": len(items),
        "truncated": len(items) > _HEALTH_SAMPLE_LIMIT,
    }


def _tag_health(bundle: Path, concepts: Iterable[str]) -> Dict[str, Any]:
    tag_counts: Counter[str] = Counter()
    display_names: Dict[str, str] = {}
    duplicate_tags = []
    pages_over_budget = []
    tagged_page_count = 0

    for concept in concepts:
        try:
            parsed = okflib.read_concept(bundle, concept)
        except (OSError, UnicodeDecodeError):
            continue
        if parsed is None:
            continue
        metadata, _ = parsed
        raw_tags = metadata.get("tags")
        if not isinstance(raw_tags, list):
            continue
        tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
        if tags:
            tagged_page_count += 1
        normalized = [tag.casefold() for tag in tags]
        for tag, key in zip(tags, normalized):
            display_names.setdefault(key, tag)
        for key in set(normalized):
            tag_counts[key] += 1
        duplicates = sorted(
            {display_names[key] for key, count in Counter(normalized).items() if count > 1}
        )
        path = f"{concept}.md"
        if duplicates:
            duplicate_tags.append({"path": path, "tags": duplicates})
        if len(tags) > _TAG_BUDGET_MAX:
            pages_over_budget.append({"path": path, "count": len(tags), "tags": tags})

    singleton_keys = [key for key, count in tag_counts.items() if count == 1]
    singleton_names = [display_names[key] for key in singleton_keys]
    top_tags = [
        {"tag": display_names[key], "count": count}
        for key, count in sorted(tag_counts.items(), key=lambda item: (-item[1], display_names[item[0]]))[
            :_HEALTH_SAMPLE_LIMIT
        ]
    ]
    unique_count = len(tag_counts)
    return {
        "advisory_only": True,
        "recommended_tags_per_page": "1-3; maximum 4 unless the page genuinely spans more reusable facets",
        "tagged_page_count": tagged_page_count,
        "unique_tag_count": unique_count,
        "singleton_tag_count": len(singleton_keys),
        "singleton_tag_ratio": round(len(singleton_keys) / unique_count, 3) if unique_count else 0.0,
        "singleton_tags": _bounded_values(singleton_names),
        "duplicate_tags": _bounded_items(duplicate_tags),
        "pages_over_budget": _bounded_items(pages_over_budget),
        "top_tags": top_tags,
    }


def _enrichment_health(bundle: Path) -> Dict[str, Any]:
    manifest = bundle / ".mneme" / "graph-extractions.json"
    base: Dict[str, Any] = {
        "advisory_only": True,
        "manifest_present": manifest.is_file(),
        "recommended_entities_per_enriched_page": "3-6",
        "recommended_semantic_relations_per_enriched_page": "2-5",
        "enriched_page_count": 0,
        "entity_count": 0,
        "semantic_relation_count": 0,
        "unique_predicate_count": 0,
        "singleton_predicate_count": 0,
        "singleton_predicates": _bounded_values([]),
        "predicate_counts": [],
        "pages_over_entity_budget": _bounded_items([]),
        "pages_over_relation_budget": _bounded_items([]),
        "reserved_mentions_relations": _bounded_items([]),
    }
    if not manifest.is_file():
        return base
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        base["manifest_error"] = str(exc)
        return base

    pages = payload.get("pages") if isinstance(payload, dict) else None
    if not isinstance(pages, list):
        base["manifest_error"] = "graph-extractions.json has no pages list"
        return base

    predicates: Counter[str] = Counter()
    pages_over_entity_budget = []
    pages_over_relation_budget = []
    reserved_mentions_relations = []
    for block in pages:
        if not isinstance(block, dict):
            continue
        page = str(block.get("page", "") or "")
        entities = block.get("entities") if isinstance(block.get("entities"), list) else []
        relations = block.get("relations") if isinstance(block.get("relations"), list) else []
        base["enriched_page_count"] += 1
        base["entity_count"] += len(entities)
        semantic_relations = []
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            predicate = str(relation.get("predicate", "") or "").strip().casefold()
            if predicate == "mentions":
                reserved_mentions_relations.append(
                    {"page": page, "subject": relation.get("subject"), "object": relation.get("object")}
                )
                continue
            semantic_relations.append(relation)
            if predicate:
                predicates[predicate] += 1
        base["semantic_relation_count"] += len(semantic_relations)
        if len(entities) > _ENTITY_BUDGET_MAX:
            pages_over_entity_budget.append({"path": page, "count": len(entities)})
        if len(semantic_relations) > _RELATION_BUDGET_MAX:
            pages_over_relation_budget.append(
                {"path": page, "count": len(semantic_relations)}
            )

    singleton_predicates = [predicate for predicate, count in predicates.items() if count == 1]
    base["unique_predicate_count"] = len(predicates)
    base["singleton_predicate_count"] = len(singleton_predicates)
    base["singleton_predicates"] = _bounded_values(singleton_predicates)
    base["pages_over_entity_budget"] = _bounded_items(pages_over_entity_budget)
    base["pages_over_relation_budget"] = _bounded_items(pages_over_relation_budget)
    base["reserved_mentions_relations"] = _bounded_items(reserved_mentions_relations)
    base["predicate_counts"] = [
        {"predicate": predicate, "count": count}
        for predicate, count in sorted(predicates.items(), key=lambda item: (-item[1], item[0]))[
            :_HEALTH_SAMPLE_LIMIT
        ]
    ]
    return base


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
        "tag_health": {},
        "enrichment_health": {},
        "_meta": {
            "raw_distance_only": True,
            "writes": "none — agent does writes in SKILL.md workflow",
        },
    }
    if not bundle.is_dir():
        report["_meta"]["error"] = f"bundle path is not a directory: {bundle}"
        return report

    concepts = okflib.list_concepts(bundle)
    report["tag_health"] = _tag_health(bundle, concepts)
    report["enrichment_health"] = _enrichment_health(bundle)
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
