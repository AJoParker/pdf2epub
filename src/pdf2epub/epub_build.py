"""EPUB construction utilities."""

from __future__ import annotations

from html import escape
from pathlib import Path

from ebooklib import epub

from .pdf_extract import ContentBlock, InlineSpan


def _render_spans(spans: list[InlineSpan]) -> str:
    chunks: list[str] = []
    for span in spans:
        text = escape(span.text)
        if span.bold and span.italic:
            text = f"<strong><em>{text}</em></strong>"
        elif span.bold:
            text = f"<strong>{text}</strong>"
        elif span.italic:
            text = f"<em>{text}</em>"
        chunks.append(text)
    return "".join(chunks)


def _render_block_content(lines: list[list[InlineSpan]], preserve_breaks: bool = False) -> str:
    rendered_lines = [_render_spans(line) for line in lines]
    return "\n".join(rendered_lines) if preserve_breaks else "<br/>".join(rendered_lines)


def _blocks_to_xhtml(blocks: list[ContentBlock]) -> str:
    if not blocks:
        return "<p></p>"

    html_parts: list[str] = []
    pending_list_type: str | None = None

    def flush_list() -> None:
        nonlocal pending_list_type
        if pending_list_type is not None:
            html_parts.append(f"</{pending_list_type}>")
            pending_list_type = None

    for block in blocks:
        if block.kind == "list":
            list_type = block.list_type or "ul"
            if pending_list_type != list_type:
                flush_list()
                html_parts.append(f"<{list_type}>")
                pending_list_type = list_type
            html_parts.append(f"<li>{_render_block_content(block.spans_by_line)}</li>")
            continue

        flush_list()
        if block.kind == "heading":
            heading_level = block.heading_level or 2
            html_parts.append(f"<h{heading_level}>{_render_block_content(block.spans_by_line)}</h{heading_level}>")
        elif block.kind == "code":
            html_parts.append(f"<pre><code>{_render_block_content(block.spans_by_line, preserve_breaks=True)}</code></pre>")
        else:
            html_parts.append(f"<p>{_render_block_content(block.spans_by_line)}</p>")

    flush_list()
    return "\n".join(html_parts)


def build_epub(
    chapter_blocks: list[list[ContentBlock]],
    output_path: Path,
    *,
    title: str,
    author: str,
    lang: str,
    identifier: str,
    preface_authors: list[str] | None = None,
    preface_contacts: list[str] | None = None,
    include_preface: bool = True,
    cover_png_bytes: bytes | None = None,
) -> None:
    """Build and write a simple reflowable EPUB from chapter text chunks."""
    book = epub.EpubBook()
    book.set_identifier(identifier)
    book.set_title(title)
    book.set_language(lang)
    book.add_author(author)
    if cover_png_bytes:
        book.set_cover("cover.png", cover_png_bytes)

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

    for idx, chapter_content in enumerate(chapter_blocks, start=1):
        chapter_title = f"Chapter {idx}"
        html = (
            "<html><head><meta charset='utf-8' /></head><body>"
            f"<h1>{escape(chapter_title)}</h1>"
            f"{_blocks_to_xhtml(chapter_content)}"
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
