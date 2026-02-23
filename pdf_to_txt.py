#!/usr/bin/env python3
"""
Convert one PDF (or all PDFs in a folder) to UTF-8 .txt files.

Primary extraction uses PyMuPDF. Optional OCR fallback can be enabled for pages
that appear scanned or image-only.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import fitz  # PyMuPDF
except ImportError:
    print(
        "Missing dependency: PyMuPDF\n"
        "Install with: pip install pymupdf",
        file=sys.stderr,
    )
    raise


@dataclass
class ConvertConfig:
    sort_text: bool
    add_page_markers: bool
    use_ocr: bool
    ocr_dpi: int
    ocr_lang: str
    ocr_min_chars: int
    include_metadata: bool
    overwrite: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert PDF(s) to .txt with high-fidelity extraction. "
            "Use --ocr for scanned/image-only pages."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="PDF file path or directory containing PDFs.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Destination folder for .txt files. "
            "Default: next to each source PDF."
        ),
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="If --input is a directory, scan subfolders recursively.",
    )
    parser.add_argument(
        "--no-sort",
        action="store_true",
        help="Disable positional sorting while extracting text.",
    )
    parser.add_argument(
        "--no-page-markers",
        action="store_true",
        help="Do not add '===== PAGE N =====' separators in output text.",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Enable OCR fallback for pages with little/no embedded text.",
    )
    parser.add_argument(
        "--ocr-dpi",
        type=int,
        default=300,
        help="Render DPI for OCR pages (default: 300).",
    )
    parser.add_argument(
        "--ocr-lang",
        default="eng",
        help="Tesseract OCR language code(s), e.g. 'eng' or 'eng+hin'.",
    )
    parser.add_argument(
        "--ocr-min-chars",
        type=int,
        default=25,
        help=(
            "If non-whitespace chars on a page are below this threshold, "
            "OCR fallback is used when --ocr is enabled (default: 25)."
        ),
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Do not include PDF metadata header in the output text.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .txt files.",
    )
    return parser.parse_args()


def tesseract_available() -> bool:
    try:
        completed = subprocess.run(
            ["tesseract", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        return False
    return completed.returncode == 0


def ensure_ocr_dependencies() -> None:
    if not tesseract_available():
        raise RuntimeError(
            "Tesseract binary not found. Install it first.\n"
            "macOS (Homebrew): brew install tesseract"
        )
    try:
        import pytesseract  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Missing Python dependency for OCR: pytesseract\n"
            "Install with: pip install pytesseract"
        ) from exc
    try:
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Missing Python dependency for OCR image handling: pillow\n"
            "Install with: pip install pillow"
        ) from exc


def list_pdf_files(input_path: Path, recursive: bool) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            raise ValueError(f"Input file is not a PDF: {input_path}")
        return [input_path]

    if not input_path.is_dir():
        raise ValueError(f"Input path does not exist: {input_path}")

    pdfs: list[Path] = []
    walker: Iterable[tuple[str, list[str], list[str]]] = os.walk(input_path)
    for root, _, files in walker:
        root_path = Path(root)
        for name in files:
            if name.lower().endswith(".pdf"):
                pdfs.append(root_path / name)
        if not recursive:
            break

    return sorted(pdfs)


def build_output_path(
    pdf_path: Path,
    input_root: Path,
    output_dir: Path | None,
) -> Path:
    if output_dir is None:
        return pdf_path.with_suffix(".txt")

    if input_root.is_file():
        return output_dir / f"{pdf_path.stem}.txt"

    rel = pdf_path.relative_to(input_root)
    return (output_dir / rel).with_suffix(".txt")


def sanitize_metadata_value(value: object) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text).strip()


def extract_page_text(page: fitz.Page, sort_text: bool) -> str:
    try:
        text = page.get_text("text", sort=sort_text)
    except TypeError:
        text = page.get_text("text")
    return text or ""


def should_use_ocr(page_text: str, threshold: int) -> bool:
    non_space_chars = sum(0 if ch.isspace() else 1 for ch in page_text)
    return non_space_chars < threshold


def ocr_page(page: fitz.Page, dpi: int, lang: str) -> str:
    import pytesseract
    from PIL import Image

    matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    mode = "RGB" if pix.n >= 3 else "L"
    image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    return pytesseract.image_to_string(image, lang=lang)


def convert_pdf_to_text(
    pdf_path: Path,
    txt_path: Path,
    config: ConvertConfig,
) -> tuple[int, int]:
    ocr_pages = 0
    total_pages = 0

    with fitz.open(pdf_path) as doc:
        total_pages = doc.page_count
        lines: list[str] = []

        if config.include_metadata:
            md = doc.metadata or {}
            lines.extend(
                [
                    "# PDF Metadata",
                    f"source_file: {pdf_path.name}",
                    f"pages: {doc.page_count}",
                    f"title: {sanitize_metadata_value(md.get('title', ''))}",
                    f"author: {sanitize_metadata_value(md.get('author', ''))}",
                    f"subject: {sanitize_metadata_value(md.get('subject', ''))}",
                    f"creator: {sanitize_metadata_value(md.get('creator', ''))}",
                    f"producer: {sanitize_metadata_value(md.get('producer', ''))}",
                    "",
                ]
            )

        for page_index, page in enumerate(doc, start=1):
            page_text = extract_page_text(page, config.sort_text)
            if config.use_ocr and should_use_ocr(page_text, config.ocr_min_chars):
                page_text = ocr_page(page, config.ocr_dpi, config.ocr_lang)
                ocr_pages += 1

            if config.add_page_markers:
                lines.append(f"===== PAGE {page_index} =====")
            lines.append(page_text.rstrip("\n"))
            lines.append("")

    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return total_pages, ocr_pages


def main() -> int:
    args = parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else None
    )

    config = ConvertConfig(
        sort_text=not args.no_sort,
        add_page_markers=not args.no_page_markers,
        use_ocr=args.ocr,
        ocr_dpi=args.ocr_dpi,
        ocr_lang=args.ocr_lang,
        ocr_min_chars=args.ocr_min_chars,
        include_metadata=not args.no_metadata,
        overwrite=args.overwrite,
    )

    if config.use_ocr:
        try:
            ensure_ocr_dependencies()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    try:
        pdf_files = list_pdf_files(input_path, recursive=args.recursive)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not pdf_files:
        print("No PDF files found.")
        return 0

    converted = 0
    skipped = 0
    failed = 0
    total_pages = 0
    total_ocr_pages = 0

    for pdf_path in pdf_files:
        txt_path = build_output_path(pdf_path, input_path, output_dir)
        if txt_path.exists() and not config.overwrite:
            print(f"SKIP: {txt_path} already exists (use --overwrite)")
            skipped += 1
            continue

        try:
            pages, ocr_pages = convert_pdf_to_text(pdf_path, txt_path, config)
            converted += 1
            total_pages += pages
            total_ocr_pages += ocr_pages
            ocr_note = f", ocr_pages={ocr_pages}" if config.use_ocr else ""
            print(f"OK: {pdf_path} -> {txt_path} (pages={pages}{ocr_note})")
        except Exception as exc:  # broad on purpose: continue batch conversion
            failed += 1
            print(f"FAIL: {pdf_path} ({type(exc).__name__}: {exc})", file=sys.stderr)

    print(
        "Summary: "
        f"converted={converted}, skipped={skipped}, failed={failed}, "
        f"pages={total_pages}, ocr_pages={total_ocr_pages}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
