# Nanopublication Evidence Binder

A runtime-neutral Agent Skill for atomic scientific claim extraction, minimal-evidence binding, source traceability, and validated JSON/JSONL export. It processes supplied documents at run time and contains no prepared answers for evaluation cases.

## Contents

- `SKILL.md`: Agent procedure and failure behavior.
- `references/field_dictionary.md`: output schema, controlled relation types, and evidence fields.
- `references/extraction_rules.md`: atomicity, strength, scope, conflict, and visual-evidence rules.
- `scripts/index_sources.py`: page/line source index with stable IDs and hashes.
- `scripts/bind_evidence.py`: deterministic quotation matching and locator population.
- `scripts/audit_result.py`: structural, contract, duplicate, and evidence-chain audit plus JSONL export.
- `examples/`: explicitly synthetic reusable samples and a minimal invocation example.

## Runtime

Python 3.9+; scripts otherwise use only the standard library. PDF indexing selects `pdftotext` (preferred), `pypdf`, or `fitz`, whichever is installed. Official challenge runners provide PDF parsing/rendering tools. No network access, credentials, package installation, personal paths, or external databases are required for text inputs.

In the challenge image the Skill is mounted at `/skills/weekly-skill`. Inputs are `/input/case.json`, `/input/task.md`, and supplied materials. Work in `/app/work`; write final files to `/app/output`.

## Minimal invocation

```bash
python /skills/weekly-skill/scripts/index_sources.py \
  --input /input \
  --out /app/work/sources.jsonl \
  --manifest /app/work/source_manifest.json
```

After the Agent reads the actual task and sources and creates `/app/work/result.draft.json`:

```bash
python /skills/weekly-skill/scripts/bind_evidence.py \
  --result /app/work/result.draft.json \
  --sources /app/work/sources.jsonl \
  --output /app/work/result.bound.json \
  --report /app/work/binding_report.json

python /skills/weekly-skill/scripts/audit_result.py \
  --result /app/work/result.bound.json \
  --sources /app/work/sources.jsonl \
  --contract /input/case.json \
  --output /app/output/result.json \
  --report /app/output/quality_report.json \
  --jsonl /app/output/assertions.jsonl
```

`--contract` is optional but recommended: it checks fields declared by `output_contract`, recursively validating `required`, `properties`, `items`, `type` unions, `enum`, `const`, `allOf`, and `additionalProperties`. Unsupported constraints such as `$ref`, `oneOf`, regular-expression patterns, and numeric/length bounds produce explicit warnings for Agent review. If `case.json` stores a nonstandard schema, the Agent must still apply the full original contract itself.

## Verification semantics

A `verified` locator means the quote matches the cited indexed text exactly or under documented normalization. It does **not** mean the quotation semantically entails the assertion, and it does not validate the underlying experiment. The Agent must perform the semantic checklist in `SKILL.md`. Visual evidence remains marked for visual review; no script in this package claims image understanding.

The scripts fail loudly for missing sources, ambiguous pages, broken evidence chains, duplicate IDs, and missing required fields. Atomicity warnings are heuristic. A clean audit is necessary for the designed pipeline, not sufficient for scientific correctness.

## Reuse and adaptation

The deterministic evidence binder can be reused independently of an Agent by supplying the documented JSON structures. Adapt the controlled relation vocabulary to a domain only by extending the dictionary; do not silently map distinct relations to an inaccurate generic type. IDs are content-based for repeatability, not nanopublication trusty URIs. This package does not publish records to a nanopublication server.

Maintenance checks: rerun the synthetic self-test after code changes; test scanned pages, multi-column PDFs, blank text layers, table headers, duplicate quotes on several pages, figure-only evidence, conflicting passages, and missing output-contract fields before release.
