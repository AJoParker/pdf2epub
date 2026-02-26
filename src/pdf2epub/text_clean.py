"""Text cleanup utilities for PDF extraction."""

from __future__ import annotations

import re

_HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")
_EXCESS_BLANKS_RE = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalize extracted text for EPUB output.

    - Fixes hyphenation split across lines
    - Normalizes CRLF/CR to LF
    - Collapses excessive blank lines
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _HYPHEN_BREAK_RE.sub(r"\1\2", normalized)
    normalized = _EXCESS_BLANKS_RE.sub("\n\n", normalized)
    return normalized.strip()
