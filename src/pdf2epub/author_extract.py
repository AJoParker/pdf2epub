"""Author and contact inference from PDF metadata and front matter."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import fitz  # type: ignore[import-not-found]

from .ocr import ocr_page
from .pdf_extract import OCRMode
from .text_clean import clean_text

AuthorMode = Literal["metadata", "heuristic", "auto"]

_INVALID_AUTHOR_VALUES = {"", "unknown", "untitled", "anonymous", "none", "n/a"}
_STOP_HEADER_RE = re.compile(
    r"^(abstract|introduction|table\s+of\s+contents|contents|chapter\s+\d+|\d+\.|i\.|ii\.|iii\.)\b",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
_AFFILIATION_RE = re.compile(r"\b(university|institute|department|college|school|laboratory|lab|faculty)\b", re.IGNORECASE)


@dataclass(frozen=True)
class AuthorExtractionResult:
    primary_author: str | None
    authors: list[str]
    contacts: list[str]
    source: Literal["metadata", "heuristic", "none"]


def _is_usable_author(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip()
    if not normalized:
        return False
    return normalized.casefold() not in _INVALID_AUTHOR_VALUES


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _split_authors(raw: str) -> list[str]:
    cleaned = raw.strip().strip(";:")
    if not cleaned:
        return []
    parts = re.split(r"\s*(?:,| and | & )\s*", cleaned)
    return [part.strip() for part in parts if _looks_like_name(part.strip())]


def _looks_like_name(value: str) -> bool:
    text = value.strip()
    if not text or len(text) > 80:
        return False
    if _EMAIL_RE.search(text) or _URL_RE.search(text):
        return False
    if any(ch.isdigit() for ch in text):
        return False
    if _AFFILIATION_RE.search(text):
        return False

    tokens = re.findall(r"[A-Za-z][A-Za-z'\-\.]*", text)
    if len(tokens) < 2 or len(tokens) > 4:
        return False

    lowered_tokens = {token.strip(".").lower() for token in tokens}
    if lowered_tokens & {"paper", "study", "analysis", "report", "thesis", "untitled"}:
        return False

    capitalized = 0
    for token in tokens:
        t = token.strip(".")
        if len(t) == 1 and t.isalpha() and t.isupper():
            capitalized += 1
            continue
        if token[0].isupper():
            capitalized += 1

    return capitalized >= 2


def _extract_front_lines(pdf_path: Path, ocr_mode: OCRMode, logger: logging.Logger) -> list[str]:
    lines: list[str] = []
    doc = fitz.open(str(pdf_path))
    try:
        for index in range(min(2, len(doc))):
            page = doc[index]
            extracted = (page.get_text("text") or "").strip()
            if not extracted and ocr_mode in {"auto", "always"}:
                logger.debug("No text found on page %s while inferring author; trying OCR", index + 1)
                extracted = ocr_page(page).strip()
            elif ocr_mode == "always":
                extracted = ocr_page(page).strip()

            cleaned = clean_text(extracted)
            for line in cleaned.splitlines():
                line = line.strip()
                if line:
                    lines.append(line)
            if len(lines) >= 60:
                return lines[:60]
    finally:
        doc.close()
    return lines[:60]


def _extract_contacts(lines: list[str], author_line_indexes: list[int]) -> list[str]:
    contacts: list[str] = []

    for line in lines:
        contacts.extend(_EMAIL_RE.findall(line))
        contacts.extend(_URL_RE.findall(line))

    if author_line_indexes:
        for index in author_line_indexes:
            start = max(0, index - 3)
            end = min(len(lines), index + 4)
            for nearby in lines[start:end]:
                if _AFFILIATION_RE.search(nearby):
                    contacts.append(nearby)

    return _dedupe([c.strip(".,; ") for c in contacts if c.strip(".,; ")])


def infer_authors_from_heuristic(pdf_path: Path, ocr_mode: OCRMode, logger: logging.Logger) -> AuthorExtractionResult:
    lines = _extract_front_lines(pdf_path, ocr_mode=ocr_mode, logger=logger)
    if not lines:
        return AuthorExtractionResult(primary_author=None, authors=[], contacts=[], source="none")

    by_authors: list[str] = []
    authors: list[str] = []
    author_line_indexes: list[int] = []

    for index, line in enumerate(lines):
        if _STOP_HEADER_RE.match(line):
            break

        if line.lower().startswith("by "):
            parsed = _split_authors(line[3:])
            if parsed:
                by_authors.extend(parsed)
                author_line_indexes.append(index)
            continue

        if "," in line:
            parsed = _split_authors(line)
            if parsed:
                authors.extend(parsed)
                author_line_indexes.append(index)
                continue

        if _looks_like_name(line):
            authors.append(line)
            author_line_indexes.append(index)

    deduped_authors = _dedupe(by_authors) if by_authors else _dedupe(authors)
    contacts = _extract_contacts(lines, author_line_indexes=author_line_indexes)

    if not deduped_authors:
        return AuthorExtractionResult(primary_author=None, authors=[], contacts=contacts, source="none")

    return AuthorExtractionResult(
        primary_author=deduped_authors[0],
        authors=deduped_authors,
        contacts=contacts,
        source="heuristic",
    )


def infer_author_info(
    pdf_path: Path,
    *,
    mode: AuthorMode,
    ocr_mode: OCRMode,
    logger: logging.Logger | None = None,
) -> AuthorExtractionResult:
    """Infer author and contacts using metadata, heuristics, or both."""
    if logger is None:
        logger = logging.getLogger(__name__)

    if mode in {"metadata", "auto"}:
        doc = fitz.open(str(pdf_path))
        try:
            metadata = doc.metadata or {}
            meta_author = metadata.get("author")
        finally:
            doc.close()

        if _is_usable_author(meta_author):
            author_value = meta_author.strip()
            return AuthorExtractionResult(
                primary_author=author_value,
                authors=[author_value],
                contacts=[],
                source="metadata",
            )

        if mode == "metadata":
            return AuthorExtractionResult(primary_author=None, authors=[], contacts=[], source="none")

    if mode in {"heuristic", "auto"}:
        return infer_authors_from_heuristic(pdf_path, ocr_mode=ocr_mode, logger=logger)

    return AuthorExtractionResult(primary_author=None, authors=[], contacts=[], source="none")
