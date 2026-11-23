---
name: nanopublication-evidence-binder
description: Extract atomic scientific assertions from supplied papers or research materials, bind each assertion to verbatim page- or line-located evidence, preserve source metadata and uncertainty, validate the evidence graph, and emit machine-readable nanopublication-style JSON. Use for evidence-grounded paper reading, claim extraction, scientific question answering, translation with traceable support, assertion verification, and structured research-knowledge export.
---

# Nanopublication Evidence Binder

Produce a faithful, reviewable representation of the **actual supplied material**, not a reconstruction from prior knowledge. A verified quotation establishes textual fidelity and location; it does not by itself establish that the source's scientific conclusion is true.

## Runtime contract and priorities

1. Read `/input/task.md` and `/input/case.json` first. Identify the requested reading action, all files and figures in scope, `case_id`, and the complete `output_contract`. Reproduce every contract field, nested structure, and required data type in `/app/output/result.json`; add traceability fields without replacing contract fields. If the contract conflicts with these examples, follow the contract.
2. Work only in `/app/work`; put final deliverables in `/app/output`. Create an honest partial `result.json` as soon as the contract is understood, then improve it. Never silently substitute filename labels or domain expectations for document content.
3. The skill is installed at `/skills/weekly-skill`. Scripts use Python 3 and the standard library; PDF extraction uses an available `pdftotext`, `pypdf`, or `fitz` backend. No installation or network access is required.
4. Do not fabricate metadata, values, missing pages, visual observations, benchmark results, or verification. Use `null`, an empty collection, and an explanatory uncertainty when information is absent. Distinguish `not_reported`, `not_determinable`, `source_conflict`, `extraction_failure`, and `not_applicable`.

## Workflow

### 1. Inventory and index the sources

Run:

```bash
python /skills/weekly-skill/scripts/index_sources.py --input /input --out /app/work/sources.jsonl --manifest /app/work/source_manifest.json
```

The script writes one UTF-8 JSON object per PDF page, text document, or standalone visual attachment, with stable source IDs and SHA-256 hashes. Text records include page labels, numbered lines, and extracted text; visual records remain empty until inspected. Root-level `case.json` and `task.md` are task instructions, not scientific evidence. For large attachments, inspect the manifest and prioritize the material required by the task, but do not ignore an attachment that may qualify or contradict a claim.

If PDF text is sparse or extraction fails, inspect the page image and use the provided PDF-rendering/OCR tools. Preserve printed/PDF page identity. Re-index any OCR text actually used for quotations and record `extraction_method: "ocr"` in the source metadata. Do not claim that a scanned table or figure was read unless its image was inspected. Multi-column layouts, hyphenation, symbols, and superscripts require visual checking when consequential.

Read `references/field_dictionary.md` before constructing output and `references/extraction_rules.md` before splitting or judging assertions.

### 2. Read first, then form an analysis plan

Read the abstract, relevant results/conclusions, methods and limitations needed to interpret scope, plus all cited figure/table captions. Record bibliographic metadata only when present in supplied material or a retrieved source that was actually read. Authors are a list; year and version remain `null` if unknown. Preserve DOI or other identifiers exactly; never guess them.

If the task asks a question or translation, answer that task in its required fields. Create assertions for the material scientific propositions needed to support the answer. Do not replace a requested answer with a generic list of assertions. For a quotation or translation, keep the original wording in evidence and the translated wording in the requested answer; a translation is not a verbatim quotation.

### 3. Split assertions without changing their strength

Each assertion must be independently truth-apt: one subject, one principal relation, and one object/comparison under an explicit shared condition set. Split coordinated outcomes, multiple populations, multiple time points, or separate causal steps. Do not split a quantitative relation away from the comparator, unit, time point, uncertainty interval, or study population required to interpret it.

Preserve the source's modality and strength: association is not causation, a prespecified result is not generalized beyond its population, “no detected difference” is not equivalence, and a proposed mechanism is not an established mechanism. Distinguish source-reported findings (`reported`), deterministic recalculation from quoted inputs (`derived`), agent interpretation (`inferred`), and unsupported or contradicted statements. Do not create an unsupported assertion merely to complete a template.

Use concise standalone text and a separate structured `subject`, `relation`, `object`, and `conditions`. Controlled relation types and field rules are in the field dictionary. Assertion IDs may be omitted in the draft: the binder assigns deterministic IDs. Merge only exact semantic duplicates; retain multiple evidence records when independent passages support the same assertion.

### 4. Bind minimal sufficient evidence

For each assertion, copy one or more **contiguous verbatim spans** from the indexed source into `evidence[].quote`; identify each with `source_id`, and `page` when known. Never assemble disconnected words with ellipses and present them as a contiguous quote. Use separate evidence items for noncontiguous spans.

The evidence set must jointly contain the participants/subject, relation direction, object/outcome, decisive numerical values and units, and all qualifications used in the assertion. Prefer the results passage over an abstract-only summary when they differ. A citation to a whole page is insufficient when a precise quote is available. For a table, include header/units and the relevant row as separate spans. For a purely visual figure, supply page, figure label, inspected region, and `visual_description`; leave `quote` empty and mark the evidence type `visual`. Visual evidence remains `requires_visual_review` after automated binding.

Do not use a citation to another paper as direct evidence for what the current study measured unless the current paper explicitly attributes that statement to the citation. For a derived assertion, quote every input and provide `derivation.operation`, `inputs`, and reproducible code or formula. Never relabel arithmetic as a source-reported value.

Bind locations deterministically:

```bash
python /skills/weekly-skill/scripts/bind_evidence.py --result /app/work/result.draft.json --sources /app/work/sources.jsonl --output /app/work/result.bound.json --report /app/work/binding_report.json
```

Resolve every binding error. Normalized matches tolerate layout whitespace, Unicode equivalents, and line-break hyphenation; inspect consequential matches rather than treating normalization as permission to paraphrase evidence. Ambiguous matches require an explicit page and/or a 1-based `occurrence`; the binder always records the actual matched page in the locator. Repeat binding after any quote or page edit.

### 5. Audit semantics and completeness

For every assertion, perform and record a brief evidence-alignment decision:

- **Atomicity:** Can this proposition be false in one part while another remains true? If yes, split it, unless the parts are necessary qualifiers of one relation.
- **Entailment:** Does the quoted evidence explicitly support the full assertion, including direction and scope? Textual overlap alone is insufficient.
- **Direction and attribution:** Are intervention/comparator, exposure/outcome, and current-study/prior-work roles correct?
- **Granularity:** Are effect estimates, intervals, sample size or time point attached to the correct result when reported and needed?
- **Strength:** Do `epistemic_status`, `relation_type`, and confidence rationale reproduce the source rather than strengthen it?
- **Boundary:** Are missing information, conflicting passages, indirect inference, and uninspected visuals explicit?

Report conflicting source passages as separate evidence or uncertainty records; do not silently select the convenient one. Confidence describes evidence-to-assertion alignment, not probability that a scientific phenomenon is real. A direct, complete, correctly located quotation can have high alignment confidence even when the underlying experiment remains uncertain.

### 6. Export and validate

Ensure `/app/output/result.json` contains the original `case_id`, every `output_contract` field, `status`, `sources`, `assertions`, `uncertainties`, and `change_records`. Also keep direct answers/translations requested by the task. Use status `success` only when all required parts and evidence checks pass; otherwise use `partial`, `unable_to_judge`, `refused`, or `failed` with actionable reasons.

Run:

```bash
python /skills/weekly-skill/scripts/audit_result.py --result /app/work/result.bound.json --sources /app/work/sources.jsonl --contract /input/case.json --output /app/output/result.json --report /app/output/quality_report.json --jsonl /app/output/assertions.jsonl
```

The audit fails on missing core fields, unresolved/ambiguous quotations, unverified visual evidence presented as text, invalid source links, duplicate IDs, and deterministic contract problems. Warnings require review but are not automatically scientific errors. Never weaken or remove an uncertainty merely to obtain a clean audit. If a task requires an assertion but the material cannot support it, return no such factual assertion and explain the gap.

## Failure handling

- **No readable PDF text:** retain a partial result, identify affected pages, inspect/render and OCR if available; do not infer content from the abstract.
- **Figure/table-only evidence:** inspect the visual and identify page, figure/table, and region. Mark any uninspected element as unavailable.
- **No direct support:** set the relevant answer to not determinable and explain the missing premise; do not promote an inference to `reported`.
- **Source conflict:** preserve both statements and locations; explain which task criterion determines what the answer can conclude.
- **Schema conflict:** prioritize the original contract and record any unavoidable extra fields in change records.
- **Repeated identical extraction failure:** stop repeated retries, save partial output with the exact blocker and the manual intervention point.

## Scope and limitations

This workflow verifies source linkage and internal consistency, not experimental validity, reproducibility, or external scientific truth. Exact text matching may be affected by OCR and PDF encoding, and automated atomicity checks are heuristic. Semantic sufficiency and figure interpretation require model review. The JSON is nanopublication-style structured output; it does not claim cryptographic trusty URIs or publication to a nanopublication server.
