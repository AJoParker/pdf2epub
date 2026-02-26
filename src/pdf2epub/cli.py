"""Command-line interface for pdf2epub."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from .convert import convert_pdf_to_epub
from .pdf_extract import OCRMode


def main(
    input_pdf: Path = typer.Argument(..., exists=True, readable=True, help="Input PDF path."),
    output: Path = typer.Option(..., "-o", "--output", help="Output EPUB path."),
    title: str | None = typer.Option(None, "--title", help="Book title (defaults to input stem)."),
    author: str = typer.Option("Unknown", "--author", help="Book author."),
    lang: str = typer.Option("en", "--lang", help="Book language code."),
    ocr: OCRMode = typer.Option("auto", "--ocr", help="OCR mode: off, auto, always."),
    split_pages: int = typer.Option(10, "--split-pages", min=1, help="Pages per chapter."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    """Convert INPUT_PDF into an EPUB file."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    effective_title = title or input_pdf.stem

    try:
        convert_pdf_to_epub(
            input_pdf=input_pdf,
            output_epub=output,
            title=effective_title,
            author=author,
            lang=lang,
            ocr_mode=ocr,
            split_pages=split_pages,
            logger=logging.getLogger("pdf2epub"),
        )
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Created EPUB: {output}")


def app() -> None:
    """Entrypoint used by console scripts."""
    typer.run(main)


if __name__ == "__main__":
    app()
