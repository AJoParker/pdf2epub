"""Fixed-layout EPUB (EPUB3) builder for academic PDFs."""

from __future__ import annotations

from pathlib import Path

import fitz
from ebooklib import epub


def _page_xhtml(image_href: str, width: int, height: int, lang: str) -> str:
    return f"""<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width={width},height={height}\" />
    <title>Page</title>
    <link rel=\"stylesheet\" type=\"text/css\" href=\"../styles/fixed.css\" />
  </head>
  <body lang=\"{lang}\">
    <img src=\"{image_href}\" alt=\"PDF page image\" />
  </body>
</html>
"""


def build_academic_epub(
    pdf_path: Path,
    epub_path: Path,
    *,
    title: str,
    author: str,
    lang: str,
    identifier: str,
    cover_bytes: bytes | None,
    render_dpi: int = 200,
    image_ext: str = "png",
) -> None:
    """Build a fixed-layout EPUB where each PDF page is rendered as an image."""
    if image_ext not in {"png", "jpg", "jpeg"}:
        raise ValueError("image_ext must be one of: png, jpg, jpeg")

    book = epub.EpubBook()
    book.set_identifier(identifier)
    book.set_title(title)
    book.set_language(lang)
    book.add_author(author)

    if cover_bytes:
        book.set_cover("cover.png", cover_bytes)

    book.add_metadata(None, "meta", "pre-paginated", {"property": "rendition:layout"})
    book.add_metadata(None, "meta", "none", {"property": "rendition:spread"})
    book.add_metadata(None, "meta", "auto", {"property": "rendition:orientation"})

    stylesheet = epub.EpubItem(
        uid="fixed-layout-css",
        file_name="styles/fixed.css",
        media_type="text/css",
        content=(
            "html, body { margin: 0; padding: 0; width: 100%; height: 100%; }\n"
            "img { width: 100vw; height: 100vh; object-fit: contain; display: block; }\n"
        ).encode("utf-8"),
    )
    book.add_item(stylesheet)

    pages: list[epub.EpubHtml] = []

    with fitz.open(pdf_path) as document:
        if document.page_count == 0:
            raise RuntimeError("No pages found in input PDF")

        for index, page in enumerate(document, start=1):
            page_name = f"page_{index:04d}"
            page_rect = page.rect
            width = max(1, round(page_rect.width))
            height = max(1, round(page_rect.height))

            pix = page.get_pixmap(dpi=render_dpi, alpha=False)
            image_bytes = pix.tobytes(output=image_ext)
            image_item = epub.EpubItem(
                uid=f"img-{page_name}",
                file_name=f"pages/{page_name}.{image_ext}",
                media_type="image/png" if image_ext == "png" else "image/jpeg",
                content=image_bytes,
            )
            book.add_item(image_item)

            html = epub.EpubHtml(
                uid=f"html-{page_name}",
                title=f"Page {index}",
                file_name=f"text/{page_name}.xhtml",
                lang=lang,
                content=_page_xhtml(f"../pages/{page_name}.{image_ext}", width, height, lang),
            )
            html.add_item(stylesheet)
            book.add_item(html)
            pages.append(html)

    toc_entries: list[epub.Link | epub.EpubHtml] = []
    if pages:
        toc_entries.append(epub.Link(pages[0].file_name, "Pages", "pages"))
    toc_entries.extend(pages)

    book.toc = tuple(toc_entries)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *pages]

    epub_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(epub_path), book, {})
