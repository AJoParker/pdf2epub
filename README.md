# pdf2epub

A small, production-minded CLI tool to convert PDF files into reflowable EPUB files on macOS.

## Features

- Structured text extraction using [PyMuPDF](https://pymupdf.readthedocs.io/) (`dict` blocks/lines/spans)
- EPUB generation with [EbookLib](https://github.com/aerkalov/ebooklib)
- Optional OCR fallback for scanned/image pages via `pytesseract`
- Clean, simple chapter chunking by page count
- Batch conversion from files, directories, and glob patterns
- Parallel conversion with process workers (`--jobs`)
- Rich progress bar for batch runs
- Author inference from PDF metadata/front matter
- EPUB preface page with detected authors/contact details (best-effort)

## Requirements

- Python 3.10+
- macOS (Apple Silicon or Intel)
- Optional OCR binary:
  - `brew install tesseract`

## Install (macOS + venv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

If you want OCR support:

```bash
brew install tesseract
pip install -e '.[ocr]'
```

## Usage

```bash
pdf2epub FILES_OR_PATTERNS...
```

### Core examples

```bash
# Single
pdf2epub input.pdf

# Multiple
pdf2epub a.pdf b.pdf

# Glob expanded by shell
pdf2epub *.pdf

# Quoted glob expanded in-app
pdf2epub "*.pdf"

# Directory
pdf2epub ./books/

# Recursive directory scan
pdf2epub ./books/ --recursive

# Quoted glob + parallel jobs
pdf2epub "*.pdf" --jobs 6
```

### Input discovery rules

Each positional input can be:

- A PDF file (included)
- A directory:
  - direct `*.pdf` children
  - recursive `**/*.pdf` when `--recursive` is used
- A glob pattern (expanded by Python when passed literally, e.g. `"*.pdf"`)

Discovered PDFs are deduplicated and processed in deterministic sorted order.

### Output behavior

- Default: output is next to each source PDF using the same stem:
  - `report.pdf -> report.epub`
  - `./books/a.pdf -> ./books/a.epub`
- With `-o/--out`:
  - Single discovered PDF: treated as an output file path (coerced to `.epub` if needed)
  - Multiple discovered PDFs: treated as an output directory (`out_dir/<stem>.epub`)


### Author inference and preface

By default (`--author-mode auto`), each PDF is processed independently with this order:

1. PDF metadata author (`doc.metadata["author"]`)
2. Heuristic parsing from the first 1-2 pages (`By ...`, name-like lines near the top)
3. Fallback to `Unknown`

`--author` overrides inference completely for EPUB metadata.

Contact details in the preface are best-effort and include only values detected from PDF text (emails/URLs and nearby affiliation lines).

Options:

- `--author-mode metadata` -> use metadata only
- `--author-mode heuristic` -> use heuristic only
- `--author-mode auto` -> metadata then heuristic fallback
- `--no-preface` -> do not include the preface page
- `--cover-mode styled|none` -> generate branded navy cover or disable cover generation
- `--no-brand` -> keep styled cover but hide the logo badge
- `--logo PATH` -> custom logo for bottom-right cover badge
- `--layout simple|columns` -> keep native block order (`simple`, default) or try left-to-right block ordering (`columns`)

When preface is enabled, TOC/spine order starts with **Preface**, then Chapter 1, Chapter 2, etc.

### Existing output files

- Without `--force`: existing output is skipped and reported as skipped
- With `--force`: output is overwritten

### Parallel and progress options

- `-j, --jobs N`
  - Default: `cpu_count() - 1`
  - Min: `1`
  - Max: `cpu_count()`
- `--sequential`
  - Forces single-process conversion (helpful for debugging)

Batch runs use a Rich progress bar showing total and completed counts plus a current file label.

### Exit codes and summary

End-of-run summary includes:

- Total PDFs discovered
- Converted
- Skipped
- Failed

Exit code:

- `0` when no failures
- `1` when one or more conversions fail
- `2` when no PDFs are discovered

### Shell glob behavior on macOS (zsh/bash)

On macOS shells, unquoted globs are usually expanded before the CLI starts:

```bash
pdf2epub *.pdf
```

Quoted globs are passed literally, so the CLI performs expansion:

```bash
pdf2epub "*.pdf"
```

Both forms are supported.

## How it works

1. Resolve inputs into a deduplicated list of PDFs
2. Build one conversion task per PDF
3. Run tasks sequentially or in parallel workers
4. Extract per-page structured text with `page.get_text("dict")`
5. In `--ocr auto`, OCR pages with very little extracted text (< 50 chars)
6. Clean text (hyphenation/newline normalization)
7. Reconstruct paragraphs/headings/lists/code blocks with geometry + font heuristics
8. Chunk pages into chapters of `N` pages
9. Write reflowable EPUB with navigation (NCX + nav)

## Known limitations

- Pixel-perfect PDF layout parity is not guaranteed in reflowable EPUB output.
- Complex tables may lose structure.
- Multi-column layouts can be read out of order (use `--layout columns` as a best-effort alternative).
- Mathematical notation is not faithfully preserved.
- OCR quality depends on scan quality and Tesseract language data; OCR output is plain text and does not preserve inline formatting.
- For highest layout fidelity, a fixed-layout EPUB mode is future work.

## Development

Contributor guide: see [`AGENTS.md`](AGENTS.md) for repository conventions and PR expectations.

Run tests:

```bash
pip install -e '.[dev]'
pytest
```
