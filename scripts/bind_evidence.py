#!/usr/bin/env python3
"""Bind verbatim evidence quotes to indexed pages, lines, and raw offsets."""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

TOOL_VERSION = "1.0.0"
DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")


def hangul_class(character: str) -> Optional[str]:
    codepoint = ord(character)
    if 0x1100 <= codepoint <= 0x115F or 0xA960 <= codepoint <= 0xA97C:
        return "L"
    if 0x1160 <= codepoint <= 0x11A7 or 0xD7B0 <= codepoint <= 0xD7C6:
        return "V"
    if 0x11A8 <= codepoint <= 0x11FF or 0xD7CB <= codepoint <= 0xD7FB:
        return "T"
    return None


def extend_canonical_cluster(text: str, start: int, end: int) -> int:
    """Include combining marks or Hangul Jamo composing at the span boundary."""
    while end < len(text) and unicodedata.combining(text[end]):
        end += 1
    if start >= len(text) or start >= end:
        return end
    if hangul_class(text[start]) == "L":
        if end < len(text) and hangul_class(text[end]) == "V":
            end += 1
            while end < len(text) and unicodedata.combining(text[end]):
                end += 1
            if end < len(text) and hangul_class(text[end]) == "T":
                end += 1
    elif 0xAC00 <= ord(text[start]) <= 0xD7A3 and (ord(text[start]) - 0xAC00) % 28 == 0:
        if end < len(text) and hangul_class(text[end]) == "T":
            end += 1
    while end < len(text) and unicodedata.combining(text[end]):
        end += 1
    return end


def normalized_with_map(text: str) -> Tuple[str, List[int]]:
    """Return a layout-tolerant form and a map to original character offsets.

    NFKC/case folding handles Unicode equivalents. Layout whitespace collapses.
    A hyphen at a line break between word characters is removed. Every retained
    normalized character maps to an offset in the original indexed text.
    """
    output: List[Tuple[str, int]] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            end = index + 1
            while end < len(text) and text[end].isspace():
                end += 1
            whitespace = text[index:end]
            next_index = end
            while next_index < len(text) and text[next_index] in "\u200b\u200c\u200d\ufeff":
                next_index += 1
            can_dehyphenate = (
                any(mark in whitespace for mark in "\r\n\v\f\u0085\u2028\u2029")
                and len(output) >= 2
                and output[-1][0] == "-"
                and output[-2][0].isalnum()
                and next_index < len(text)
                and unicodedata.normalize("NFKC", text[next_index]).translate(DASHES).casefold()[:1].isalnum()
            )
            if can_dehyphenate:
                output.pop()
            elif output and output[-1][0] != " ":
                output.append((" ", index))
            index = end
            continue
        if char in "\u00ad\u200b\u200c\u200d\ufeff":
            index += 1
            continue
        # Normalize a base character together with its combining marks. Doing
        # NFKC one code point at a time misses canonical equivalents such as a
        # precomposed accented character versus base + combining accent.
        cluster_end = index + 1
        if hangul_class(char) == "L" and cluster_end < len(text) and hangul_class(text[cluster_end]) == "V":
            cluster_end += 1
            if cluster_end < len(text) and hangul_class(text[cluster_end]) == "T":
                cluster_end += 1
        elif 0xAC00 <= ord(char) <= 0xD7A3 and (ord(char) - 0xAC00) % 28 == 0:
            if cluster_end < len(text) and hangul_class(text[cluster_end]) == "T":
                cluster_end += 1
        while cluster_end < len(text) and unicodedata.combining(text[cluster_end]):
            cluster_end += 1
        cluster = text[index:cluster_end]
        normalized = unicodedata.normalize("NFKC", cluster).translate(DASHES).casefold()
        for folded in normalized:
            if not folded.isspace():
                output.append((folded, index))
        index = cluster_end
    while output and output[-1][0] == " ":
        output.pop()
    return "".join(item[0] for item in output), [item[1] for item in output]


def normalize(text: str) -> str:
    return normalized_with_map(text)[0]


def all_occurrences(haystack: str, needle: str) -> List[int]:
    if not needle:
        return []
    positions: List[int] = []
    start = haystack.find(needle)
    while start >= 0:
        positions.append(start)
        start = haystack.find(needle, start + 1)
    return positions


def line_span(record: Dict[str, Any], start: int, end: int) -> Tuple[int, int]:
    starts = record.get("line_start_offsets")
    if not isinstance(starts, list) or not starts:
        starts = [0]
    line_start = bisect.bisect_right(starts, start)
    last_character = max(start, end - 1)
    line_end = bisect.bisect_right(starts, last_character)
    return max(1, line_start), max(1, line_end)



def records_by_source(records: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    paths: Dict[str, str] = {}
    for record in records:
        source_id = record.get("source_id")
        if isinstance(source_id, str) and source_id:
            grouped.setdefault(source_id, []).append(record)
            paths[record.get("source_path", "")] = source_id
    return grouped


def assign_assertion_id(assertion: Dict[str, Any]) -> None:
    current = assertion.get("id")
    if isinstance(current, str) and current.strip():
        return
    identity = {
        "text": assertion.get("text"),
        "subject": assertion.get("subject"),
        "relation": assertion.get("relation"),
        "object": assertion.get("object"),
        "conditions": assertion.get("conditions"),
        "source_ids": assertion.get("source_ids"),
        "quotes": [item.get("quote") for item in assertion.get("evidence", []) if isinstance(item, dict)],
    }
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assertion["id"] = "np_" + hashlib.sha256(encoded).hexdigest()[:20]


def bind_one(
    evidence: Dict[str, Any],
    candidates: Dict[str, List[Dict[str, Any]]],
    errors: List[Dict[str, Any]],
    stats: Dict[str, int],
    context: str,
) -> None:
    source_id = evidence.get("source_id")
    if not source_id and evidence.get("source_path"):
        matches = [
            key for key, records in candidates.items()
            if any(item.get("source_path") == evidence["source_path"] for item in records)
        ]
        if len(matches) == 1:
            source_id = matches[0]
            evidence["source_id"] = source_id
    if not isinstance(source_id, str) or source_id not in candidates:
        errors.append({"context": context, "code": "unknown_source", "message": f"Cannot resolve source_id {source_id!r}"})
        evidence["verification_status"] = "unresolved"
        return

    locator = evidence.get("locator") if isinstance(evidence.get("locator"), dict) else {}
    top_page = evidence.get("page")
    locator_page = locator.get("page")
    if top_page is not None and locator_page is not None and top_page != locator_page:
        errors.append({"context": context, "code": "conflicting_page", "message": f"Conflicting draft page fields: evidence.page={top_page!r}, locator.page={locator_page!r}"})
        evidence["verification_status"] = "unresolved"
        return
    if locator.get("source_id") is not None and locator.get("source_id") != source_id:
        errors.append({"context": context, "code": "conflicting_locator_source", "message": "Draft locator.source_id conflicts with evidence.source_id"})
        evidence["verification_status"] = "unresolved"
        return
    available = candidates[source_id]
    expected_paths = {record.get("source_path") for record in available}
    if locator.get("source_path") is not None and locator.get("source_path") not in expected_paths:
        errors.append({"context": context, "code": "conflicting_locator_path", "message": "Draft locator.source_path conflicts with the indexed source"})
        evidence["verification_status"] = "unresolved"
        return
    page = top_page if top_page is not None else locator_page
    if page is not None:
        available = [record for record in available if record.get("page") == page]
        if not available:
            errors.append({"context": context, "code": "unknown_page", "message": f"Page {page!r} is absent from {source_id}"})
            evidence["verification_status"] = "unresolved"
            return

    quote = evidence.get("quote")
    evidence_type = evidence.get("evidence_type", "text")
    if not isinstance(quote, str) or not quote.strip():
        if evidence_type == "visual" or evidence.get("visual_description"):
            selected = available[0] if len(available) == 1 else None
            selected_page = selected.get("page") if selected is not None else page
            new_locator = dict(locator)
            new_locator.update({
                "source_id": source_id,
                "source_path": available[0].get("source_path"),
                "page": selected_page,
                "match_type": "visual_manual",
                "verification_status": "requires_visual_review",
            })
            evidence["locator"] = new_locator
            evidence["page"] = selected_page
            evidence["verification_status"] = "requires_visual_review"
            if selected is None and page is None:
                errors.append({"context": context, "code": "ambiguous_visual_page", "message": "Visual evidence requires a page for PDF sources"})
            stats["visual"] += 1
            return
        errors.append({"context": context, "code": "empty_quote", "message": "Textual evidence requires a nonempty quote"})
        evidence["verification_status"] = "unresolved"
        return

    normalized_quote = normalize(quote).strip()
    if not normalized_quote:
        errors.append({"context": context, "code": "empty_normalized_quote", "message": "Quote contains no matchable characters"})
        evidence["verification_status"] = "unresolved"
        return

    # Gather matches across the entire selected source before choosing one;
    # otherwise a quote occurring on two PDF pages could be bound silently to
    # whichever page happened to appear first in the index.
    matches: List[Tuple[Dict[str, Any], int, int, str]] = []
    for record in available:
        raw_text = record.get("text", "")
        # Exact and normalized searches can identify different occurrences on
        # the same page. Keep both, then deduplicate only identical raw spans.
        page_matches: Dict[Tuple[int, int], Tuple[Dict[str, Any], int, int, str]] = {}
        for position in all_occurrences(raw_text, quote):
            page_matches[(position, position + len(quote))] = (
                record, position, position + len(quote), "exact",
            )
        normalized_text, offset_map = normalized_with_map(raw_text)
        normalized_positions = all_occurrences(normalized_text, normalized_quote)
        for position in normalized_positions:
            raw_start = offset_map[position]
            raw_end = offset_map[position + len(normalized_quote) - 1] + 1
            raw_end = extend_canonical_cluster(raw_text, raw_start, raw_end)
            # A match starting or ending inside a multi-character case fold
            # (for example the 'ss' expansion of ß) has no faithful raw span.
            if normalize(raw_text[raw_start:raw_end]).strip() != normalized_quote:
                continue
            page_matches.setdefault(
                (raw_start, raw_end),
                (record, raw_start, raw_end, "normalized"),
            )
        matches.extend(sorted(page_matches.values(), key=lambda item: (item[1], item[2])))

    occurrence = evidence.get("occurrence")
    if not matches:
        errors.append({"context": context, "code": "quote_not_found", "message": "Quote not found as a complete raw or normalized span on the specified source/page", "quote_preview": quote[:160]})
        evidence["verification_status"] = "unresolved"
        return
    if occurrence is not None:
        if not isinstance(occurrence, int) or isinstance(occurrence, bool) or occurrence < 1 or occurrence > len(matches):
            errors.append({"context": context, "code": "invalid_occurrence", "message": f"occurrence must be between 1 and {len(matches)}"})
            evidence["verification_status"] = "unresolved"
            return
        matches = [matches[occurrence - 1]]
    elif len(matches) != 1:
        errors.append({"context": context, "code": "ambiguous_quote", "message": f"Ambiguous quote: {len(matches)} matches in the selected source/page scope; specify page and/or 1-based occurrence", "quote_preview": quote[:160]})
        evidence["verification_status"] = "unresolved"
        return

    record, char_start, char_end, match_type = matches[0]
    line_start, line_end = line_span(record, char_start, char_end)
    new_locator = dict(locator)
    new_locator.update({
        "source_id": source_id,
        "source_path": record.get("source_path"),
        "page": record.get("page"),
        "line_start": line_start,
        "line_end": line_end,
        "char_start": char_start,
        "char_end": char_end,
        "match_type": match_type,
        "verification_status": "verified",
    })
    evidence["locator"] = new_locator
    evidence["page"] = record.get("page")
    evidence["verification_status"] = "verified"
    stats[match_type] += 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, type=Path, help="Draft result JSON")
    parser.add_argument("--sources", required=True, type=Path, help="Source-index JSONL")
    parser.add_argument("--output", required=True, type=Path, help="Bound result JSON")
    parser.add_argument("--report", required=True, type=Path, help="Binding report JSON")
    parser.add_argument("--assertions-key", default="assertions", help="Top-level assertions field (default: assertions)")
    args = parser.parse_args(argv)

    result = json.loads(args.result.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("result root must be a JSON object")
    records = [json.loads(line) for line in args.sources.read_text(encoding="utf-8").splitlines() if line.strip()]
    candidates = records_by_source(records)
    assertions = result.get(args.assertions_key, [])
    if not isinstance(assertions, list):
        raise ValueError(f"{args.assertions_key} must be an array")

    errors: List[Dict[str, Any]] = []
    stats = {"exact": 0, "normalized": 0, "visual": 0}
    for assertion_index, assertion in enumerate(assertions):
        if not isinstance(assertion, dict):
            errors.append({"context": f"assertions[{assertion_index}]", "code": "invalid_assertion", "message": "Assertion must be an object"})
            continue
        evidence_items = assertion.get("evidence", [])
        if not isinstance(evidence_items, list):
            errors.append({"context": f"assertions[{assertion_index}].evidence", "code": "invalid_evidence", "message": "Evidence must be an array"})
            continue
        for evidence_index, evidence in enumerate(evidence_items):
            if not isinstance(evidence, dict):
                errors.append({"context": f"assertions[{assertion_index}].evidence[{evidence_index}]", "code": "invalid_evidence", "message": "Evidence item must be an object"})
                continue
            bind_one(
                evidence, candidates, errors, stats,
                f"assertions[{assertion_index}].evidence[{evidence_index}]",
            )
        if evidence_items:
            assertion["source_ids"] = list(dict.fromkeys(
                item.get("source_id") for item in evidence_items
                if isinstance(item, dict) and isinstance(item.get("source_id"), str)
            ))
        assign_assertion_id(assertion)

    report = {
        "schema_version": "binding-report-1.0",
        "tool_version": TOOL_VERSION,
        "assertion_count": len(assertions),
        "textual_matches": stats["exact"] + stats["normalized"],
        "exact_matches": stats["exact"],
        "normalized_matches": stats["normalized"],
        "visual_items_requiring_review": stats["visual"],
        "error_count": len(errors),
        "errors": errors,
        "status": "error" if errors else ("warning" if stats["visual"] else "success"),
        "semantics_verified": False,
        "note": "Matching verifies quotation location only, not entailment or scientific truth.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "errors": len(errors), **stats}, ensure_ascii=False))
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
