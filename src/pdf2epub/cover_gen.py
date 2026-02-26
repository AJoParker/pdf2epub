"""Cover generation utilities for EPUB output."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COVER_WIDTH = 1600
COVER_HEIGHT = 2400
COVER_SIZE = (COVER_WIDTH, COVER_HEIGHT)
BACKGROUND_COLOR = (8, 24, 48)
TEXT_COLOR = (245, 245, 245)
LOGO_BADGE_FILL = (0, 0, 0, 89)  # rgba(0,0,0,0.35)
LOGO_BADGE_RADIUS = 24
LOGO_BADGE_PADDING = 24
LOGO_BADGE_MARGIN = 60
DEFAULT_TITLE_SIZE = 96
DEFAULT_AUTHOR_SIZE = 48
MAX_TEXT_WIDTH = int(COVER_WIDTH * 0.8)


def _default_logo_path() -> Path | None:
    repo_root_logo = Path(__file__).resolve().parents[2] / "embeddedimg.png"
    if repo_root_logo.exists():
        return repo_root_logo
    return None


def _fit_font_for_lines(draw: ImageDraw.ImageDraw, text: str, max_width: int, base_size: int) -> tuple[ImageFont.ImageFont, list[str], int]:
    words = text.split() or [""]

    def wrap_text(font: ImageFont.ImageFont) -> list[str]:
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            candidate = " ".join([*current, word]).strip()
            if not candidate:
                continue
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width or not current:
                current.append(word)
            else:
                lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines or [""]

    size = max(8, base_size)
    while size >= 8:
        font = ImageFont.load_default(size=size)
        lines = wrap_text(font)
        line_widths = [draw.textbbox((0, 0), line, font=font)[2] for line in lines]
        if max(line_widths, default=0) <= max_width:
            return font, lines, size
        size -= 2

    font = ImageFont.load_default(size=8)
    return font, wrap_text(font), 8


def _draw_multiline_center(draw: ImageDraw.ImageDraw, text: str, top: int, base_size: int) -> int:
    font, lines, _ = _fit_font_for_lines(draw, text, MAX_TEXT_WIDTH, base_size)
    line_bbox = draw.textbbox((0, 0), "Ag", font=font)
    line_height = (line_bbox[3] - line_bbox[1]) + 12

    y = top
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (COVER_WIDTH - line_width) // 2
        draw.text((x, y), line, font=font, fill=TEXT_COLOR)
        y += line_height
    return y


def _load_logo(logo_path: Path | None) -> Image.Image | None:
    path = logo_path if logo_path else _default_logo_path()
    if path is None or not path.exists():
        return None
    return Image.open(path).convert("RGBA")


def _draw_logo_badge(canvas: Image.Image, logo_path: Path | None) -> None:
    logo = _load_logo(logo_path)
    if logo is None:
        return

    draw = ImageDraw.Draw(canvas, "RGBA")
    max_logo_width = int(COVER_WIDTH * 0.15)
    if logo.width > max_logo_width:
        ratio = max_logo_width / logo.width
        logo = logo.resize((max_logo_width, max(1, int(logo.height * ratio))), Image.Resampling.LANCZOS)

    badge_width = logo.width + LOGO_BADGE_PADDING * 2
    badge_height = logo.height + LOGO_BADGE_PADDING * 2
    badge_x1 = COVER_WIDTH - LOGO_BADGE_MARGIN - badge_width
    badge_y1 = COVER_HEIGHT - LOGO_BADGE_MARGIN - badge_height
    badge_x2 = badge_x1 + badge_width
    badge_y2 = badge_y1 + badge_height

    draw.rounded_rectangle(
        [(badge_x1, badge_y1), (badge_x2, badge_y2)],
        radius=LOGO_BADGE_RADIUS,
        fill=LOGO_BADGE_FILL,
    )

    logo_x = badge_x1 + LOGO_BADGE_PADDING
    logo_y = badge_y1 + LOGO_BADGE_PADDING
    canvas.alpha_composite(logo, (logo_x, logo_y))


def generate_cover_png(
    title: str,
    author: str,
    *,
    include_branding: bool = True,
    logo_path: Path | None = None,
) -> bytes:
    """Generate styled 1600x2400 cover PNG bytes."""
    cover = Image.new("RGBA", COVER_SIZE, BACKGROUND_COLOR + (255,))
    draw = ImageDraw.Draw(cover)

    title_top = int(COVER_HEIGHT * 0.3)
    after_title = _draw_multiline_center(draw, title.strip() or "Untitled", title_top, DEFAULT_TITLE_SIZE)
    _draw_multiline_center(draw, author.strip() or "Unknown", after_title + 70, DEFAULT_AUTHOR_SIZE)

    if include_branding:
        _draw_logo_badge(cover, logo_path=logo_path)

    output = BytesIO()
    cover.convert("RGB").save(output, format="PNG")
    return output.getvalue()
