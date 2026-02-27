from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

fitz = pytest.importorskip("fitz")

from pdf2epub.convert import convert_pdf_to_epub


def _make_structured_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()

    page.insert_text((72, 72), "Formatting Test Heading", fontsize=22, fontname="Times-Bold")
    page.insert_text((72, 120), "This paragraph has ", fontsize=12, fontname="Times-Roman")
    page.insert_text((175, 120), "bold", fontsize=12, fontname="Times-Bold")
    page.insert_text((205, 120), " and ", fontsize=12, fontname="Times-Roman")
    page.insert_text((235, 120), "italic", fontsize=12, fontname="Times-Italic")
    page.insert_text((270, 120), " text.", fontsize=12, fontname="Times-Roman")

    page.insert_text((72, 160), "• First bullet", fontsize=12, fontname="Times-Roman")
    page.insert_text((72, 180), "• Second bullet", fontsize=12, fontname="Times-Roman")

    doc.save(path)
    doc.close()


def _chapter_xhtml(epub_path: Path) -> str:
    with ZipFile(epub_path, "r") as zf:
        return zf.read("EPUB/chap_1.xhtml").decode("utf-8")


def test_structured_extraction_preserves_formatting(tmp_path: Path) -> None:
    input_pdf = tmp_path / "structured.pdf"
    output_epub = tmp_path / "structured.epub"
    _make_structured_pdf(input_pdf)

    convert_pdf_to_epub(
        input_pdf=input_pdf,
        output_epub=output_epub,
        title="Structured",
        author="Tester",
        lang="en",
        ocr_mode="off",
        split_pages=1,
    )

    chapter_html = _chapter_xhtml(output_epub)

    assert "<h1>" in chapter_html or "<h2>" in chapter_html
    assert "<strong>" in chapter_html or "<em>" in chapter_html
    assert ("<ul>" in chapter_html and "<li>" in chapter_html) or "•" in chapter_html
