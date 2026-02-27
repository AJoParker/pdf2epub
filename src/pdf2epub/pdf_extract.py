"""PDF text extraction logic with optional OCR fallback."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from statistics import median
from typing import Literal

import fitz  # type: ignore[import-not-found]

from .ocr import ocr_page
from .text_clean import clean_text

OCRMode = Literal["off", "auto", "always"]
LayoutMode = Literal["simple", "columns"]

_BOLD_FLAG = 16
_ITALIC_FLAG = 2
_LIST_BULLET_RE = re.compile(r"^\s*([•·\-*])\s+")
_LIST_NUMBER_RE = re.compile(r"^\s*(\d+)([\.)])\s+")


@dataclass(frozen=True)
class InlineSpan:
    text: str
    bold: bool = False
    italic: bool = False


@dataclass(frozen=True)
class ContentBlock:
    kind: Literal["heading", "paragraph", "code", "list"]
    spans_by_line: list[list[InlineSpan]]
    heading_level: int | None = None
    list_type: Literal["ul", "ol"] | None = None


def _join_plain(line: list[InlineSpan]) -> str:
    return "".join(span.text for span in line)


def _line_style(spans: list[dict]) -> list[InlineSpan]:
    styled: list[InlineSpan] = []
    for span in spans:
        text = span.get("text", "")
        if not text:
            continue
        flags = int(span.get("flags", 0))
        font_name = str(span.get("font", "")).lower()
        is_bold = bool(flags & _BOLD_FLAG) or "bold" in font_name
        is_italic = bool(flags & _ITALIC_FLAG) or "italic" in font_name or "oblique" in font_name
        styled.append(InlineSpan(text=text, bold=is_bold, italic=is_italic))
    return styled


def _sort_blocks(blocks: list[dict], layout: LayoutMode) -> list[dict]:
    if layout == "columns":
        return sorted(blocks, key=lambda block: (block.get("bbox", [0, 0, 0, 0])[0], block.get("bbox", [0, 0, 0, 0])[1]))
    return blocks


def _is_heading(line_text: str, line_size: float, page_median: float) -> bool:
    cleaned = line_text.strip()
    return bool(cleaned) and len(cleaned) <= 80 and line_size >= (page_median * 1.25)


def _paragraphize_lines(lines: list[dict]) -> list[list[list[InlineSpan]]]:
    if not lines:
        return []

    heights = [line["bottom"] - line["top"] for line in lines if line["bottom"] > line["top"]]
    baseline_height = median(heights) if heights else 12.0

    paragraphs: list[list[list[InlineSpan]]] = []
    current: list[list[InlineSpan]] = []
    prev: dict | None = None

    for line in lines:
        should_break = False
        if prev is not None:
            gap = line["top"] - prev["bottom"]
            indent_delta = abs(line["left"] - prev["left"])
            prev_text = _join_plain(prev["spans"]).rstrip()
            if gap > baseline_height * 1.3:
                should_break = True
            elif indent_delta > 14:
                should_break = True
            if prev_text.endswith("-") and _join_plain(line["spans"]).lstrip()[:1].islower():
                joined = prev["spans"][:-1] + [InlineSpan(prev["spans"][-1].text[:-1], prev["spans"][-1].bold, prev["spans"][-1].italic)]
                if joined and not joined[-1].text:
                    joined = joined[:-1]
                current[-1] = joined + line["spans"]
                prev = line
                continue

        if should_break and current:
            paragraphs.append(current)
            current = []
        current.append(line["spans"])
        prev = line

    if current:
        paragraphs.append(current)
    return paragraphs


def _is_code_block(lines: list[dict]) -> bool:
    if len(lines) < 2:
        return False
    mono_count = 0
    indented_count = 0
    short_count = 0
    base_left = lines[0]["left"]
    for line in lines:
        fonts = {str(font).lower() for font in line.get("fonts", set())}
        if any("courier" in f or "mono" in f for f in fonts):
            mono_count += 1
        if line["left"] - base_left >= 12:
            indented_count += 1
        if len(_join_plain(line["spans"]).strip()) <= 50:
            short_count += 1

    looks_like_code_shape = indented_count >= max(1, len(lines) // 2) and short_count >= max(2, int(len(lines) * 0.6))
    return mono_count >= max(1, len(lines) // 2) or looks_like_code_shape


def _to_content_blocks(page_dict: dict, layout: LayoutMode) -> list[ContentBlock]:
    text_blocks = [block for block in page_dict.get("blocks", []) if block.get("type") == 0 and block.get("lines")]
    text_blocks = _sort_blocks(text_blocks, layout)

    all_sizes: list[float] = []
    parsed_blocks: list[list[dict]] = []
    for block in text_blocks:
        parsed_lines: list[dict] = []
        for line in block.get("lines", []):
            spans = _line_style(line.get("spans", []))
            if not spans:
                continue
            parsed_lines.append(
                {
                    "spans": spans,
                    "left": float(line.get("bbox", [0, 0, 0, 0])[0]),
                    "top": float(line.get("bbox", [0, 0, 0, 0])[1]),
                    "bottom": float(line.get("bbox", [0, 0, 0, 0])[3]),
                    "size": float(median([float(s.get("size", 0.0)) for s in line.get("spans", []) if s.get("size") is not None]) if line.get("spans") else 0.0),
                    "fonts": {span.get("font", "") for span in line.get("spans", [])},
                }
            )
            if parsed_lines[-1]["size"] > 0:
                all_sizes.append(parsed_lines[-1]["size"])
        if parsed_lines:
            parsed_blocks.append(parsed_lines)

    body_size = median(all_sizes) if all_sizes else 12.0
    out: list[ContentBlock] = []

    for lines in parsed_blocks:
        if _is_code_block(lines):
            out.append(ContentBlock(kind="code", spans_by_line=[line["spans"] for line in lines]))
            continue

        for para_lines in _paragraphize_lines(lines):
            if len(para_lines) == 1:
                single = para_lines[0]
                text = _join_plain(single).strip()
                size = median([line["size"] for line in lines if _join_plain(line["spans"]).strip() == text] or [body_size])
                if _is_heading(text, size, body_size):
                    level = 1 if size >= body_size * 1.6 else 2
                    out.append(ContentBlock(kind="heading", spans_by_line=[single], heading_level=level))
                    continue

                if _LIST_BULLET_RE.match(text):
                    stripped = _LIST_BULLET_RE.sub("", text, count=1)
                    out.append(ContentBlock(kind="list", spans_by_line=[[InlineSpan(stripped)]], list_type="ul"))
                    continue
                if _LIST_NUMBER_RE.match(text):
                    stripped = _LIST_NUMBER_RE.sub("", text, count=1)
                    out.append(ContentBlock(kind="list", spans_by_line=[[InlineSpan(stripped)]], list_type="ol"))
                    continue

            out.append(ContentBlock(kind="paragraph", spans_by_line=para_lines))

    return out


def extract_pages_content(
    pdf_path: str,
    *,
    ocr_mode: OCRMode = "auto",
    low_text_threshold: int = 50,
    layout: LayoutMode = "simple",
    logger: logging.Logger | None = None,
) -> list[list[ContentBlock]]:
    """Extract structured content from each PDF page."""
    if logger is None:
        logger = logging.getLogger(__name__)

    doc = fitz.open(pdf_path)
    try:
        pages: list[list[ContentBlock]] = []
        for index, page in enumerate(doc):
            extracted_text = (page.get_text("text") or "").strip()

            should_ocr = False
            if ocr_mode == "always":
                should_ocr = True
            elif ocr_mode == "auto" and len(extracted_text) < low_text_threshold:
                should_ocr = True

            if should_ocr:
                logger.debug("Using OCR for page %s (extracted_chars=%s)", index + 1, len(extracted_text))
                ocr_text = clean_text(ocr_page(page).strip())
                if ocr_text:
                    pages.append([ContentBlock(kind="paragraph", spans_by_line=[[InlineSpan(ocr_text)]])])
                else:
                    pages.append([])
                continue

            page_dict = page.get_text("dict")
            pages.append(_to_content_blocks(page_dict, layout=layout))

        return pages
    finally:
        doc.close()
