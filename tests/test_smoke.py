from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image
import pytest

fitz = pytest.importorskip("fitz")

from pdf2epub.convert import convert_pdf_to_epub


def _make_test_pdf(path: Path) -> None:
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Hello from page one.\nThis is a smoke test.")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Hello from page two.\nSecond page content.")
    doc.save(path)
    doc.close()


def _extract_cover_png(epub_path: Path) -> bytes:
    with ZipFile(epub_path, "r") as zf:
        return zf.read("EPUB/cover.png")


def _assert_navy_cover(cover_bytes: bytes) -> None:
    assert cover_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(BytesIO(cover_bytes)).convert("RGB")
    pixel = image.getpixel((20, 20))
    expected = (8, 24, 48)
    for actual, target in zip(pixel, expected, strict=True):
        assert abs(actual - target) <= 3


def test_pdf_to_epub_smoke(tmp_path: Path) -> None:
    input_pdf = tmp_path / "sample.pdf"
    output_epub = tmp_path / "sample.epub"
    _make_test_pdf(input_pdf)

    convert_pdf_to_epub(
        input_pdf=input_pdf,
        output_epub=output_epub,
        title="Smoke Test",
        author="Tester",
        lang="en",
        ocr_mode="off",
        split_pages=1,
    )

    assert output_epub.exists()
    assert output_epub.stat().st_size > 512

    cover_bytes = _extract_cover_png(output_epub)
    _assert_navy_cover(cover_bytes)


def test_cover_is_generated_with_no_brand(tmp_path: Path) -> None:
    input_pdf = tmp_path / "sample_nobrand.pdf"
    output_epub = tmp_path / "sample_nobrand.epub"
    _make_test_pdf(input_pdf)

    convert_pdf_to_epub(
        input_pdf=input_pdf,
        output_epub=output_epub,
        title="Smoke Test",
        author="Tester",
        lang="en",
        ocr_mode="off",
        split_pages=1,
        no_brand=True,
    )

    assert output_epub.exists()
    cover_bytes = _extract_cover_png(output_epub)
    _assert_navy_cover(cover_bytes)
