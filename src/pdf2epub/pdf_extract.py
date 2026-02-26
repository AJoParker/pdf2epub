"""PDF text extraction logic with optional OCR fallback."""

from __future__ import annotations

import logging
from typing import Literal

import fitz  # type: ignore[import-not-found]

from .ocr import ocr_page
from .text_clean import clean_text

OCRMode = Literal["off", "auto", "always"]


def extract_pages_text(
    pdf_path: str,
    *,
    ocr_mode: OCRMode = "auto",
    low_text_threshold: int = 50,
    logger: logging.Logger | None = None,
) -> list[str]:
    """Extract cleaned text from each PDF page."""
    if logger is None:
        logger = logging.getLogger(__name__)

    doc = fitz.open(pdf_path)
    try:
        pages: list[str] = []
        for index, page in enumerate(doc):
            extracted = page.get_text("text") or ""
            extracted = extracted.strip()

            should_ocr = False
            if ocr_mode == "always":
                should_ocr = True
            elif ocr_mode == "auto" and len(extracted) < low_text_threshold:
                should_ocr = True

            if should_ocr:
                logger.debug(
                    "Using OCR for page %s (extracted_chars=%s)",
                    index + 1,
                    len(extracted),
                )
                extracted = ocr_page(page).strip()

            pages.append(clean_text(extracted))

        return pages
    finally:
        doc.close()
