# pdf2epub

A small, production-minded CLI tool to convert PDF files into reflowable EPUB files on macOS.

## Features

- Text-based PDF extraction using [PyMuPDF](https://pymupdf.readthedocs.io/)
- EPUB generation with [EbookLib](https://github.com/aerkalov/ebooklib)
- Optional OCR fallback for scanned/image pages via `pytesseract`
- Clean, simple chapter chunking by page count

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
pdf2epub INPUT.pdf -o OUTPUT.epub
```

### Options

- `--title` (default: PDF filename stem)
- `--author` (default: `Unknown`)
- `--lang` (default: `en`)
- `--ocr` (`off|auto|always`, default: `auto`)
- `--split-pages N` (default: `10`)
- `--verbose`

## Examples

Basic conversion:

```bash
pdf2epub book.pdf -o book.epub
```

Force OCR on every page:

```bash
pdf2epub scan.pdf -o scan.epub --ocr always
```

Smaller chapter chunks:

```bash
pdf2epub long.pdf -o long.epub --split-pages 5 --title "My Book" --author "A. Author"
```

## How it works

1. Extract per-page text with `page.get_text("text")`
2. In `--ocr auto`, OCR pages with very little extracted text (< 50 chars)
3. Clean text (hyphenation/newline normalization)
4. Chunk pages into chapters of `N` pages
5. Write a reflowable EPUB with navigation (NCX + nav)

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
