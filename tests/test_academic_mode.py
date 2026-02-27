from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

fitz = pytest.importorskip("fitz")

from pdf2epub.convert import convert_pdf_to_academic_epub


def _make_two_page_academic_pdf(path: Path) -> None:
    doc = fitz.open()
    for page_index in range(2):
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 70), f"Paper Title - Page {page_index + 1}", fontsize=14)
        page.insert_textbox(
            fitz.Rect(50, 100, 280, 760),
            "Left column text. " * 40,
            fontsize=10,
        )
        page.insert_textbox(
            fitz.Rect(315, 100, 545, 760),
            "Right column text. " * 40,
            fontsize=10,
        )
    doc.save(path)
    doc.close()


def test_academic_mode_builds_fixed_layout_epub(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    epub_path = tmp_path / "paper.epub"
    _make_two_page_academic_pdf(pdf_path)

    convert_pdf_to_academic_epub(
        input_pdf=pdf_path,
        output_epub=epub_path,
        title="Academic Test",
        author="Researcher",
        lang="en",
        ocr_mode="off",
    )

    assert epub_path.exists()

    with ZipFile(epub_path, "r") as zf:
        names = set(zf.namelist())
        assert "EPUB/pages/page_0001.png" in names
        assert "EPUB/pages/page_0002.png" in names
        assert "EPUB/text/page_0001.xhtml" in names
        assert "EPUB/text/page_0002.xhtml" in names
        assert "EPUB/cover.png" in names

        opf = zf.read("EPUB/content.opf").decode("utf-8")
        first_spine = opf.index('idref="html-page_0001"')
        second_spine = opf.index('idref="html-page_0002"')
        assert first_spine < second_spine
        assert "rendition:layout" in opf
        assert "pre-paginated" in opf
        assert "rendition:spread" in opf
        assert "rendition:orientation" in opf
