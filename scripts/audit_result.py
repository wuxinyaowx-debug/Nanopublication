#!/usr/bin/env python3
"""Audit a nanopublication-style result and export assertions as JSONL."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from bind_evidence import TOOL_VERSION, line_span, normalize

RELATION_TYPES = {
    "quantitative_measurement", "comparative_effect", "association",
    "causal_effect", "absence_of_detected_effect", "characterization",
    "mechanism", "procedural", "limitation", "other",
}
STATUSES = {"success", "partial", "unable_to_judge", "refused", "failed"}
EPISTEMIC_STATUSES = {"reported", "derived", "inferred", "unsupported", "contradicted"}
SUPPORT_TYPES = {"direct", "derived", "inferred", "conflicting", "none"}
CONFIDENCE_LEVELS = {"high", "moderate", "low"}
JSON_TYPES = {
    "object": dict, "array": list, "string": str, "number": (int, float),
    "integer": int, "boolean": bool, "null": type(None),
}


class Audit:
    def __init__(self) -> None:
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []

    def error(self, path: str, code: str, message: str) -> None:
        self.errors.append({"path": path, "code": code, "message": message})

    def warn(self, path: str, code: str, message: str) -> None:
        self.warnings.append({"path": path, "code": code, "message": message})


def load_index(path: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[Tuple[str, Any], Dict[str, Any]]]:
    sources: Dict[str, Dict[str, Any]] = {}
    records: Dict[Tuple[str, Any], Dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        source_id = record.get("source_id")
        if not isinstance(source_id, str):
            raise ValueError(f"source index line {line_number} has no source_id")
        sources[source_id] = record
        records[(source_id, record.get("page"))] = record
    return sources, records


def output_contract(case: Dict[str, Any], audit: Audit) -> Tuple[List[str], Dict[str, Any]]:
    contract = case.get("output_contract")
    if contract is None:
        audit.warn("output_contract", "contract_unavailable", "case.json has no machine-readable output_contract; only core fields were checked")
        return [], {}
    if isinstance(contract, list):
        return [item for item in contract if isinstance(item, str)], {}
    if not isinstance(contract, dict):
        audit.warn("output_contract", "contract_not_machine_readable", "Output contract was not a JSON object or field list; inspect task.md manually")
        return [], {}
    properties: Dict[str, Any] = {}
    required: List[str] = []
    if isinstance(contract.get("properties"), dict):
        properties = contract["properties"]
        # In JSON Schema, properties are optional unless listed in required.
        required = [item for item in contract.get("required", []) if isinstance(item, str)] if isinstance(contract.get("required"), list) else []
    elif isinstance(contract.get("fields"), list):
        for item in contract["fields"]:
            if isinstance(item, str):
                required.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                required.append(item["name"])
                properties[item["name"]] = item
    elif isinstance(contract.get("required"), list):
        required = [item for item in contract["required"] if isinstance(item, str)]
    else:
        wrappers = {"title", "description", "type", "$schema", "additionalProperties"}
        candidate_keys = [key for key in contract if key not in wrappers]
        if candidate_keys and all(isinstance(contract[key], (dict, list, str)) for key in candidate_keys):
            required = candidate_keys
            properties = {key: contract[key] for key in candidate_keys if isinstance(contract[key], dict)}
        else:
            audit.warn("output_contract", "contract_shape_needs_manual_review", "Could not infer top-level contract fields; apply the full original contract manually")
    return list(dict.fromkeys(required)), properties


def check_json_type(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(check_json_type(value, option) for option in expected)
    if not isinstance(expected, str) or expected not in JSON_TYPES:
        return True
    if expected in {"integer", "number"} and isinstance(value, bool):
        return False
    return isinstance(value, JSON_TYPES[expected])


def validate_schema(value: Any, schema: Any, path: str, audit: Audit) -> None:
    """Validate deterministic JSON-Schema subset used by output contracts."""
    if not isinstance(schema, dict):
        return
    expected = schema.get("type")
    if isinstance(expected, str) and expected not in JSON_TYPES:
        audit.warn(path + ".type", "unsupported_schema_type", f"Unknown JSON type {expected!r}; inspect manually")
    if isinstance(expected, list):
        for option in expected:
            if not isinstance(option, str) or option not in JSON_TYPES:
                audit.warn(path + ".type", "unsupported_schema_type", f"Unknown JSON type option {option!r}; inspect manually")
    if expected is not None and not check_json_type(value, expected):
        audit.error(path, "contract_type_mismatch", f"Expected JSON type {expected}")
        return
    if "const" in schema and value != schema["const"]:
        audit.error(path, "contract_const_mismatch", f"Expected constant value {schema['const']!r}")
    if isinstance(schema.get("enum"), list) and value not in schema["enum"]:
        audit.error(path, "contract_enum_mismatch", f"Value is not in the contract enum {schema['enum']!r}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    audit.error(f"{path}.{key}", "contract_field_missing", "Nested required output_contract field is missing")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value:
                    validate_schema(value[key], child_schema, f"{path}.{key}", audit)
            additional = schema.get("additionalProperties")
            if additional is False:
                for key in value:
                    if key not in properties:
                        audit.error(f"{path}.{key}", "contract_additional_field", "Field is forbidden by additionalProperties: false")
            elif isinstance(additional, dict):
                for key in value:
                    if key not in properties:
                        validate_schema(value[key], additional, f"{path}.{key}", audit)
    if isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                validate_schema(item, items, f"{path}[{index}]", audit)
        elif isinstance(items, list):
            for index, child_schema in enumerate(items[:len(value)]):
                validate_schema(value[index], child_schema, f"{path}[{index}]", audit)

    for keyword in ("$ref", "oneOf", "anyOf", "not", "pattern", "minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength"):
        if keyword in schema:
            audit.warn(path, "unsupported_contract_constraint", f"Constraint {keyword!r} requires manual validation by the Agent")
    if isinstance(schema.get("allOf"), list):
        for child_schema in schema["allOf"]:
            validate_schema(value, child_schema, path, audit)


def audit_contract(result: Dict[str, Any], case: Optional[Dict[str, Any]], audit: Audit) -> None:
    if case is None:
        return
    expected_case_id = case.get("case_id")
    if expected_case_id is not None and result.get("case_id") != expected_case_id:
        audit.error("case_id", "case_id_mismatch", "Result case_id must exactly match case.json case_id")
    contract = case.get("output_contract")
    schema_keywords = {"type", "properties", "required", "items", "enum", "const", "allOf", "anyOf", "oneOf", "$ref", "$schema", "additionalProperties"}
    if isinstance(contract, dict) and schema_keywords.intersection(contract):
        validate_schema(result, contract, "result", audit)
        return
    required, properties = output_contract(case, audit)
    for key in required:
        if key not in result:
            audit.error(key, "contract_field_missing", "Top-level output_contract field is missing")
        elif key in properties:
            validate_schema(result[key], properties[key], key, audit)


def audit_sources(result: Dict[str, Any], index_sources: Dict[str, Dict[str, Any]], audit: Audit) -> Dict[str, Dict[str, Any]]:
    source_items = result.get("sources")
    if not isinstance(source_items, list):
        audit.error("sources", "invalid_sources", "sources must be an array")
        return {}
    declared: Dict[str, Dict[str, Any]] = {}
    for index, source in enumerate(source_items):
        path = f"sources[{index}]"
        if not isinstance(source, dict):
            audit.error(path, "invalid_source", "Source must be an object")
            continue
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            audit.error(path + ".source_id", "missing_source_id", "Source ID is required")
            continue
        if source_id in declared:
            audit.error(path + ".source_id", "duplicate_source_id", source_id)
        declared[source_id] = source
        for field in ("source_path", "sha256", "extraction_method"):
            if not isinstance(source.get(field), str) or not source.get(field):
                audit.error(path + "." + field, "missing_source_field", f"{field} must be a nonempty string")
        if source_id not in index_sources:
            audit.error(path + ".source_id", "source_not_indexed", source_id)
        else:
            indexed = index_sources[source_id]
            for field in ("source_path", "sha256"):
                if source.get(field) != indexed.get(field):
                    audit.error(path + "." + field, "source_index_mismatch", f"Does not match indexed {field}")
        if "authors" in source and not isinstance(source["authors"], list):
            audit.error(path + ".authors", "invalid_authors", "authors must be an array")
    return declared


def audit_evidence(
    evidence: Dict[str, Any], path: str, records: Dict[Tuple[str, Any], Dict[str, Any]],
    declared_sources: Dict[str, Dict[str, Any]], audit: Audit,
) -> Optional[str]:
    source_id = evidence.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        audit.error(path + ".source_id", "missing_source_id", "Evidence source_id is required")
        return None
    if source_id not in declared_sources:
        audit.error(path + ".source_id", "source_not_declared", "Evidence source must also occur in result.sources")
    if source_id not in {key[0] for key in records}:
        audit.error(path + ".source_id", "source_not_indexed", source_id)
        return source_id
    locator = evidence.get("locator")
    if not isinstance(locator, dict):
        audit.error(path + ".locator", "missing_locator", "Run bind_evidence.py before auditing")
        return source_id
    page = locator.get("page")
    record = records.get((source_id, page))
    if record is None:
        audit.error(path + ".locator.page", "unknown_page", f"No indexed record for page {page!r}")
        return source_id
    if locator.get("source_id") != source_id:
        audit.error(path + ".locator.source_id", "locator_source_mismatch", "Locator source_id must equal evidence.source_id")
    if locator.get("source_path") != record.get("source_path"):
        audit.error(path + ".locator.source_path", "locator_path_mismatch", "Locator source_path must match the indexed source")
    if "page" in evidence and evidence.get("page") != page:
        audit.error(path + ".page", "evidence_page_mismatch", "Top-level evidence.page and locator.page must agree")
    quote = evidence.get("quote")
    evidence_type = evidence.get("evidence_type", "text")
    if not isinstance(quote, str) or not quote.strip():
        if evidence_type == "visual" or evidence.get("visual_description"):
            if not isinstance(evidence.get("visual_description"), str) or not evidence.get("visual_description"):
                audit.error(path + ".visual_description", "missing_visual_description", "Visual evidence needs an observation and region")
            if evidence.get("verification_status") != "requires_visual_review" or locator.get("verification_status") != "requires_visual_review" or locator.get("match_type") != "visual_manual":
                audit.error(path + ".verification_status", "invalid_visual_status", "Visual statuses and match type must agree on visual_manual/requires_visual_review")
            if not isinstance(evidence.get("region"), str) or not evidence.get("region").strip():
                audit.error(path + ".region", "missing_visual_region", "Visual evidence requires an inspected region")
            if not isinstance(evidence.get("figure_label"), str) or not evidence.get("figure_label").strip():
                audit.error(path + ".figure_label", "missing_figure_label", "Visual evidence requires a figure/panel or standalone-image label")
            audit.warn(path, "visual_review_required", "Confirm that an Agent actually inspected this visual region; scripts verify only the source/page")
        else:
            audit.error(path + ".quote", "empty_quote", "Textual evidence requires a quote")
        return source_id
    if evidence.get("verification_status") != "verified" or locator.get("verification_status") != "verified":
        audit.error(path + ".verification_status", "unverified_text", "Run binder and resolve quotation errors")
        return source_id
    start = locator.get("char_start")
    end = locator.get("char_end")
    if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or start < 0 or end <= start or end > len(record.get("text", "")):
        audit.error(path + ".locator", "invalid_offsets", "Offsets must be valid zero-based, end-exclusive integers")
        return source_id
    raw_excerpt = record["text"][start:end]
    match_type = locator.get("match_type")
    if match_type == "exact":
        if raw_excerpt != quote:
            audit.error(path + ".locator", "exact_offset_mismatch", "Offsets do not recover the exact quote")
    elif match_type == "normalized":
        if normalize(raw_excerpt).strip() != normalize(quote).strip():
            audit.error(path + ".locator", "normalized_offset_mismatch", "Offsets do not recover a normalized quote match")
        audit.warn(path, "normalized_match", "Layout-tolerant match used; visually check consequential symbols and wording")
    else:
        audit.error(path + ".locator.match_type", "invalid_match_type", "Expected exact or normalized for textual evidence")
    # The raw-span checks above are authoritative. Re-normalizing the entire
    # page would add surrounding context and can change boundary dehyphenation.
    expected_lines = line_span(record, start, end)
    if (locator.get("line_start"), locator.get("line_end")) != expected_lines:
        audit.error(path + ".locator", "line_mismatch", f"Expected lines {expected_lines[0]}–{expected_lines[1]}")
    if evidence_type == "visual":
        audit.error(path + ".evidence_type", "visual_mislabeled_as_text", "Visual evidence cannot be certified through a text quote")
    return source_id


def audit_assertions(
    result: Dict[str, Any], records: Dict[Tuple[str, Any], Dict[str, Any]],
    declared_sources: Dict[str, Dict[str, Any]], audit: Audit,
) -> List[Dict[str, Any]]:
    assertions = result.get("assertions")
    if not isinstance(assertions, list):
        audit.error("assertions", "invalid_assertions", "assertions must be an array")
        return []
    if not assertions and result.get("status") == "success":
        audit.warn("assertions", "no_assertions", "Successful result contains no assertions; confirm that the task did not require claim extraction or explain why none are supportable")
    required = ("id", "text", "subject", "relation", "relation_type", "object", "conditions", "epistemic_status", "support_type", "evidence", "source_ids", "confidence", "uncertainty")
    seen_ids: Dict[str, int] = {}
    texts: Dict[str, List[int]] = defaultdict(list)
    valid_objects: List[Dict[str, Any]] = []
    for index, assertion in enumerate(assertions):
        path = f"assertions[{index}]"
        if not isinstance(assertion, dict):
            audit.error(path, "invalid_assertion", "Assertion must be an object")
            continue
        valid_objects.append(assertion)
        for field in required:
            if field not in assertion:
                audit.error(path + "." + field, "missing_assertion_field", "Required field is absent")
        assertion_id = assertion.get("id")
        if not isinstance(assertion_id, str) or not assertion_id:
            audit.error(path + ".id", "invalid_assertion_id", "Assertion ID must be a nonempty string")
        elif assertion_id in seen_ids:
            audit.error(path + ".id", "duplicate_assertion_id", f"Already used by assertions[{seen_ids[assertion_id]}]")
        else:
            seen_ids[assertion_id] = index
        for field in ("text", "subject", "relation"):
            if not isinstance(assertion.get(field), str) or not assertion.get(field).strip():
                audit.error(path + "." + field, "invalid_text_field", f"{field} must be a nonempty string")
        if isinstance(assertion.get("text"), str):
            texts[normalize(assertion["text"])].append(index)
        if assertion.get("relation_type") not in RELATION_TYPES:
            audit.error(path + ".relation_type", "invalid_relation_type", "Use a type from references/field_dictionary.md")
        if assertion.get("epistemic_status") not in EPISTEMIC_STATUSES:
            audit.error(path + ".epistemic_status", "invalid_epistemic_status", "Unrecognized epistemic status")
        if assertion.get("support_type") not in SUPPORT_TYPES:
            audit.error(path + ".support_type", "invalid_support_type", "Unrecognized support type")
        if not isinstance(assertion.get("conditions"), dict):
            audit.error(path + ".conditions", "invalid_conditions", "conditions must be an object, empty only when no conditions apply")
        confidence = assertion.get("confidence")
        if not isinstance(confidence, dict) or confidence.get("level") not in CONFIDENCE_LEVELS or not isinstance(confidence.get("basis"), str) or not confidence.get("basis").strip():
            audit.error(path + ".confidence", "invalid_confidence", "confidence requires level high/moderate/low and a nonempty alignment basis")
        if not isinstance(assertion.get("uncertainty"), list):
            audit.error(path + ".uncertainty", "invalid_uncertainty", "uncertainty must be an array")
        evidence_items = assertion.get("evidence")
        evidence_source_ids: List[str] = []
        if not isinstance(evidence_items, list):
            audit.error(path + ".evidence", "invalid_evidence", "evidence must be an array")
        else:
            if not evidence_items and not (assertion.get("support_type") == "none" and assertion.get("epistemic_status") == "unsupported"):
                audit.error(path + ".evidence", "unsupported_assertion", "Only explicitly unsupported assertions may lack evidence")
            for evidence_index, evidence in enumerate(evidence_items):
                evidence_path = f"{path}.evidence[{evidence_index}]"
                if not isinstance(evidence, dict):
                    audit.error(evidence_path, "invalid_evidence", "Evidence item must be an object")
                    continue
                evidence_id = audit_evidence(evidence, evidence_path, records, declared_sources, audit)
                if evidence_id:
                    evidence_source_ids.append(evidence_id)
            expected_sources = list(dict.fromkeys(evidence_source_ids))
            if assertion.get("source_ids") != expected_sources:
                audit.error(path + ".source_ids", "source_link_mismatch", f"Expected unique evidence source IDs in first-use order: {expected_sources}")
        if assertion.get("epistemic_status") == "derived":
            derivation = assertion.get("derivation")
            if not isinstance(derivation, dict) or not derivation.get("operation") or not derivation.get("inputs") or not (derivation.get("code") or derivation.get("formula")):
                audit.error(path + ".derivation", "missing_derivation", "Derived assertions require operation, inputs, and code or formula")
        text = assertion.get("text")
        if isinstance(text, str) and re.search(r"\s+(?:and|but|whereas|while)\s+|；|，并且|，同时|以及", text, flags=re.IGNORECASE):
            audit.warn(path + ".text", "atomicity_review", "Coordination detected; verify that this is one relation with shared qualifiers, not multiple assertions")
    for text, indices in texts.items():
        if text and len(indices) > 1:
            audit.warn(f"assertions[{indices[1]}].text", "possible_duplicate", f"Normalized text duplicates assertions at {indices}; merge or distinguish conditions")
    return valid_objects


def audit_uncertainties_and_changes(result: Dict[str, Any], audit: Audit) -> None:
    uncertainties = result.get("uncertainties")
    if not isinstance(uncertainties, list):
        audit.error("uncertainties", "invalid_uncertainties", "uncertainties must be an array")
    else:
        for index, item in enumerate(uncertainties):
            if not isinstance(item, dict) or not item.get("type") or not item.get("description") or not item.get("resolution"):
                audit.error(f"uncertainties[{index}]", "incomplete_uncertainty", "Requires type, description, and resolution")
    changes = result.get("change_records")
    if not isinstance(changes, list):
        audit.error("change_records", "invalid_change_records", "change_records must be an array")
    else:
        for index, item in enumerate(changes):
            if not isinstance(item, dict) or not item.get("action") or not item.get("reason"):
                audit.error(f"change_records[{index}]", "incomplete_change_record", "Requires action and reason; record only actual changes")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--contract", type=Path, help="Optional case.json for output_contract checks")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--jsonl", type=Path)
    args = parser.parse_args(argv)

    result = json.loads(args.result.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("result root must be a JSON object")
    case = json.loads(args.contract.read_text(encoding="utf-8")) if args.contract else None
    index_sources, records = load_index(args.sources)
    audit = Audit()

    if not isinstance(result.get("case_id"), str) or not result.get("case_id"):
        audit.error("case_id", "missing_case_id", "case_id must be a nonempty string")
    status = result.get("status")
    if status not in STATUSES:
        audit.error("status", "invalid_status", f"Expected one of {sorted(STATUSES)}")
    if status not in {"success", None} and not result.get("status_reason"):
        audit.error("status_reason", "missing_status_reason", "Non-success status needs an actionable reason")
    audit_contract(result, case, audit)
    declared_sources = audit_sources(result, index_sources, audit)
    assertions = audit_assertions(result, records, declared_sources, audit)
    audit_uncertainties_and_changes(result, audit)

    report = {
        "schema_version": "quality-report-1.0",
        "tool_version": TOOL_VERSION,
        "status": "error" if audit.errors else ("warning" if audit.warnings else "success"),
        "case_id": result.get("case_id"),
        "assertion_count": len(assertions),
        "error_count": len(audit.errors),
        "warning_count": len(audit.warnings),
        "errors": audit.errors,
        "warnings": audit.warnings,
        "semantic_entailment_verified": False,
        "visual_content_verified": False,
        "note": "Automated checks cover structure and text locations. Agent semantic review and visual inspection remain necessary.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.jsonl:
        args.jsonl.parent.mkdir(parents=True, exist_ok=True)
        args.jsonl.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in assertions), encoding="utf-8")
    print(json.dumps({"status": report["status"], "errors": len(audit.errors), "warnings": len(audit.warnings), "assertions": len(assertions)}, ensure_ascii=False))
    return 2 if audit.errors else 0


if __name__ == "__main__":
    sys.exit(main())
