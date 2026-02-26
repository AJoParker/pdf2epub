"""EPUB construction utilities."""

from __future__ import annotations

from html import escape
from pathlib import Path

from ebooklib import epub


def _paragraphs_to_xhtml(paragraphs: list[str]) -> str:
    if not paragraphs:
        return "<p></p>"
    return "\n".join(f"<p>{escape(p)}</p>" for p in paragraphs)


def build_epub(
    chapter_texts: list[str],
    output_path: Path,
    *,
    title: str,
    author: str,
    lang: str,
    identifier: str,
) -> None:
    """Build and write a simple reflowable EPUB from chapter text chunks."""
    book = epub.EpubBook()
    book.set_identifier(identifier)
    book.set_title(title)
    book.set_language(lang)
    book.add_author(author)

    items: list[epub.EpubHtml] = []
    for idx, chapter_text in enumerate(chapter_texts, start=1):
        chapter_title = f"Chapter {idx}"
        paragraphs = [p.strip() for p in chapter_text.split("\n\n") if p.strip()]
        html = (
            "<html><head><meta charset='utf-8' /></head><body>"
            f"<h1>{escape(chapter_title)}</h1>"
            f"{_paragraphs_to_xhtml(paragraphs)}"
            "</body></html>"
        )
        chapter = epub.EpubHtml(
            title=chapter_title,
            file_name=f"chap_{idx}.xhtml",
            lang=lang,
            content=html,
        )
        book.add_item(chapter)
        items.append(chapter)

    book.toc = tuple(items)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *items]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(output_path), book, {})
