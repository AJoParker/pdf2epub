# pdf2epub

A small, production-minded CLI tool to convert PDF files into reflowable EPUB files on macOS.

## Features

- Text-based PDF extraction using [PyMuPDF](https://pymupdf.readthedocs.io/)
- EPUB generation with [EbookLib](https://github.com/aerkalov/ebooklib)
- Optional OCR fallback for scanned/image pages via `pytesseract`
- Clean, simple chapter chunking by page count
- Batch conversion from files, directories, and glob patterns

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

### CLI behavior

Input arguments can be:

- PDF files
- Directories (find `*.pdf` in that directory)
- Glob patterns like `*.pdf`

Examples:

```bash
# Single file
pdf2epub input.pdf

# Multiple files
pdf2epub file1.pdf file2.pdf

# Directory
pdf2epub ./books/

# Directory recursively
pdf2epub ./books/ --recursive

# Explicit glob (quoted, expanded by Python)
pdf2epub "*.pdf"
```

### Output behavior

- By default, each input PDF writes an EPUB next to the source file:
  - `report.pdf -> report.epub`
  - `./books/a.pdf -> ./books/a.epub`
- With `-o/--output`:
  - Single input: `-o` is the exact output file path
  - Multiple inputs: `-o` is treated as an output directory

### Options

- `-o, --output`
- `--title` (default: PDF filename stem)
- `--author` (default: `Unknown`)
- `--lang` (default: `en`)
- `--ocr` (`off|auto|always`, default: `auto`)
- `--split-pages N` (default: `10`)
- `--force` (overwrite existing output files)
- `--recursive` (recursive directory scanning)
- `--verbose`

### Shell glob expansion (macOS zsh/bash)

On macOS, zsh/bash typically expands globs before your command runs:

```bash
pdf2epub *.pdf
```

This becomes a list of matching files passed to the CLI. If you quote the pattern:

```bash
pdf2epub "*.pdf"
```

The shell passes the literal string, and `pdf2epub` expands it using Python's `glob.glob()`.

## How it works

1. Resolve input arguments to a deduplicated list of PDF files
2. Extract per-page text with `page.get_text("text")`
3. In `--ocr auto`, OCR pages with very little extracted text (< 50 chars)
4. Clean text (hyphenation/newline normalization)
5. Chunk pages into chapters of `N` pages
6. Write a reflowable EPUB with navigation (NCX + nav)

## Known limitations

- Complex tables may lose structure
- Multi-column layouts can be read out of order
- Mathematical notation is not faithfully preserved
- OCR quality depends on scan quality and Tesseract language data

## Development

Run tests:

```bash
pip install -e '.[dev]'
pytest
```
