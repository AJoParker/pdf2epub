"""OCR utilities used for scanned/image-only PDF pages."""

from __future__ import annotations

from io import BytesIO

import fitz  # type: ignore[import-not-found]
from PIL import Image


def ocr_page(page: fitz.Page) -> str:
    """Render a PDF page to an image and return OCR text.

    Raises RuntimeError with a helpful message if pytesseract isn't installed
    or Tesseract binary is unavailable.
    """
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "OCR requested but pytesseract is not installed. "
            "Install with: pip install pdf2epub[ocr]"
        ) from exc

    pix = page.get_pixmap(dpi=200)
    image = Image.open(BytesIO(pix.tobytes("png")))

    try:
        return pytesseract.image_to_string(image)
    except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "OCR requested but Tesseract is not installed or not in PATH. "
            "On macOS run: brew install tesseract"
        ) from exc
