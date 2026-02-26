from __future__ import annotations

from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
from typer.testing import CliRunner

from pdf2epub.cli import app


runner = CliRunner()


def _make_test_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def test_cli_batch_directory_conversion(tmp_path: Path) -> None:
    books_dir = tmp_path / "books"
    books_dir.mkdir()

    first_pdf = books_dir / "a.pdf"
    second_pdf = books_dir / "b.pdf"
    ignored_txt = books_dir / "notes.txt"

    _make_test_pdf(first_pdf, "first document")
    _make_test_pdf(second_pdf, "second document")
    ignored_txt.write_text("not a pdf", encoding="utf-8")

    result = runner.invoke(app, [str(books_dir), "--ocr", "off", "--split-pages", "1"])

    assert result.exit_code == 0, result.stdout
    assert (books_dir / "a.epub").exists()
    assert (books_dir / "b.epub").exists()
