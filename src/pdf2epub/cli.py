"""Command-line interface for pdf2epub."""

from __future__ import annotations

import glob
import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import typer

from .convert import AuthorMode, CoverMode, convert_pdf_to_epub
from .pdf_extract import LayoutMode, OCRMode

try:
    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
except Exception:  # noqa: BLE001 - fallback path for environments without rich.
    Progress = None


app = typer.Typer(add_completion=False)

LOGGER_NAME = "pdf2epub"


@dataclass(frozen=True)
class ConvertTask:
    input_pdf: Path
    output_epub: Path
    title: str
    author: str | None
    lang: str
    ocr_mode: OCRMode
    split_pages: int
    author_mode: AuthorMode
    no_preface: bool
    no_brand: bool
    logo_path: Path | None
    cover_mode: CoverMode
    layout: LayoutMode
    force: bool


@dataclass(frozen=True)
class ConvertResult:
    status: Literal["ok", "skip", "fail"]
    input_pdf: Path
    output_epub: Path
    error: str | None = None


@dataclass(frozen=True)
class BatchSummary:
    total: int
    converted: int
    skipped: int
    failed: int


def _is_pattern(value: str) -> bool:
    return any(char in value for char in "*?[]")


def _expand_directory(directory: Path, recursive: bool) -> list[Path]:
    iterator = directory.rglob("*.pdf") if recursive else directory.glob("*.pdf")
    return [path for path in iterator if path.is_file() and path.suffix.lower() == ".pdf"]


def _dedupe_key(path: Path) -> str:
    resolved = str(path.resolve())
    return resolved.lower()


def resolve_input_pdfs(inputs: list[str], recursive: bool, logger: logging.Logger) -> list[Path]:
    """Resolve CLI input arguments into a deduplicated, stable, sorted list of PDFs."""
    discovered: list[Path] = []
    seen: set[str] = set()

    for raw in inputs:
        candidate = Path(raw)

        if candidate.is_dir():
            matches = _expand_directory(candidate, recursive=recursive)
        elif candidate.is_file():
            matches = [candidate] if candidate.suffix.lower() == ".pdf" else []
            if not matches:
                logger.warning("Skipping non-PDF file: %s", candidate)
        else:
            matches = []
            if _is_pattern(raw):
                for match_raw in glob.glob(raw, recursive=recursive):
                    match = Path(match_raw)
                    if match.is_file() and match.suffix.lower() == ".pdf":
                        matches.append(match)
            else:
                logger.warning("Input not found, skipping: %s", raw)

        for match in matches:
            key = _dedupe_key(match)
            if key not in seen:
                seen.add(key)
                discovered.append(match)

    return sorted(discovered, key=lambda path: str(path.resolve()).lower())


def _build_output_path(input_pdf: Path, output: Path | None, multiple_inputs: bool) -> Path:
    if output is None:
        return input_pdf.with_suffix(".epub")

    if multiple_inputs:
        return output / f"{input_pdf.stem}.epub"

    return output if output.suffix.lower() == ".epub" else output.with_suffix(".epub")


def _convert_one(task: ConvertTask) -> ConvertResult:
    if task.output_epub.exists() and not task.force:
        return ConvertResult(status="skip", input_pdf=task.input_pdf, output_epub=task.output_epub)

    task.output_epub.parent.mkdir(parents=True, exist_ok=True)

    try:
        convert_pdf_to_epub(
            input_pdf=task.input_pdf,
            output_epub=task.output_epub,
            title=task.title,
            author=task.author,
            lang=task.lang,
            ocr_mode=task.ocr_mode,
            author_mode=task.author_mode,
            no_preface=task.no_preface,
            split_pages=task.split_pages,
            no_brand=task.no_brand,
            logo_path=task.logo_path,
            cover_mode=task.cover_mode,
            layout=task.layout,
        )
    except Exception as exc:  # noqa: BLE001 - keep batch conversion alive per-file.
        return ConvertResult(status="fail", input_pdf=task.input_pdf, output_epub=task.output_epub, error=str(exc))

    return ConvertResult(status="ok", input_pdf=task.input_pdf, output_epub=task.output_epub)


def _default_jobs() -> int:
    cpu_total = os.cpu_count() or 1
    return max(1, cpu_total - 1)


def _bounded_jobs(value: int) -> int:
    cpu_total = os.cpu_count() or 1
    return max(1, min(value, cpu_total))


def run_batch_conversion(tasks: list[ConvertTask], jobs: int, sequential: bool, logger: logging.Logger) -> BatchSummary:
    converted = 0
    skipped = 0
    failed = 0

    def handle_result(result: ConvertResult) -> None:
        nonlocal converted, skipped, failed

        if result.status == "ok":
            converted += 1
            logger.info("Converting: %s -> %s", result.input_pdf, result.output_epub)
            return
        if result.status == "skip":
            skipped += 1
            logger.warning("Exists (use --force): %s", result.output_epub)
            return

        failed += 1
        logger.error("FAIL: %s (%s)", result.input_pdf, result.error)

    if not tasks:
        return BatchSummary(total=0, converted=0, skipped=0, failed=0)

    if Progress is None:
        logger.warning("rich not available; falling back to simple logging progress")
        if sequential:
            for task in tasks:
                handle_result(_convert_one(task))
        else:
            with ProcessPoolExecutor(max_workers=jobs) as executor:
                futures = [executor.submit(_convert_one, task) for task in tasks]
                for future in as_completed(futures):
                    handle_result(future.result())
        return BatchSummary(total=len(tasks), converted=converted, skipped=skipped, failed=failed)

    progress_columns = [
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
    ]

    with Progress(*progress_columns, transient=True) as progress:
        progress_task = progress.add_task("Converting PDFs", total=len(tasks))

        if sequential:
            for task in tasks:
                progress.update(progress_task, description=f"Converting {task.input_pdf.name}")
                handle_result(_convert_one(task))
                progress.advance(progress_task)
        else:
            with ProcessPoolExecutor(max_workers=jobs) as executor:
                future_map = {executor.submit(_convert_one, task): task for task in tasks}
                for future in as_completed(future_map):
                    task = future_map[future]
                    progress.update(progress_task, description=f"Converting {task.input_pdf.name}")
                    handle_result(future.result())
                    progress.advance(progress_task)

    return BatchSummary(total=len(tasks), converted=converted, skipped=skipped, failed=failed)


@app.command()
def main(
    files_or_patterns: list[str] = typer.Argument(..., metavar="FILES_OR_PATTERNS...", help="PDF files, directories, or glob patterns."),
    output: Path | None = typer.Option(None, "-o", "--out", "--output", help="Output EPUB file (single input) or output directory (multiple inputs)."),
    title: str | None = typer.Option(None, "--title", help="Book title (defaults to each input stem)."),
    author: str | None = typer.Option(None, "--author", help="Book author (overrides inference)."),
    lang: str = typer.Option("en", "--lang", help="Book language code."),
    ocr: OCRMode = typer.Option("auto", "--ocr", help="OCR mode: off, auto, always."),
    author_mode: AuthorMode = typer.Option("auto", "--author-mode", help="Author inference mode: metadata, heuristic, auto."),
    no_preface: bool = typer.Option(False, "--no-preface", help="Do not include a preface section in the EPUB."),
    split_pages: int = typer.Option(10, "--split-pages", min=1, help="Pages per chapter."),
    no_brand: bool = typer.Option(False, "--no-brand", help="Generate cover without embedding the logo badge."),
    logo: Path | None = typer.Option(None, "--logo", exists=True, file_okay=True, dir_okay=False, help="Path to logo image used for cover branding."),
    cover_mode: CoverMode = typer.Option("styled", "--cover-mode", help="Cover generation mode: styled or none."),
    layout: LayoutMode = typer.Option("simple", "--layout", help="Layout mode: simple (default block order) or columns (left-to-right ordering)."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing EPUB output file(s)."),
    recursive: bool = typer.Option(False, "--recursive", help="Recursively scan directories for PDFs."),
    jobs: int = typer.Option(_default_jobs(), "-j", "--jobs", min=1, help="Parallel worker processes."),
    sequential: bool = typer.Option(False, "--sequential", help="Disable multiprocessing and run sequentially."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    """Convert one or more PDF files into EPUB files."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s")
    logger = logging.getLogger(LOGGER_NAME)

    input_pdfs = resolve_input_pdfs(files_or_patterns, recursive=recursive, logger=logger)

    if not input_pdfs:
        typer.echo("No PDF files found in inputs. Provide a PDF file, directory, or glob pattern.", err=True)
        raise typer.Exit(code=2)

    multiple_inputs = len(input_pdfs) > 1
    if multiple_inputs and output is not None:
        output.mkdir(parents=True, exist_ok=True)

    tasks = [
        ConvertTask(
            input_pdf=input_pdf,
            output_epub=_build_output_path(input_pdf, output=output, multiple_inputs=multiple_inputs),
            title=title or input_pdf.stem,
            author=author,
            lang=lang,
            ocr_mode=ocr,
            author_mode=author_mode,
            no_preface=no_preface,
            no_brand=no_brand,
            logo_path=logo,
            cover_mode=cover_mode,
            layout=layout,
            split_pages=split_pages,
            force=force,
        )
        for input_pdf in input_pdfs
    ]

    effective_jobs = 1 if sequential else _bounded_jobs(jobs)
    summary = run_batch_conversion(tasks=tasks, jobs=effective_jobs, sequential=sequential, logger=logger)

    typer.echo(f"Total PDFs discovered: {summary.total}")
    typer.echo(f"Converted: {summary.converted}")
    typer.echo(f"Skipped: {summary.skipped}")
    typer.echo(f"Failed: {summary.failed}")

    if summary.failed > 0:
        raise typer.Exit(code=1)


def run() -> None:
    """Entrypoint used by console scripts."""
    app()


if __name__ == "__main__":
    run()
