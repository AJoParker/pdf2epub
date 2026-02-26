"""Command-line interface for pdf2epub."""

from __future__ import annotations

import glob
import logging
from pathlib import Path

import typer

from .convert import convert_pdf_to_epub
from .pdf_extract import OCRMode

app = typer.Typer(add_completion=False)


LOGGER_NAME = "pdf2epub"


def _is_pattern(value: str) -> bool:
    return any(char in value for char in "*?[]")


def _expand_directory(directory: Path, recursive: bool) -> list[Path]:
    iterator = directory.rglob("*.pdf") if recursive else directory.glob("*.pdf")
    return sorted(path for path in iterator if path.is_file())


def resolve_input_pdfs(inputs: list[str], recursive: bool, logger: logging.Logger) -> list[Path]:
    """Resolve CLI input arguments into a deduplicated list of PDF files."""
    discovered: list[Path] = []
    seen: set[Path] = set()

    for raw in inputs:
        candidate = Path(raw)

        if candidate.is_dir():
            matches = _expand_directory(candidate, recursive=recursive)
            for match in matches:
                resolved = match.resolve()
                if resolved not in seen and match.suffix.lower() == ".pdf":
                    discovered.append(match)
                    seen.add(resolved)
            continue

        if candidate.is_file():
            if candidate.suffix.lower() == ".pdf":
                resolved = candidate.resolve()
                if resolved not in seen:
                    discovered.append(candidate)
                    seen.add(resolved)
            else:
                logger.warning("Skipping non-PDF file: %s", candidate)
            continue

        if _is_pattern(raw):
            for match_raw in sorted(glob.glob(raw, recursive=recursive)):
                match = Path(match_raw)
                if not match.is_file() or match.suffix.lower() != ".pdf":
                    continue
                resolved = match.resolve()
                if resolved not in seen:
                    discovered.append(match)
                    seen.add(resolved)
            continue

        logger.warning("Input not found, skipping: %s", raw)

    return discovered


def _build_output_path(input_pdf: Path, output: Path | None, multiple_inputs: bool) -> Path:
    if output is None:
        return input_pdf.with_suffix(".epub")

    if not multiple_inputs:
        return output

    return output / f"{input_pdf.stem}.epub"


@app.command()
def main(
    files_or_patterns: list[str] = typer.Argument(..., metavar="FILES_OR_PATTERNS...", help="PDF files, directories, or glob patterns."),
    output: Path | None = typer.Option(None, "-o", "--output", help="Output EPUB file (single input) or output directory (multiple inputs)."),
    title: str | None = typer.Option(None, "--title", help="Book title (defaults to each input stem)."),
    author: str = typer.Option("Unknown", "--author", help="Book author."),
    lang: str = typer.Option("en", "--lang", help="Book language code."),
    ocr: OCRMode = typer.Option("auto", "--ocr", help="OCR mode: off, auto, always."),
    split_pages: int = typer.Option(10, "--split-pages", min=1, help="Pages per chapter."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing EPUB output file(s)."),
    recursive: bool = typer.Option(False, "--recursive", help="Recursively scan directories for PDFs."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    """Convert one or more PDF files into EPUB files."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    logger = logging.getLogger(LOGGER_NAME)

    input_pdfs = resolve_input_pdfs(files_or_patterns, recursive=recursive, logger=logger)

    if not input_pdfs:
        typer.echo("No PDF files found in inputs. Provide a PDF file, directory, or glob pattern.", err=True)
        raise typer.Exit(code=1)

    multiple_inputs = len(input_pdfs) > 1

    if multiple_inputs and output is not None:
        output.mkdir(parents=True, exist_ok=True)

    success_count = 0
    failed_count = 0

    for input_pdf in input_pdfs:
        output_epub = _build_output_path(input_pdf, output=output, multiple_inputs=multiple_inputs)

        if output_epub.exists() and not force:
            typer.echo(f"Skipping existing output (use --force): {output_epub}", err=True)
            failed_count += 1
            continue

        output_epub.parent.mkdir(parents=True, exist_ok=True)
        effective_title = title or input_pdf.stem
        typer.echo(f"Converting: {input_pdf} -> {output_epub}")

        try:
            convert_pdf_to_epub(
                input_pdf=input_pdf,
                output_epub=output_epub,
                title=effective_title,
                author=author,
                lang=lang,
                ocr_mode=ocr,
                split_pages=split_pages,
                logger=logger,
            )
        except Exception as exc:  # noqa: BLE001 - keep batch conversion alive per-file.
            typer.echo(f"Failed: {input_pdf} ({exc})", err=True)
            failed_count += 1
            continue

        success_count += 1

    typer.echo(f"Success: {success_count}")
    typer.echo(f"Failed: {failed_count}")

    if failed_count > 0:
        raise typer.Exit(code=1)


def run() -> None:
    """Entrypoint used by console scripts."""
    app()


if __name__ == "__main__":
    run()
