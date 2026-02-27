from __future__ import annotations

import logging
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")

from pdf2epub.cli import ConvertTask, resolve_input_pdfs, run_batch_conversion


def _make_test_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def test_batch_conversion_and_force_skip_behavior(tmp_path: Path) -> None:
    books_dir = tmp_path / "books"
    books_dir.mkdir()

    pdf_a = books_dir / "a.pdf"
    pdf_b = books_dir / "b.pdf"
    pdf_c = books_dir / "c.pdf"

    _make_test_pdf(pdf_a, "document A")
    _make_test_pdf(pdf_b, "document B")
    _make_test_pdf(pdf_c, "document C")

    existing_epub = books_dir / "b.epub"
    existing_epub.write_bytes(b"already here")

    logger = logging.getLogger("test-batch")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())

    tasks_without_force = [
        ConvertTask(
            input_pdf=path,
            output_epub=path.with_suffix(".epub"),
            title=path.stem,
            author="Tester",
            lang="en",
            ocr_mode="off",
            split_pages=1,
            author_mode="auto",
            no_preface=False,
            no_brand=False,
            logo_path=None,
            cover_mode="styled",
            layout="simple",
            force=False,
            academic=False,
        )
        for path in [pdf_a, pdf_b, pdf_c]
    ]

    summary = run_batch_conversion(tasks_without_force, jobs=1, sequential=True, logger=logger)

    assert summary.total == 3
    assert summary.converted == 2
    assert summary.skipped == 1
    assert summary.failed == 0
    assert (books_dir / "a.epub").exists()
    assert (books_dir / "c.epub").exists()
    assert existing_epub.read_bytes() == b"already here"

    tasks_with_force = [
        ConvertTask(
            input_pdf=pdf_b,
            output_epub=existing_epub,
            title="b",
            author="Tester",
            lang="en",
            ocr_mode="off",
            split_pages=1,
            author_mode="auto",
            no_preface=False,
            no_brand=False,
            logo_path=None,
            cover_mode="styled",
            layout="simple",
            force=True,
            academic=False,
        )
    ]

    force_summary = run_batch_conversion(tasks_with_force, jobs=1, sequential=True, logger=logger)

    assert force_summary.total == 1
    assert force_summary.converted == 1
    assert force_summary.skipped == 0
    assert force_summary.failed == 0
    assert existing_epub.exists()
    assert existing_epub.read_bytes()[:2] == b"PK"


def test_literal_glob_pattern_expands(tmp_path: Path) -> None:
    first_pdf = tmp_path / "first.pdf"
    second_pdf = tmp_path / "second.pdf"
    ignored = tmp_path / "ignore.txt"

    _make_test_pdf(first_pdf, "first")
    _make_test_pdf(second_pdf, "second")
    ignored.write_text("nope", encoding="utf-8")

    logger = logging.getLogger("test-glob")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())

    pattern = str(tmp_path / "*.pdf")
    resolved = resolve_input_pdfs([pattern], recursive=False, logger=logger)

    assert resolved == [first_pdf, second_pdf]
