#!/usr/bin/env python3
"""Offline synthetic regression test; contains no formal evaluation cases."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

import audit_result
import bind_evidence
import index_sources
from index_sources import line_records, make_record


TEST_COUNT = 0


def require(condition: bool, message: str) -> None:
    global TEST_COUNT
    TEST_COUNT += 1
    if not condition:
        raise AssertionError(message)


def main() -> int:
    require(bind_evidence.normalize("  ﬁnger-\nprint  ") == "fingerprint", "Unicode/dehyphenation normalization")
    require(bind_evidence.normalize("Café") == bind_evidence.normalize("Cafe\u0301"), "canonical Unicode equivalence")
    decoded, encoding, warnings = index_sources.decode_text(b"\xffa")
    require(encoding == "utf-8-replace" and bool(warnings) and "�" in decoded, "bare non-UTF bytes must not become silent UTF-16")
    decoded, encoding, warnings = index_sources.decode_text("marked".encode("utf-16"))
    require(decoded == "marked" and encoding == "utf-16-bom" and not warnings, "BOM-marked UTF-16 remains supported")
    decoded, encoding, warnings = index_sources.decode_text("A".encode("utf-32"))
    require(decoded == "A" and encoding == "utf-32-bom" and not warnings, "UTF-32LE BOM precedes UTF-16 detection")
    require(bind_evidence.normalize("\u1100\u1161\u11a8") == bind_evidence.normalize("\uac01"), "Hangul canonical composition")
    _, offsets = line_records("a\r\nb\u2028c")
    require(offsets == [0, 3, 5], f"line offsets: {offsets}")

    with tempfile.TemporaryDirectory(prefix="nanopub-synthetic-") as directory:
        root = Path(directory)
        raw = b"SYNTHETIC TEST DATA - NOT A SCIENTIFIC RESULT"
        digest = hashlib.sha256(raw).hexdigest()
        source_id = "src_synthetic"
        page1_text = "Synthetic report\nIn adults, at 12 weeks, Treat-\nment A reduced mortality by 20% versus placebo.\n"
        page2_text = "Methods\nMethod B enabled detection of the marker in cultured cells.\nTreatment A was measured again.\n"
        records = [
            make_record(source_id, "synthetic.pdf", "application/pdf", digest, 1, page1_text, "synthetic"),
            make_record(source_id, "synthetic.pdf", "application/pdf", digest, 2, page2_text, "synthetic"),
        ]
        index_path = root / "sources.jsonl"
        index_path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")

        def bind_variant(label, variant, variant_records=records):
            variant_index = root / f"{label}.sources.jsonl"
            variant_index.write_text("".join(json.dumps(item) + "\n" for item in variant_records), encoding="utf-8")
            input_path = root / f"{label}.draft.json"
            output_path = root / f"{label}.bound.json"
            report_path = root / f"{label}.binding.json"
            input_path.write_text(json.dumps(variant), encoding="utf-8")
            code = bind_evidence.main([
                "--result", str(input_path), "--sources", str(variant_index),
                "--output", str(output_path), "--report", str(report_path),
            ])
            return code, json.loads(output_path.read_text(encoding="utf-8")), json.loads(report_path.read_text(encoding="utf-8")), variant_index, output_path

        def audit_variant(label, variant, variant_index=index_path, contract_path=None):
            input_path = root / f"{label}.audit-input.json"
            report_path = root / f"{label}.quality.json"
            input_path.write_text(json.dumps(variant), encoding="utf-8")
            arguments = [
                "--result", str(input_path), "--sources", str(variant_index),
                "--output", str(root / f"{label}.audit-output.json"), "--report", str(report_path),
            ]
            if contract_path is not None:
                arguments.extend(["--contract", str(contract_path)])
            code = audit_result.main(arguments)
            return code, json.loads(report_path.read_text(encoding="utf-8"))

        draft = {
            "case_id": "synthetic-case-001",
            "status": "success",
            "status_reason": None,
            "answer": "SYNTHETIC EXAMPLE: Treatment A was associated with the stated reported comparison; Method B enabled marker detection.",
            "sources": [{
                "source_id": source_id,
                "source_path": "synthetic.pdf",
                "sha256": digest,
                "title": "Synthetic report (fabricated for software testing only)",
                "authors": [],
                "year": None,
                "version": None,
                "identifiers": {},
                "extraction_method": "text",
            }],
            "assertions": [
                {
                    "text": "At 12 weeks, Treatment A reduced mortality by 20% versus placebo in adults.",
                    "subject": "Treatment A",
                    "relation": "decreases",
                    "relation_type": "comparative_effect",
                    "object": {"outcome": "mortality", "relative_reduction": "20%", "comparator": "placebo"},
                    "conditions": {"population": "adults", "time_point": "12 weeks"},
                    "epistemic_status": "reported",
                    "support_type": "direct",
                    "evidence": [{
                        "source_id": source_id,
                        "quote": "In adults, at 12 weeks, Treatment A reduced mortality by 20% versus placebo.",
                        "page": 1,
                        "evidence_type": "text",
                        "role": "supports",
                    }],
                    "confidence": {"level": "high", "basis": "The synthetic quotation directly includes the full comparison and its qualifiers."},
                    "uncertainty": [],
                },
                {
                    "text": "Method B enabled detection of the marker in cultured cells.",
                    "subject": "Method B",
                    "relation": "enables",
                    "relation_type": "procedural",
                    "object": "detection of the marker",
                    "conditions": {"model_system": "cultured cells"},
                    "epistemic_status": "reported",
                    "support_type": "direct",
                    "evidence": [{
                        "source_id": source_id,
                        "quote": "Method B enabled detection of the marker in cultured cells.",
                        "page": 2,
                        "evidence_type": "text",
                        "role": "supports",
                    }],
                    "confidence": {"level": "high", "basis": "The exact synthetic sentence contains the complete procedural assertion."},
                    "uncertainty": [],
                },
            ],
            "uncertainties": [{
                "type": "other",
                "description": "All scientific content is synthetic and demonstrates software behavior only.",
                "resolution": "not_applicable",
            }],
            "change_records": [],
        }
        draft_path = root / "result.draft.json"
        bound_path = root / "result.bound.json"
        binding_report_path = root / "binding_report.json"
        draft_path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
        bound_return = bind_evidence.main([
            "--result", str(draft_path), "--sources", str(index_path),
            "--output", str(bound_path), "--report", str(binding_report_path),
        ])
        require(bound_return == 0, "valid synthetic binding should pass")
        bound = json.loads(bound_path.read_text(encoding="utf-8"))
        require(bound["assertions"][0]["evidence"][0]["locator"]["match_type"] == "normalized", "line-break quote should normalize")
        require(bound["assertions"][0]["evidence"][0]["locator"]["line_start"] == 2, "first quote start line")
        require(bound["assertions"][0]["evidence"][0]["locator"]["line_end"] == 3, "dehyphenated quote end line")
        require(bound["assertions"][1]["evidence"][0]["locator"]["match_type"] == "exact", "second quote exact match")
        require(all(item["id"].startswith("np_") for item in bound["assertions"]), "deterministic assertion IDs")

        # UTF-8 BOM inputs (e.g. files written by Windows editors) must be accepted.
        bom_draft_path = root / "result.draft.bom.json"
        bom_draft_path.write_text("\ufeff" + json.dumps(draft), encoding="utf-8")
        bom_return = bind_evidence.main([
            "--result", str(bom_draft_path), "--sources", str(index_path),
            "--output", str(root / "result.bom.bound.json"), "--report", str(root / "result.bom.report.json"),
        ])
        require(bom_return == 0, "BOM-prefixed draft should bind successfully")

        ambiguous_draft = copy.deepcopy(draft)
        ambiguous_draft["assertions"] = [ambiguous_draft["assertions"][0]]
        ambiguous_draft["assertions"][0]["evidence"][0].pop("page")
        ambiguous_draft["assertions"][0]["evidence"][0]["quote"] = "Treatment A"
        ambiguous_path = root / "ambiguous.json"
        ambiguous_path.write_text(json.dumps(ambiguous_draft), encoding="utf-8")
        ambiguous_return = bind_evidence.main([
            "--result", str(ambiguous_path), "--sources", str(index_path),
            "--output", str(root / "ambiguous.bound.json"), "--report", str(root / "ambiguous.report.json"),
        ])
        ambiguous_report = json.loads((root / "ambiguous.report.json").read_text(encoding="utf-8"))
        require(ambiguous_return == 2, "cross-page repeated quote must fail")
        require("Ambiguous quote" in ambiguous_report["errors"][0]["message"], "ambiguity explanation")

        case = {
            "case_id": "synthetic-case-001",
            "output_contract": {
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "answer": {"type": "string"},
                    "status": {"type": "string"},
                    "sources": {"type": "array"},
                    "assertions": {"type": "array"},
                    "uncertainties": {"type": "array"},
                    "change_records": {"type": "array"},
                },
            },
        }
        case_path = root / "case.json"
        case_path.write_text(json.dumps(case), encoding="utf-8")
        final_path = root / "output" / "result.json"
        quality_path = root / "output" / "quality_report.json"
        jsonl_path = root / "output" / "assertions.jsonl"
        audit_return = audit_result.main([
            "--result", str(bound_path), "--sources", str(index_path), "--contract", str(case_path),
            "--output", str(final_path), "--report", str(quality_path), "--jsonl", str(jsonl_path),
        ])
        require(audit_return == 0, "valid synthetic audit should not have errors")
        require(len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 2, "JSONL assertion count")

        bom_case_path = root / "case.bom.json"
        bom_case_path.write_text("\ufeff" + json.dumps(case), encoding="utf-8")
        bom_audit_return = audit_result.main([
            "--result", str(bound_path), "--sources", str(index_path), "--contract", str(bom_case_path),
            "--output", str(root / "bom.result.json"), "--report", str(root / "bom.report.json"),
        ])
        require(bom_audit_return == 0, "BOM-prefixed contract should audit successfully")

        tampered = copy.deepcopy(bound)
        tampered["assertions"][1]["evidence"][0]["quote"] = "Method B did not enable detection of the marker."
        tampered_path = root / "tampered.json"
        tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
        tampered_return = audit_result.main([
            "--result", str(tampered_path), "--sources", str(index_path),
            "--output", str(root / "tampered.output.json"), "--report", str(root / "tampered.report.json"),
        ])
        require(tampered_return == 2, "tampered quote must fail audit")

        # Exact and line-break-normalized variants on one page are two matches.
        same_page_variant = copy.deepcopy(draft)
        same_page_variant["assertions"] = [same_page_variant["assertions"][0]]
        same_page_variant["assertions"][0]["evidence"][0].update({"page": 3, "quote": "Treatment A"})
        same_page_records = records + [
            make_record(source_id, "synthetic.pdf", "application/pdf", digest, 3, "Treatment A\nTreat-\nment A", "synthetic"),
        ]
        code, _, report, _, _ = bind_variant("same-page-ambiguity", same_page_variant, same_page_records)
        require(code == 2 and report["errors"][0]["code"] == "ambiguous_quote", "same-page exact/normalized variants must be ambiguous")
        require("2 matches" in report["errors"][0]["message"], "both same-page variants must be counted")

        # A partial multi-character case fold cannot define a faithful span.
        casefold_variant = copy.deepcopy(same_page_variant)
        casefold_variant["assertions"][0]["evidence"][0].update({"page": 1, "quote": "sx", "occurrence": 1})
        casefold_records = [make_record(source_id, "synthetic.pdf", "application/pdf", digest, 1, "ßx", "synthetic")]
        code, _, report, _, _ = bind_variant("partial-casefold", casefold_variant, casefold_records)
        require(code == 2 and report["errors"][0]["code"] == "quote_not_found", "partial ß expansion must be rejected")

        # Canonical composition/decomposition must retain the combining mark.
        unicode_variant = copy.deepcopy(same_page_variant)

        unicode_variant["assertions"][0]["evidence"] = [dict(unicode_variant["assertions"][0]["evidence"][0], page=1, quote="Café")]
        unicode_records = [make_record(source_id, "synthetic.pdf", "application/pdf", digest, 1, "Cafe\u0301", "synthetic")]
        code, unicode_bound, _, unicode_index, _ = bind_variant("canonical-unicode", unicode_variant, unicode_records)
        require(code == 0 and unicode_bound["assertions"][0]["evidence"][0]["locator"]["char_end"] == 5, "decomposed quote span includes combining mark")
        code, report = audit_variant("canonical-unicode", unicode_bound, unicode_index)
        require(code == 0 and report["error_count"] == 0, "canonical Unicode bound result survives audit")

        hangul_variant = copy.deepcopy(same_page_variant)
        hangul_variant["assertions"][0]["evidence"] = [dict(hangul_variant["assertions"][0]["evidence"][0], page=1, quote="\uac01")]
        hangul_records = [make_record(source_id, "synthetic.pdf", "application/pdf", digest, 1, "\u1100\u1161\u11a8", "synthetic")]
        code, hangul_bound, _, hangul_index, _ = bind_variant("canonical-hangul", hangul_variant, hangul_records)
        require(code == 0 and hangul_bound["assertions"][0]["evidence"][0]["locator"]["char_end"] == 3, "Hangul match includes the complete Jamo cluster")
        code, report = audit_variant("canonical-hangul", hangul_bound, hangul_index)
        require(code == 0 and report["error_count"] == 0, "Hangul canonical bound result survives audit")

        conflict_variant = copy.deepcopy(draft)
        conflict_variant["assertions"] = [conflict_variant["assertions"][0]]
        conflict_variant["assertions"][0]["evidence"][0]["locator"] = {
            "page": 2, "source_id": "src_wrong", "source_path": "wrong.pdf"
        }
        code, _, report, _, _ = bind_variant("prebinding-conflict", conflict_variant)
        require(code == 2 and report["errors"][0]["code"] == "conflicting_page", "conflicting draft page fields are rejected before binding")

        # Exact boundary evidence must not be rejected by whole-page context.
        boundary_variant = copy.deepcopy(same_page_variant)
        boundary_variant["assertions"][0]["evidence"] = [dict(boundary_variant["assertions"][0]["evidence"][0], page=1, quote="word-")]
        boundary_records = [make_record(source_id, "synthetic.pdf", "application/pdf", digest, 1, "word-\nA", "synthetic")]
        code, boundary_bound, _, boundary_index, _ = bind_variant("exact-boundary", boundary_variant, boundary_records)
        require(code == 0 and boundary_bound["assertions"][0]["evidence"][0]["locator"]["match_type"] == "exact", "exact boundary quote binds exactly")
        code, report = audit_variant("exact-boundary", boundary_bound, boundary_index)
        require(code == 0 and report["error_count"] == 0, "whole-page dehyphenation does not invalidate exact boundary quote")

        # A single PDF page is enough to locate purely visual evidence.
        visual_variant = copy.deepcopy(draft)
        visual_variant["assertions"] = [visual_variant["assertions"][0]]
        visual_variant["assertions"][0]["evidence"] = [{
            "source_id": source_id, "quote": "", "evidence_type": "visual",
            "visual_description": "Synthetic visual placeholder for locator testing only.",
            "figure_label": "Synthetic Figure 1", "region": "entire synthetic page",
        }]
        code, visual_bound, _, visual_index, _ = bind_variant("single-page-visual", visual_variant, [records[0]])
        require(code == 0 and visual_bound["assertions"][0]["evidence"][0]["page"] == 1, "single-page visual binder backfills page")
        code, report = audit_variant("single-page-visual", visual_bound, visual_index)
        require(code == 0 and report["error_count"] == 0 and report["warning_count"] >= 1, "visual locator audits with explicit review warning")
        visual_bad = copy.deepcopy(visual_bound)
        visual_bad["assertions"][0]["evidence"][0]["locator"]["verification_status"] = "verified"
        visual_bad["assertions"][0]["evidence"][0].pop("region")
        code, report = audit_variant("visual-status-region", visual_bad, visual_index)
        codes = {item["code"] for item in report["errors"]}
        require(code == 2 and {"invalid_visual_status", "missing_visual_region"}.issubset(codes), "visual status and inspected region are enforced")

        # Standalone images receive index records rather than manifest-only IDs.
        image_input = root / "image-input"
        image_input.mkdir()
        image_bytes = b"SYNTHETIC IMAGE PLACEHOLDER - NOT REAL PIXEL DATA"
        (image_input / "figure.png").write_bytes(image_bytes)
        image_index = root / "image.sources.jsonl"
        image_manifest = root / "image.manifest.json"
        code = index_sources.main(["--input", str(image_input), "--out", str(image_index), "--manifest", str(image_manifest)])
        image_record = json.loads(image_index.read_text(encoding="utf-8").strip())
        image_digest = hashlib.sha256(image_bytes).hexdigest()
        require(code == 0 and image_record["record_type"] == "visual_document", "standalone image has a visual index record")
        image_variant = copy.deepcopy(visual_variant)
        image_variant["sources"] = [{
            "source_id": image_record["source_id"], "source_path": "figure.png", "sha256": image_digest,
            "extraction_method": "visual", "authors": [], "identifiers": {},
        }]
        image_variant["assertions"][0]["evidence"][0]["source_id"] = image_record["source_id"]
        code, image_bound, _, _, _ = bind_variant("standalone-image", image_variant, [image_record])
        require(code == 0 and image_bound["assertions"][0]["evidence"][0]["page"] is None, "standalone visual source binds without PDF page")
        code, report = audit_variant("standalone-image", image_bound, image_index)
        require(code == 0 and report["error_count"] == 0, "standalone image source declaration resolves in audit")

        # Contradictory duplicate locator fields are rejected.
        inconsistent = copy.deepcopy(bound)
        inconsistent["assertions"][0]["evidence"][0]["page"] = 999
        inconsistent["assertions"][0]["evidence"][0]["locator"]["source_id"] = "src_wrong"
        code, report = audit_variant("inconsistent-locator", inconsistent)
        codes = {item["code"] for item in report["errors"]}
        require(code == 2 and {"evidence_page_mismatch", "locator_source_mismatch"}.issubset(codes), "contradictory locator metadata is rejected")

        # Nested required fields and JSON Schema union types are deterministic.
        nested_case = {
            "case_id": "synthetic-case-001",
            "output_contract": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "object", "required": ["value"],
                        "properties": {"value": {"type": ["string", "null"]}},
                    },
                },
            },
        }
        nested_case_path = root / "nested-case.json"
        nested_case_path.write_text(json.dumps(nested_case), encoding="utf-8")
        nested_bad = copy.deepcopy(bound)
        nested_bad["answer"] = {}
        code, report = audit_variant("nested-contract-missing", nested_bad, index_path, nested_case_path)
        require(code == 2 and any(item["path"] == "result.answer.value" for item in report["errors"]), "nested required contract field is enforced")
        nested_good = copy.deepcopy(bound)
        nested_good["answer"] = {"value": None}
        code, report = audit_variant("nested-contract-union", nested_good, index_path, nested_case_path)
        require(code == 0 and report["error_count"] == 0, "nullable union type is enforced without false error")

        optional_case = {"case_id": "synthetic-case-001", "output_contract": {"type": "object", "properties": {"optional_answer": {"type": "string"}}}}
        optional_path = root / "optional-case.json"
        optional_path.write_text(json.dumps(optional_case), encoding="utf-8")
        code, report = audit_variant("root-optional", bound, index_path, optional_path)
        require(code == 0 and report["error_count"] == 0, "root JSON Schema properties are optional unless required")

        allof_case = {"case_id": "synthetic-case-001", "output_contract": {"type": "object", "allOf": [{"required": ["answer"], "properties": {"answer": {"type": "string"}}}]}}
        allof_path = root / "allof-case.json"
        allof_path.write_text(json.dumps(allof_case), encoding="utf-8")
        code, report = audit_variant("root-allof", bound, index_path, allof_path)
        require(code == 0 and report["error_count"] == 0, "root allOf validates the result instead of becoming a field name")

        strict_case = {"case_id": "synthetic-case-001", "output_contract": {"type": "object", "properties": {}, "additionalProperties": False}}
        strict_path = root / "strict-case.json"
        strict_path.write_text(json.dumps(strict_case), encoding="utf-8")
        code, report = audit_variant("root-additional", bound, index_path, strict_path)
        require(code == 2 and any(item["code"] == "contract_additional_field" for item in report["errors"]), "additionalProperties false rejects forbidden extra fields")
        strict_only_case = {"case_id": "synthetic-case-001", "output_contract": {"additionalProperties": False}}
        strict_only_path = root / "strict-only-case.json"
        strict_only_path.write_text(json.dumps(strict_only_case), encoding="utf-8")
        code, report = audit_variant("root-additional-only", bound, index_path, strict_only_path)
        require(code == 2 and any(item["code"] == "contract_additional_field" for item in report["errors"]), "standalone root additionalProperties also enters schema validation")

    print(json.dumps({"status": "success", "tests": TEST_COUNT, "data": "synthetic only"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
