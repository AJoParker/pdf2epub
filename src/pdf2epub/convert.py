"""Top-level conversion orchestration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from .author_extract import infer_author_info
from .epub_build import build_epub
from .pdf_extract import OCRMode, extract_pages_text

AuthorMode = Literal["metadata", "heuristic", "auto"]


def _chunk_pages(pages: list[str], split_pages: int) -> list[str]:
    if split_pages <= 0:
        raise ValueError("split_pages must be > 0")

    chunks: list[str] = []
    for i in range(0, len(pages), split_pages):
        chunk = "\n\n".join(page for page in pages[i : i + split_pages] if page.strip())
        chunks.append(chunk.strip())
    return [chunk for chunk in chunks if chunk]


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
    pages = extract_pages_text(str(input_pdf), ocr_mode=ocr_mode, logger=logger)
    if not pages:
        raise RuntimeError("No pages found in input PDF")

    chapters = _chunk_pages(pages, split_pages)
    if not chapters:
        raise RuntimeError("No usable text extracted from PDF")

    logger.info("Building EPUB with %s chapter(s)", len(chapters))
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
    )
