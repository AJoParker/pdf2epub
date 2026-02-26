from __future__ import annotations

from pathlib import Path

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
