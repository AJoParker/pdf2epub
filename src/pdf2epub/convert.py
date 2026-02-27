"""Top-level conversion orchestration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from .author_extract import infer_author_info
from .epub_build import build_epub
from .cover_gen import generate_cover_png
from .pdf_extract import ContentBlock, LayoutMode, OCRMode, extract_pages_content

AuthorMode = Literal["metadata", "heuristic", "auto"]
CoverMode = Literal["styled", "none"]


def _chunk_pages(pages: list[list[ContentBlock]], split_pages: int) -> list[list[ContentBlock]]:
    if split_pages <= 0:
        raise ValueError("split_pages must be > 0")

    chunks: list[list[ContentBlock]] = []
    for i in range(0, len(pages), split_pages):
        chunk: list[ContentBlock] = []
        for page in pages[i : i + split_pages]:
            chunk.extend(page)
        if chunk:
            chunks.append(chunk)
    return chunks


def convert_pdf_to_epub(
    input_pdf: Path,
    output_epub: Path,
    *,
    title: str,
    author: str | None = None,
    lang: str = "en",
    ocr_mode: OCRMode = "auto",
    author_mode: AuthorMode = "auto",
    no_preface: bool = False,
    split_pages: int = 10,
    no_brand: bool = False,
    logo_path: Path | None = None,
    cover_mode: CoverMode = "styled",
    layout: LayoutMode = "simple",
    logger: logging.Logger | None = None,
) -> None:
    """Convert a PDF file into a reflowable EPUB."""
    if logger is None:
        logger = logging.getLogger(__name__)

    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")

    inferred = infer_author_info(input_pdf, mode=author_mode, ocr_mode=ocr_mode, logger=logger)
    final_author = author.strip() if author and author.strip() else (inferred.primary_author or "Unknown")

    preface_authors = inferred.authors if inferred.authors else ([final_author] if author else [])
    preface_contacts = inferred.contacts

    logger.info("Extracting text from PDF: %s", input_pdf)
    pages = extract_pages_content(str(input_pdf), ocr_mode=ocr_mode, layout=layout, logger=logger)
    if not pages:
        raise RuntimeError("No pages found in input PDF")

    chapters = _chunk_pages(pages, split_pages)
    if not chapters:
        raise RuntimeError("No usable text extracted from PDF")

    logger.info("Building EPUB with %s chapter(s)", len(chapters))
    cover_png_bytes = None
    if cover_mode != "none":
        cover_png_bytes = generate_cover_png(
            title=title,
            author=final_author,
            include_branding=not no_brand,
            logo_path=logo_path,
        )

    build_epub(
        chapters,
        output_epub,
        title=title,
        author=final_author,
        lang=lang,
        identifier=f"pdf2epub:{input_pdf.resolve()}",
        preface_authors=preface_authors,
        preface_contacts=preface_contacts,
        include_preface=not no_preface,
        cover_png_bytes=cover_png_bytes,
    )
