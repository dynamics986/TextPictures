#!/usr/bin/env python3
"""Convert an image to text art rendered as an image."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
except ModuleNotFoundError:
    Image = None
    ImageDraw = None
    ImageFilter = None
    ImageFont = None
    ImageOps = None


DEFAULT_CHARS = "I大布體紐"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
DEFAULT_WIDTH = 180
DEFAULT_FONT_SIZE = 9


def ensure_pillow_installed() -> None:
    """Raise a clear error when Pillow is not installed."""
    if (
        Image is None
        or ImageDraw is None
        or ImageFilter is None
        or ImageFont is None
        or ImageOps is None
    ):
        raise RuntimeError("Pillow is not installed. Please run: pip install pillow")


def is_supported_image(path: Path) -> bool:
    """Return True when the path is a supported image file."""
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def parse_positive_int(value: str) -> int:
    """Parse a positive integer command line option."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc

    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")

    return number


def parse_optional_height(value: str) -> int | None:
    """Parse a positive height, or 0 for automatic aspect-preserving height."""
    try:
        height = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc

    if height < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    if height == 0:
        return None
    return height


def parse_chars(value: str) -> str:
    """Validate the density character string."""
    if len(value) < 2:
        raise argparse.ArgumentTypeError("must have at least 2 characters")
    return value


def brightness_to_char(brightness: int, chars: str) -> str:
    """Map brightness to chars where dark pixels use denser characters."""
    index = round((255 - brightness) / 255 * (len(chars) - 1))
    return chars[index]


def strength_to_char(strength: int, chars: str) -> str:
    """Map edge strength to chars where stronger edges use denser characters."""
    index = round(strength / 255 * (len(chars) - 1))
    return chars[index]


def auto_height(image_width: int, image_height: int, text_width: int) -> int:
    """Estimate text rows so the rendered image keeps the original outline."""
    return max(1, round(text_width * image_height / image_width))


def image_to_text_rows(
    image_path: Path,
    width: int,
    height: int | None,
    chars: str,
    mode: str,
) -> list[str]:
    """Resize an image, convert it to grayscale, then map pixels to text rows."""
    ensure_pillow_installed()

    if not image_path.exists():
        raise FileNotFoundError(f"Input image does not exist: {image_path}")
    if not is_supported_image(image_path):
        raise ValueError(f"Unsupported image format: {image_path}")

    with Image.open(image_path) as image:
        if height is None:
            height = auto_height(image.width, image.height, width)

        resample = getattr(Image, "Resampling", Image).LANCZOS
        image = image.resize((width, height), resample=resample)
        gray_image = image.convert("L")
        if mode == "edge":
            gray_image = ImageOps.autocontrast(gray_image.filter(ImageFilter.FIND_EDGES))

        pixels = gray_image.load()

        rows: list[str] = []
        for y in range(height):
            row_chars = []
            for x in range(width):
                if mode == "edge":
                    row_chars.append(strength_to_char(pixels[x, y], chars))
                else:
                    row_chars.append(brightness_to_char(pixels[x, y], chars))
            rows.append("".join(row_chars))

    return rows


def find_font(font_size: int) -> Any:
    """Return a font that can render Latin and Chinese characters."""
    ensure_pillow_installed()

    font_candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]

    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, font_size)
        except OSError:
            continue

    return ImageFont.load_default()


def render_text_image(rows: list[str], font_size: int = DEFAULT_FONT_SIZE) -> Any:
    """Render text rows into a white-background image."""
    ensure_pillow_installed()

    if not rows:
        rows = [""]

    font = find_font(font_size)
    measure_image = Image.new("RGB", (1, 1), "white")
    draw = ImageDraw.Draw(measure_image)
    sample_chars = set("".join(rows)) or {" "}

    max_char_width = 1
    max_char_height = 1
    for char in sample_chars:
        box = draw.textbbox((0, 0), char, font=font)
        max_char_width = max(max_char_width, box[2] - box[0])
        max_char_height = max(max_char_height, box[3] - box[1])

    if hasattr(font, "getmetrics"):
        ascent, descent = font.getmetrics()
        cell_height = max(max_char_height, ascent + descent)
    else:
        cell_height = max_char_height

    cell_width = max_char_width
    image_width = max(1, max(len(row) for row in rows) * cell_width)
    image_height = max(1, len(rows) * cell_height)
    output_image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(output_image)

    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char != " ":
                draw.text((x * cell_width, y * cell_height), char, fill="black", font=font)

    return output_image


def build_output_path(image_path: Path) -> Path:
    """Build the output image path in the current working directory."""
    return Path.cwd() / f"text_{image_path.name}"


def save_text_image(rows: list[str], output_path: Path, font_size: int = DEFAULT_FONT_SIZE) -> None:
    """Save rendered text rows as an image."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_image = render_text_image(rows, font_size=font_size)

    if output_path.suffix.lower() in {".jpg", ".jpeg"}:
        output_image.save(output_path, "JPEG", quality=95)
    else:
        output_image.save(output_path)


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(description="Convert an image to text art and save it as an image.")
    parser.add_argument("input", type=Path, help="Input image path")
    parser.add_argument(
        "--width",
        type=parse_positive_int,
        default=DEFAULT_WIDTH,
        help=f"Text matrix width, default: {DEFAULT_WIDTH}",
    )
    parser.add_argument(
        "--height",
        type=parse_optional_height,
        default=None,
        help="Text matrix height. Use 0 or omit it to keep the original aspect ratio.",
    )
    parser.add_argument(
        "--font-size",
        type=parse_positive_int,
        default=DEFAULT_FONT_SIZE,
        help=f"Output text font size, default: {DEFAULT_FONT_SIZE}",
    )
    parser.add_argument(
        "--chars",
        type=parse_chars,
        default=DEFAULT_CHARS,
        help=f"Character density dictionary from sparse to dense, default: {DEFAULT_CHARS!r}",
    )
    parser.add_argument(
        "--mode",
        choices=("edge", "tone"),
        default="edge",
        help="edge keeps outlines clearer; tone maps the full grayscale image. Default: edge",
    )
    return parser


def main() -> int:
    """Program entry point."""
    parser = build_parser()
    args = parser.parse_args()

    image_path = args.input.expanduser().resolve()

    try:
        rows = image_to_text_rows(image_path, args.width, args.height, args.chars, args.mode)
        output_path = build_output_path(image_path)
        save_text_image(rows, output_path, font_size=args.font_size)
        print(f"Saved: {output_path}")
    except Exception as exc:  # noqa: BLE001 - print clean CLI errors.
        print(f"Error : {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
