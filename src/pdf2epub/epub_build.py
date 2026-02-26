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
    preface_authors: list[str] | None = None,
    preface_contacts: list[str] | None = None,
    include_preface: bool = True,
) -> None:
    """Build and write a simple reflowable EPUB from chapter text chunks."""
    book = epub.EpubBook()
    book.set_identifier(identifier)
    book.set_title(title)
    book.set_language(lang)
    book.add_author(author)

    items: list[epub.EpubHtml] = []
    if include_preface:
        author_items = preface_authors or []
        contact_items = preface_contacts or []

        authors_html = "".join(f"<li>{escape(item)}</li>" for item in author_items)
        contacts_html = "".join(f"<li>{escape(item)}</li>" for item in contact_items)
        preface_html = ["<html><head><meta charset='utf-8' /></head><body>", "<h1>Preface</h1>"]

        if author_items:
            preface_html.extend(["<h2>Authors</h2>", f"<ul>{authors_html}</ul>"])
        else:
            preface_html.append("<p>Author information not found in PDF.</p>")

        if contact_items:
            preface_html.extend(["<h2>Contact</h2>", f"<ul>{contacts_html}</ul>"])

        preface_html.append("</body></html>")
        preface = epub.EpubHtml(
            title="Preface",
            file_name="preface.xhtml",
            lang=lang,
            content="".join(preface_html),
        )
        book.add_item(preface)
        items.append(preface)

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
