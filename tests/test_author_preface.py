from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

fitz = pytest.importorskip("fitz")

from pdf2epub.convert import convert_pdf_to_epub


def _make_pdf(path: Path, lines: list[str], metadata_author: str | None = None) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "\n".join(lines))
    if metadata_author is not None:
        doc.set_metadata({"author": metadata_author})
    doc.save(path)
    doc.close()


def _read_epub(output_epub: Path) -> tuple[str, str]:
    with ZipFile(output_epub, "r") as zf:
        opf_name = next(name for name in zf.namelist() if name.endswith(".opf"))
        opf = zf.read(opf_name).decode("utf-8")
        preface = zf.read("EPUB/preface.xhtml").decode("utf-8")
    return opf, preface


def test_metadata_author_is_preferred(tmp_path: Path) -> None:
    input_pdf = tmp_path / "meta.pdf"
    output_epub = tmp_path / "meta.epub"
    _make_pdf(input_pdf, ["Title", "Body"], metadata_author="Metadata Author")

    convert_pdf_to_epub(input_pdf=input_pdf, output_epub=output_epub, title="Meta", ocr_mode="off")

    opf, preface = _read_epub(output_epub)
    assert "Metadata Author" in opf
    assert "Metadata Author" in preface


def test_heuristic_author_and_contact(tmp_path: Path) -> None:
    input_pdf = tmp_path / "heuristic.pdf"
    output_epub = tmp_path / "heuristic.epub"
    _make_pdf(
        input_pdf,
        [
            "A Great Paper",
            "By Jane Doe, John Smith",
            "Department of Computer Science",
            "jane@example.com",
        ],
    )

    convert_pdf_to_epub(
        input_pdf=input_pdf,
        output_epub=output_epub,
        title="Heuristic",
        ocr_mode="off",
        author_mode="heuristic",
    )

    opf, preface = _read_epub(output_epub)
    assert "Jane Doe" in opf
    assert "Jane Doe" in preface
    assert "John Smith" in preface
    assert "jane@example.com" in preface


def test_no_author_falls_back_to_unknown(tmp_path: Path) -> None:
    input_pdf = tmp_path / "none.pdf"
    output_epub = tmp_path / "none.epub"
    _make_pdf(input_pdf, ["Completely Untitled", "Some body text with no author"]) 

    convert_pdf_to_epub(input_pdf=input_pdf, output_epub=output_epub, title="None", ocr_mode="off")

    opf, preface = _read_epub(output_epub)
    assert "Unknown" in opf
    assert "Author information not found in PDF." in preface
