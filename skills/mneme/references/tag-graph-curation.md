---
type: Reference
title: Tag and Graph enrichment curation
description: Bundle-local vocabulary and extraction guidance that keeps navigation useful without turning every phrase into metadata.
tags: [mneme, curation, graph]
---

# Tag and Graph enrichment curation

Load this reference while preparing a dream preview that adds or changes tags,
entities, or semantic relations. These are Mneme producer guidelines, not OKF v0.1 validity rules.
Existing external bundles remain consumable when they do not follow them.

## Put each fact in the narrowest useful place

Use this decision order:

1. Put the page's document role in `type`.
2. Put source identity in `resource` or a link to an OKF `Source` page.
3. Use a tag only for a reusable cross-page facet a reader may browse or filter.
4. Extract an entity only when the concept is worth finding across pages.
5. Extract a semantic relation only when the page provides evidence for a
   query-worthy connection between two entities.
6. Leave everything else in body text.

Do not encode the same distinction in `type`, tags, entity names, and relation
predicates. Metadata should improve navigation rather than restate every noun.

## Curate a bundle-local tag vocabulary

- Prefer 1-3 tags per Mneme-written page. Use at most 4 unless the page truly
  spans more reusable facets.
- Reuse the bundle's existing spelling before introducing a new tag. Read
  `index.md`, related pages, and the dream audit's `tag_health` summary first.
- Prefer stable subject facets such as `retrieval`, `evaluation`, or
  `context-engineering`. Avoid transient wording, page slugs, author or book
  identity, and tags that merely repeat `type: Source` or another page field.
- Do not duplicate a tag within one page. Treat case-only and punctuation-only
  variants as vocabulary drift and choose the established form.
- A singleton tag is not automatically wrong. Keep it when it names a durable
  facet likely to recur; otherwise leave that detail in the body or reuse a
  broader established tag.
- Do not build a fixed global taxonomy or mirror every tag into `tags/*.md`.
  Let vocabulary evolve inside the bundle. Create an ordinary `Topic` page only
  when readers need a maintained thematic map.

## Extract a sparse, reusable semantic graph

- Prefer 3-6 reusable entities and 2-5 evidence-backed semantic relations for
  an enriched page. Fewer is valid when the source is narrow; these are quality
  budgets, not quotas.
- Reuse an existing entity's canonical name and type when it denotes the same
  thing. Do not create separate entities for capitalization, pluralization, an
  acronym, or a page-title variation unless the distinction is meaningful.
- Use short canonical predicates in one direction, for example `depends_on`,
  `implements`, `evaluates`, `mitigates`, or `part_of`. Before inventing one,
  inspect predicates already reported by `enrichment_health`.
- Choose one direction for a relationship. Do not emit both `mitigates` and
  `is_mitigated_by`, or drift among `applies`, `applied_to`, and `applied_by`,
  unless those predicates carry genuinely different meanings in this bundle.
- Include concise evidence grounded in the source page and a calibrated
  confidence. Do not infer a relation merely because two entities co-occur.
- Never emit `mentions` in extraction JSON. `graph ingest` creates `mentions`
  edges automatically as provenance from a page to its extracted entities.
- Tags and entities may overlap only when both views earn their keep: a tag is
  a broad browsing facet, while an entity participates in specific relations.

## Review the preview

Before asking for write approval, compare proposed metadata with the audit:

- duplicate tags and pages over the tag budget;
- singleton-heavy tag vocabulary and near-duplicate spellings;
- pages over entity or relation budgets;
- singleton predicates and competing predicate directions;
- any manually proposed `mentions` relation.

Explain intentional exceptions in the preview. Never auto-delete or rename
existing tags, entities, or predicates from these signals; vocabulary cleanup
changes navigation semantics and requires explicit user approval.
