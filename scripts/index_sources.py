#!/usr/bin/env python3
"""Build a stable page/line index from supplied research materials.

Only standard-library code is required. PDF parsing optionally uses pdftotext,
pypdf, or fitz. Errors are reported per source and a partial manifest is saved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

TOOL_VERSION = "1.0.0"
TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".jsonl", ".csv", ".tsv", ".html", ".htm",
    ".xml", ".tex", ".ris", ".bib",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".gif"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_identifier(relative_path: str, digest: str) -> str:
    value = (relative_path.replace("\\", "/") + "\0" + digest).encode("utf-8")
    return "src_" + hashlib.sha256(value).hexdigest()[:16]


def line_records(text: str) -> Tuple[List[Dict[str, Any]], List[int]]:
    # Keep terminators while computing offsets so CRLF and Unicode line
    # separators cannot shift every locator on subsequent lines.
    physical_lines = text.splitlines(keepends=True)
    if not physical_lines:
        physical_lines = [""]
    records: List[Dict[str, Any]] = []
    starts: List[int] = []
    offset = 0
    for number, physical_line in enumerate(physical_lines, start=1):
        starts.append(offset)
        records.append({"line": number, "text": physical_line.rstrip("\r\n\v\f\x85\u2028\u2029")})
        offset += len(physical_line)
    return records, starts


def make_record(
    source_id: str,
    relative_path: str,
    media_type: str,
    digest: str,
    page: Optional[int],
    text: str,
    parser: str,
) -> Dict[str, Any]:
    suffix = f"_p{page:04d}" if page is not None else "_text"
    records, starts = line_records(text)
    return {
        "record_id": source_id + suffix,
        "source_id": source_id,
        "source_path": relative_path,
        "media_type": media_type,
        "sha256": digest,
        "page": page,
        "record_type": "pdf_page" if page is not None else "text_document",
        "extraction_method": "text",
        "parser": parser,
        "text": text,
        "lines": records,
        "line_start_offsets": starts,
        "char_count": len(text),
    }


def pdftotext_pages(path: Path) -> List[str]:
    executable = shutil.which("pdftotext")
    if not executable:
        raise RuntimeError("pdftotext is not installed")
    completed = subprocess.run(
        [executable, "-enc", "UTF-8", str(path), "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"pdftotext exited {completed.returncode}: {message}")
    text = completed.stdout.decode("utf-8", errors="replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def pypdf_pages(path: Path) -> List[str]:
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(str(path))
    return [(page.extract_text() or "") for page in reader.pages]


def fitz_pages(path: Path) -> List[str]:
    import fitz  # type: ignore

    document = fitz.open(str(path))
    try:
        return [page.get_text("text") for page in document]
    finally:
        document.close()


def extract_pdf(path: Path) -> Tuple[List[str], str, List[str]]:
    failures: List[str] = []
    backends = (("pdftotext", pdftotext_pages), ("pypdf", pypdf_pages), ("fitz", fitz_pages))
    for name, backend in backends:
        if name == "pdftotext" and not shutil.which("pdftotext"):
            failures.append("pdftotext: executable not found")
            continue
        try:
            pages = backend(path)
            if not pages:
                raise RuntimeError("no pages extracted")
            return pages, name, failures
        except Exception as exc:  # optional backends fail independently
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    raise RuntimeError("all PDF extraction backends failed; " + " | ".join(failures))


def decode_text(raw: bytes) -> Tuple[str, str, List[str]]:
    warnings: List[str] = []
    try:
        return raw.decode("utf-8-sig"), "utf-8-sig", warnings
    except UnicodeDecodeError:
        pass
    # Detect four-byte BOMs before the two-byte UTF-16LE prefix FF FE.
    if raw.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        try:
            return raw.decode("utf-32"), "utf-32-bom", warnings
        except UnicodeDecodeError:
            pass
    # Bare non-UTF byte sequences can happen to decode as UTF-16 on the host
    # endianness. Require a BOM so an unrelated encoding is never silently
    # reinterpreted as valid scientific source text.
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16"), "utf-16-bom", warnings
        except UnicodeDecodeError:
            pass
    text = raw.decode("utf-8", errors="replace")
    warnings.append("Text is not valid UTF-8/BOM-marked UTF-16; replacement characters were inserted. Verify consequential quotes against the original.")
    return text, "utf-8-replace", warnings


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: str(item).lower()):
        if path.is_file() and not path.is_symlink():
            yield path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Input directory")
    parser.add_argument("--out", required=True, type=Path, help="Output source-index JSONL")
    parser.add_argument("--manifest", required=True, type=Path, help="Output manifest JSON")
    args = parser.parse_args(argv)
    root = args.input.resolve()
    if not root.is_dir():
        parser.error(f"input is not a directory: {root}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {
        "schema_version": "source-manifest-1.0",
        "tool_version": TOOL_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_root": str(root),
        "sources": [],
        "visual_attachments": [],
        "skipped_files": [],
        "warnings": [],
    }
    failures = 0
    records_written = 0

    with args.out.open("w", encoding="utf-8", newline="\n") as output:
        for path in iter_files(root):
            relative = path.relative_to(root).as_posix()
            # Root prompt files are never scientific evidence. Nested files with
            # these names may be domain data and are retained.
            if relative in {"case.json", "task.md"}:
                continue
            suffix = path.suffix.lower()
            if suffix not in TEXT_EXTENSIONS | {".pdf"} | IMAGE_EXTENSIONS:
                manifest["skipped_files"].append({"path": relative, "reason": "unsupported_extension"})
                continue
            try:
                raw = path.read_bytes()
            except Exception as exc:
                failures += 1
                manifest["sources"].append({
                    "source_id": source_identifier(relative, "unreadable"),
                    "source_path": relative,
                    "sha256": None,
                    "media_type": "application/pdf" if suffix == ".pdf" else ("image" if suffix in IMAGE_EXTENSIONS else "text"),
                    "record_ids": [],
                    "status": "read_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                })
                continue
            digest = sha256_bytes(raw)
            if suffix in IMAGE_EXTENSIONS:
                visual_source_id = source_identifier(relative, digest)
                record = make_record(visual_source_id, relative, "image", digest, None, "", "visual_index")
                record["record_type"] = "visual_document"
                record["extraction_method"] = "visual"
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                records_written += 1
                manifest["visual_attachments"].append({
                    "source_id": visual_source_id,
                    "source_path": relative,
                    "sha256": digest,
                    "media_type": "image",
                    "record_ids": [record["record_id"]],
                    "status": "requires_visual_inspection",
                })
                continue
            source_id = source_identifier(relative, digest)
            source: Dict[str, Any] = {
                "source_id": source_id,
                "source_path": relative,
                "sha256": digest,
                "media_type": "application/pdf" if suffix == ".pdf" else "text",
                "extraction_method": "text",
                "record_ids": [],
                "status": "success",
                "warnings": [],
            }
            try:
                if suffix == ".pdf":
                    pages, backend, backend_warnings = extract_pdf(path)
                    source["parser"] = backend
                    source["page_count"] = len(pages)
                    if backend_warnings:
                        source["warnings"].extend(backend_warnings)
                    for page_number, text in enumerate(pages, start=1):
                        record = make_record(
                            source_id, relative, "application/pdf", digest,
                            page_number, text, backend,
                        )
                        if len("".join(ch for ch in text if ch.isalnum())) < 20:
                            warning = f"Page {page_number} has fewer than 20 alphanumeric characters; inspect for a scanned page or extraction failure."
                            source["warnings"].append(warning)
                        output.write(json.dumps(record, ensure_ascii=False) + "\n")
                        source["record_ids"].append(record["record_id"])
                        records_written += 1
                    source["text_characters"] = sum(len(page) for page in pages)
                else:
                    text, encoding, decode_warnings = decode_text(raw)
                    source["parser"] = encoding
                    source["warnings"].extend(decode_warnings)
                    record = make_record(source_id, relative, "text", digest, None, text, encoding)
                    output.write(json.dumps(record, ensure_ascii=False) + "\n")
                    source["record_ids"].append(record["record_id"])
                    source["text_characters"] = len(text)
                    records_written += 1
                if source["warnings"]:
                    source["status"] = "success_with_warnings"
            except Exception as exc:
                failures += 1
                source["status"] = "extraction_failed"
                source["error"] = f"{type(exc).__name__}: {exc}"
            manifest["sources"].append(source)

    manifest["record_count"] = records_written
    manifest["failure_count"] = failures
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "records": records_written,
        "sources": len(manifest["sources"]),
        "visual_attachments": len(manifest["visual_attachments"]),
        "failures": failures,
        "index": str(args.out),
        "manifest": str(args.manifest),
    }, ensure_ascii=False))
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
