#!/usr/bin/env python3
"""Convert images to ASCII art JPG files."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from PIL.Image import Image as PillowImage
    from PIL.ImageFont import FreeTypeFont, ImageFont as PillowFont

try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError:
    Image = None
    ImageDraw = None
    ImageFont = None


ASCII_CHARS = "M&$B%0eol1v!'=+;:."
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
VALID_SCALES = (0.1, 0.2, 0.25, 0.5, 1.0)
LOW_ALPHA_THRESHOLD = 20
DEFAULT_MAX_BYTES = 1_000_000


def ensure_pillow_installed() -> None:
    """Raise a clear error when Pillow is not available."""
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("Pillow is not installed. Please run: pip install pillow")


def is_supported_image(path: Path) -> bool:
    """Return True when path looks like a supported image file."""
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def parse_scale(value: str) -> float:
    """Parse and validate the scale command line argument."""
    try:
        scale = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("scale must be a number") from exc

    if scale not in VALID_SCALES:
        valid_values = ", ".join(str(item) for item in VALID_SCALES)
        raise argparse.ArgumentTypeError(f"scale must be one of: {valid_values}")

    return scale


def parse_max_mb(value: str) -> float:
    """Parse and validate the max output size argument."""
    try:
        max_mb = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("max-mb must be a number") from exc

    if max_mb <= 0:
        raise argparse.ArgumentTypeError("max-mb must be greater than 0")

    return max_mb


def iter_images(folder: Path) -> Iterable[Path]:
    """Yield supported images directly inside a folder."""
    for path in sorted(folder.iterdir()):
        if is_supported_image(path):
            yield path


def pixel_to_char(red: int, green: int, blue: int, alpha: int | None = None) -> str:
    """Convert one pixel to an ASCII character."""
    if alpha is not None and alpha <= LOW_ALPHA_THRESHOLD:
        return " "

    gray = 0.299 * red + 0.578 * green + 0.114 * blue
    index = int(gray / 255 * (len(ASCII_CHARS) - 1))
    return ASCII_CHARS[index]


def image_to_ascii_rows(image_path: Path, scale: float) -> list[str]:
    """Read an image and convert sampled pixels to ASCII rows."""
    ensure_pillow_installed()
    x_step = max(1, int(1 / scale))
    y_step = max(1, int(2 / scale))

    with Image.open(image_path) as image:
        image = image.convert("RGBA")
        width, height = image.size
        pixels = image.load()

        rows: list[str] = []
        for y in range(0, height, y_step):
            chars: list[str] = []
            for x in range(0, width, x_step):
                red, green, blue, alpha = pixels[x, y]
                chars.append(pixel_to_char(red, green, blue, alpha))
            rows.append("".join(chars))

    return rows


def save_ascii_txt(rows: list[str], output_path: Path) -> None:
    """Save ASCII rows as a plain text file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(rows), encoding="utf-8")


def find_monospace_font(font_size: int) -> FreeTypeFont | PillowFont:
    """Return a usable monospace font, falling back to Pillow's default font."""
    ensure_pillow_installed()
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/local/share/fonts/DejaVuSansMono.ttf",
        "/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/lucon.ttf",
    ]

    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, font_size)
        except OSError:
            continue

    try:
        return ImageFont.truetype("DejaVuSansMono.ttf", font_size)
    except OSError:
        return ImageFont.load_default()


def downsample_rows(rows: list[str], step: int) -> list[str]:
    """Reduce ASCII rows and columns by keeping every nth item."""
    if step <= 1:
        return rows

    sampled_rows = rows[::step]
    return [row[::step] for row in sampled_rows]


def render_ascii_image(rows: list[str], font_size: int) -> PillowImage:
    """Render ASCII rows to a white-background, black-text image."""
    ensure_pillow_installed()
    if not rows:
        rows = [""]

    font = find_monospace_font(font_size)
    longest_line = max(rows, key=len, default="")

    measure_image = Image.new("RGB", (1, 1), "white")
    draw = ImageDraw.Draw(measure_image)
    char_box = draw.textbbox((0, 0), "M", font=font)
    line_box = draw.textbbox((0, 0), longest_line or " ", font=font)

    char_width = max(1, char_box[2] - char_box[0])
    if hasattr(font, "getmetrics"):
        ascent, descent = font.getmetrics()
        line_height = max(1, ascent + descent)
    else:
        line_height = max(1, char_box[3] - char_box[1])
    text_width = max(char_width, line_box[2] - line_box[0])
    text_height = line_height * len(rows)

    padding = max(8, font_size)
    image_width = text_width + padding * 2
    image_height = text_height + padding * 2

    output_image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(output_image)

    y = padding
    for row in rows:
        draw.text((padding, y), row, fill="black", font=font)
        y += line_height

    return output_image


def save_ascii_jpg(
    rows: list[str],
    output_path: Path,
    font_size: int = 12,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> None:
    """Save ASCII rows as a JPG image, reducing detail to stay under max_bytes."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    qualities = (85, 75, 65, 55, 45, 35)
    sample_step = 1

    while True:
        current_rows = downsample_rows(rows, sample_step)
        output_image = render_ascii_image(current_rows, font_size)

        best_data = b""
        for quality in qualities:
            buffer = BytesIO()
            output_image.save(buffer, "JPEG", quality=quality, optimize=True)
            data = buffer.getvalue()
            best_data = data
            if len(data) <= max_bytes:
                output_path.write_bytes(data)
                return

        if len(current_rows) <= 1 and max((len(row) for row in current_rows), default=0) <= 1:
            output_path.write_bytes(best_data)
            return

        sample_step += 1


def build_output_path(image_path: Path) -> Path:
    """Build an output path in the current working directory."""
    if image_path.suffix.lower() in {".jpg", ".jpeg"}:
        filename = f"output_{image_path.name}"
    else:
        filename = f"output_{image_path.stem}.jpg"
    return Path.cwd() / filename


def convert_image(image_path: Path, scale: float, max_bytes: int = DEFAULT_MAX_BYTES) -> Path:
    """Convert one image to an ASCII JPG and return the output path."""
    if not is_supported_image(image_path):
        raise ValueError(f"Unsupported image format: {image_path}")

    rows = image_to_ascii_rows(image_path, scale)
    output_path = build_output_path(image_path)
    save_ascii_jpg(rows, output_path, max_bytes=max_bytes)
    return output_path


def convert_path(input_path: Path, scale: float, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
    """Convert a single image or all supported images directly inside a folder."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    if input_path.is_file():
        if not is_supported_image(input_path):
            raise ValueError(f"Unsupported image format: {input_path}")

        output_path = convert_image(input_path, scale, max_bytes=max_bytes)
        print(f"Converted: {input_path} -> {output_path}")
        return

    if not input_path.is_dir():
        raise ValueError(f"Input path is not a file or directory: {input_path}")

    image_paths = list(iter_images(input_path))
    if not image_paths:
        print(f"No supported images found in directory: {input_path}")
        return

    success_count = 0
    fail_count = 0

    for image_path in image_paths:
        try:
            output_path = convert_image(image_path, scale, max_bytes=max_bytes)
        except Exception as exc:  # noqa: BLE001 - keep batch conversion going.
            fail_count += 1
            print(f"Conversion failed: {image_path}; reason: {exc}")
            continue

        success_count += 1
        print(f"Converted: {image_path} -> {output_path}")

    print(f"Done: {success_count} succeeded, {fail_count} failed.")


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(description="Convert images to ASCII art JPG files.")
    parser.add_argument("input", type=Path, help="Input image file or directory")
    parser.add_argument(
        "--scale",
        type=parse_scale,
        default=0.25,
        help="Scale factor; choices: 0.1, 0.2, 0.25, 0.5, 1.0 (default: 0.25)",
    )
    parser.add_argument(
        "--max-mb",
        type=parse_max_mb,
        default=1.0,
        help="Maximum output JPG size in MB (default: 1.0)",
    )
    return parser


def main() -> int:
    """Program entry point."""
    parser = build_parser()
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    max_bytes = int(args.max_mb * 1_000_000)

    try:
        convert_path(input_path, args.scale, max_bytes=max_bytes)
    except Exception as exc:  # noqa: BLE001 - print clean CLI errors.
        print(f"Error: {exc}")
        return 1

    print(f"Output directory: {Path.cwd()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
