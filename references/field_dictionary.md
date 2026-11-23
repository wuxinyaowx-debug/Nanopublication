# Field dictionary

## Result envelope

`result.json` is one JSON object. Preserve all fields and types in the case's `output_contract`; the following fields are the traceability layer.

| Field | Type | Meaning |
|---|---|---|
| `case_id` | string | Copied exactly from `case.json`. |
| `status` | enum | `success`, `partial`, `unable_to_judge`, `refused`, or `failed`. |
| `status_reason` | string/null | Actionable explanation for any non-success state; null for unqualified success. |
| `sources` | array<object> | Documents actually read or inspected. |
| `assertions` | array<object> | Atomic, evidence-linked propositions. Empty when none are requested or supportable; explain the latter. |
| `uncertainties` | array<object> | Missing data, ambiguity, conflicts, OCR/visual limitations, or inference boundaries. |
| `change_records` | array<object> | Material corrections during processing, never fabricated processing history. Include `action`, `reason`, and optionally `target_ids`/`timestamp` (UTC ISO 8601). |

A direct answer, translation, extraction table, or other requested primary result remains in its original contract field. Bind important answer components to assertion IDs where useful.

## Source record

Required: `source_id` (from the index manifest), `source_path` (input-relative path), `sha256`, and `extraction_method` (`text`, `ocr`, `visual`, or a combination explicitly described). Recommended bibliographic fields:

| Field | Type | Rule |
|---|---|---|
| `title` | string/null | Document title read from the material, not inferred from domain labels. |
| `authors` | array<string> | Preserve source order; empty if unavailable. |
| `year` | integer/string/null | Year explicitly supported by the material; null if unknown. |
| `version` | string/null | Version/revision actually identified in the material. |
| `identifiers` | object | For example `doi`, `pmid`, `arxiv`, or dataset accession. Keys with unknown values are omitted. |
| `source_url` | string/null | Only a supplied or actually retrieved URL. |
| `pages` | array<integer> | Indexed/inspected pages used for the result. |

## Assertion record

| Field | Type | Required rule |
|---|---|---|
| `id` | string | Deterministic `np_…` ID assigned by the binder if absent. Unique within the result. |
| `text` | string | Standalone, falsifiable proposition in the requested answer language. |
| `subject` | string | Entity, study group, dataset, material, or procedure acting/experiencing the relation. |
| `relation` | string | Explicit direction-bearing relationship, e.g. `decreases`, `associated_with`, `measured_as`, `reports_limitation`. |
| `relation_type` | enum | One controlled type below. |
| `object` | string/number/object | Outcome, comparator-relative result, measured value, or target. Objects carrying values should include value and unit explicitly. |
| `conditions` | object | Qualifying context. Use keys such as `population`, `intervention`, `comparator`, `outcome`, `time_point`, `dose`, `model_system`, and `statistical_test` as applicable; do not invent not-applicable values. |
| `epistemic_status` | enum | `reported`, `derived`, `inferred`, `unsupported`, or `contradicted`. Only the first two normally qualify as supported final findings. |
| `support_type` | enum | `direct`, `derived`, `inferred`, `conflicting`, or `none`. |
| `evidence` | array<object> | Minimal sufficient evidence items; empty only for unsupported/not-applicable records with an explanation. |
| `source_ids` | array<string> | Exactly the unique evidence source IDs, in stable order. |
| `confidence` | object | `level`: `high`, `moderate`, or `low`; `basis`: concise evidence-alignment reason. Not a scientific-truth probability. |
| `uncertainty` | array<string> | Assertion-specific caveats; empty if no specific caveat is needed. |
| `derivation` | object/null | Required for derived claims: `operation`, `inputs` linked to evidence indices/quoted values, and reproducible `code` or `formula`. |

### Controlled relation types

- `quantitative_measurement`: assigns a measured/estimated value with units when applicable.
- `comparative_effect`: direction or magnitude relative to a defined comparator, without claiming causality beyond the source.
- `association`: statistical association/correlation, not causal by default.
- `causal_effect`: explicit causal effect supported by the source's design and wording.
- `absence_of_detected_effect`: no detected association/difference under stated test and precision; not proof of equivalence.
- `characterization`: identity, composition, structure, property, prevalence, or descriptive phenotype.
- `mechanism`: mechanistic relation; retain whether proposed, observed, or demonstrated.
- `procedural`: what a method/protocol does or how it was performed.
- `limitation`: stated limitation, uncertainty, or restriction.
- `other`: necessary escape valve; explain why no existing type fits in the confidence basis or uncertainty.

These are epistemic relation classes, not domain ontology identifiers. Keep the original relationship in `relation`; do not force an inaccurate standardized predicate.

## Evidence item

| Field | Rule |
|---|---|
| `source_id` | Must resolve to an indexed source and appear in the result's `sources`. |
| `quote` | Contiguous verbatim text. Empty only for genuinely visual evidence. |
| `page` / `locator.page` | PDF page when known; both fields must agree. The binder computes lines and zero-based, end-exclusive character offsets. |
| `occurrence` | Optional 1-based match number in raw reading order when a quote occurs multiple times within the selected source/page scope. |
| `locator` | Binder-managed `line_start`, `line_end`, `char_start`, `char_end`, `match_type`, and `verification_status`. |
| `evidence_type` | `text`, `table`, `figure`, `caption`, `equation`, `metadata`, or `visual`. |
| `role` | `supports`, `qualifies`, `conflicts`, or `provides_input`. Multiple spans can jointly satisfy sufficiency. |
| `figure_label` / `region` | Required where applicable for figure/table/visual evidence. |
| `visual_description` | Factual description of the inspected visual evidence; never a substitute for an uninspected figure. |

The binder accepts either `page` or `locator.page`. It does not semantically certify an evidence item. `verification_status: verified` means textual location only; `requires_visual_review` means image content was not certified by the script.

## Uncertainty record

Use `type` (`not_reported`, `not_determinable`, `source_conflict`, `extraction_failure`, `ambiguous_evidence`, `unsupported_inference`, or `other`), `description`, `affected_fields` or `affected_assertion_ids`, and `resolution` (`resolved`, `open`, or `not_applicable`). Null alone is insufficient for a consequential missing value: explain it here.

## JSONL export

`assertions.jsonl` contains one complete assertion object per line in result order, encoded as UTF-8 without a header. It is a convenience export, not a replacement for `result.json`.
