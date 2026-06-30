"""Generate a Chinese-character density mosaic from an input image."""

from __future__ import annotations

import logging
import random
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError as exc:
    missing_name = exc.name or "a required package"
    LOGGER.error("Missing dependency: %s", missing_name)
    LOGGER.error("Install dependencies with: uv sync")
    sys.exit(1)


INPUT_CANDIDATES = [Path("input.jpg"), Path("input.png")]
DETAIL_PATH = Path("output_detail.png")
BLUR_PATH = Path("output_blur.png")
COMPARE_PATH = Path("output_compare.png")

GRID_SIZE = 15
OUTPUT_SCALE = 30
CELL_FONT_SIZE = 27
MAX_FULL_BLUR_PIXELS = 80_000_000
MAX_PREVIEW_SIDE = 2400
MAX_COMPARE_PANEL_SIDE = 1600

SIDE_TEXT = "富强民主文明和谐自由平等公正法治爱国敬业诚信友善"

# Characters are ordered from darkest visual weight to lightest visual weight.
# All tiers use the same font size; tone comes from glyph shape and boldness.
BRIGHTNESS_TIERS = [
    {
        "chars": ["IIII"],
        "font_key": "latin",
        "bold": True,
    },
    {
        "chars": ["港"],
        "font_key": "simsun",
        "bold": True,
    },
    {
        "chars": ["香"],
        "font_key": "simsun",
        "bold": True,
    },
    {
        "chars": ["牛"],
        "font_key": "simhei",
        "bold": True,
    },
    {
        "chars": ["学"],
        "font_key": "simsun",
        "bold": False,
    },
    {
        "chars": ["中"],
        "font_key": "simsun",
        "bold": False,
    },
    {
        "chars": ["文"],
        "font_key": "simsun",
        "bold": False,
    },
    {
        "chars": ["大"],
        "font_key": "simsun",
        "bold": False,
    },
]

BLACK = "#000000"
WHITE = "#FFFFFF"


def find_existing_font(candidates: list[str]) -> str | None:
    """Return the first available font path from a list of common locations."""
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def load_font(candidates: list[str], size: int, label: str) -> ImageFont.ImageFont:
    """Load a TrueType font, falling back to Pillow's default font if needed."""
    font_path = find_existing_font(candidates)
    if font_path:
        return ImageFont.truetype(font_path, size=size)

    LOGGER.warning("%s font was not found. Falling back to Pillow default font.", label)
    return ImageFont.load_default()


def contains_rendered_ink(font: ImageFont.ImageFont, text: str) -> bool:
    """Check whether a font can render visible ink for the requested text."""
    test_image = Image.new("L", (64, 64), 255)
    test_draw = ImageDraw.Draw(test_image)
    test_draw.text((8, 8), text, font=font, fill=0)
    test_array = np.array(test_image)
    return bool(np.any(test_array < 250))


def load_verified_font(
    candidates: list[str],
    size: int,
    label: str,
    sample_text: str,
) -> ImageFont.ImageFont:
    """Load a font and warn if the selected font does not render Chinese text."""
    font = load_font(candidates, size, label)
    if not contains_rendered_ink(font, sample_text):
        LOGGER.warning(
            "%s font did not render '%s' visibly. Install a Chinese font such as "
            "SimHei, SimSun, Songti, or Noto CJK.",
            label,
            sample_text,
        )
    return font


def resolve_input_path() -> Path | None:
    """Return the first supported input image path that exists."""
    for input_path in INPUT_CANDIDATES:
        if input_path.exists():
            return input_path
    return None


def draw_bold_text(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: str,
) -> None:
    """Simulate bold text by drawing the same character with tiny offsets."""
    x, y = position
    for offset_x, offset_y in ((0, 0), (1, 0), (0, 1), (1, 1)):
        draw.text((x + offset_x, y + offset_y), text, font=font, fill=fill)


def measure_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
) -> tuple[int, int, int, int]:
    """Measure text and return its bounding box components."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = max(1, bbox[2] - bbox[0])
    text_height = max(1, bbox[3] - bbox[1])
    return bbox[0], bbox[1], text_width, text_height


def choose_character(average_value: float, thresholds: list[float]) -> tuple[str, str, bool]:
    """Choose a density tier for one grid cell based on its average brightness."""
    for tier, threshold in zip(BRIGHTNESS_TIERS, thresholds):
        if average_value <= threshold:
            return (
                random.choice(tier["chars"]),
                tier["font_key"],
                tier["bold"],
            )

    fallback_tier = BRIGHTNESS_TIERS[-1]
    return (
        random.choice(fallback_tier["chars"]),
        fallback_tier["font_key"],
        fallback_tier["bold"],
    )


def build_grid_brightness(
    value_array: np.ndarray,
    input_width: int,
    input_height: int,
    grid_columns: int,
    grid_rows: int,
) -> np.ndarray:
    """Calculate the average HSV value for every source grid cell."""
    grid_values = np.zeros((grid_rows, grid_columns), dtype=np.float32)

    for row_index, source_y in enumerate(range(0, input_height, GRID_SIZE)):
        source_bottom = min(source_y + GRID_SIZE, input_height)
        for column_index, source_x in enumerate(range(0, input_width, GRID_SIZE)):
            source_right = min(source_x + GRID_SIZE, input_width)
            grid = value_array[source_y:source_bottom, source_x:source_right]
            grid_values[row_index, column_index] = float(np.mean(grid))

    return grid_values


def calculate_adaptive_thresholds(grid_values: np.ndarray) -> list[float]:
    """Create image-specific brightness thresholds for clearer tonal separation."""
    if grid_values.shape[1] > 2:
        sampled_values = grid_values[:, 1:-1].reshape(-1)
    else:
        sampled_values = grid_values.reshape(-1)

    quantiles = [0.10, 0.22, 0.35, 0.50, 0.65, 0.78, 0.90]
    thresholds = [float(np.quantile(sampled_values, q)) for q in quantiles]
    thresholds.append(256.0)
    return thresholds


def draw_character_cell(
    draw: ImageDraw.ImageDraw,
    character: str,
    font: ImageFont.ImageFont,
    cell_left: int,
    cell_top: int,
    cell_size: int,
    bold: bool,
) -> None:
    """Draw one centered black character inside one white output cell."""
    bbox_left, bbox_top, text_width, text_height = measure_text(draw, character, font)
    x = cell_left + (cell_size - text_width) // 2 - bbox_left
    y = cell_top + (cell_size - text_height) // 2 - bbox_top

    if bold:
        draw_bold_text(draw, (x, y), character, font, BLACK)
    else:
        draw.text((x, y), character, font=font, fill=BLACK)


def generate_detail_image(input_image: Image.Image) -> Image.Image:
    """Generate the detailed character mosaic image from the source image."""
    rgb_image = input_image.convert("RGB")
    input_width, input_height = rgb_image.size
    rgb_array = np.array(rgb_image, dtype=np.uint8)

    # Use the HSV value channel instead of standard grayscale. This keeps bright
    # saturated colors such as red backgrounds from being misclassified as dark.
    value_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2HSV)[:, :, 2]

    grid_columns = (input_width + GRID_SIZE - 1) // GRID_SIZE
    grid_rows = (input_height + GRID_SIZE - 1) // GRID_SIZE
    grid_values = build_grid_brightness(
        value_array, input_width, input_height, grid_columns, grid_rows
    )
    thresholds = calculate_adaptive_thresholds(grid_values)
    LOGGER.info(
        "Adaptive brightness thresholds: %s",
        ", ".join(f"{threshold:.1f}" for threshold in thresholds[:-1]),
    )

    output_width = grid_columns * OUTPUT_SCALE
    output_height = grid_rows * OUTPUT_SCALE
    detail_image = Image.new("RGB", (output_width, output_height), WHITE)
    draw = ImageDraw.Draw(detail_image)

    simhei_candidates = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/Library/Fonts/SimHei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/truetype/arphic/SimHei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ]
    simsun_candidates = [
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/Library/Fonts/SimSun.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/simsun.ttf",
        "/usr/share/fonts/truetype/arphic/SimSun.ttf",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    ]

    fonts = {
        "latin": load_verified_font(
            simhei_candidates, CELL_FONT_SIZE, f"Latin {CELL_FONT_SIZE}", "I"
        ),
        "simhei": load_verified_font(
            simhei_candidates, CELL_FONT_SIZE, f"SimHei {CELL_FONT_SIZE}", "牛"
        ),
        "simsun": load_verified_font(
            simsun_candidates, CELL_FONT_SIZE, f"SimSun {CELL_FONT_SIZE}", "富"
        ),
    }

    for row_index, source_y in enumerate(range(0, input_height, GRID_SIZE), start=1):
        LOGGER.info("Processing row %s of %s...", row_index, grid_rows)

        for column_index, source_x in enumerate(range(0, input_width, GRID_SIZE)):
            cell_left = column_index * OUTPUT_SCALE
            cell_top = (row_index - 1) * OUTPUT_SCALE

            if column_index in (0, grid_columns - 1):
                character = SIDE_TEXT[(row_index - 1) % len(SIDE_TEXT)]
                font_key = "simsun"
                bold = True
            else:
                average_value = float(grid_values[row_index - 1, column_index])
                character, font_key, bold = choose_character(average_value, thresholds)

            font = fonts[font_key]
            draw_character_cell(
                draw, character, font, cell_left, cell_top, OUTPUT_SCALE, bold
            )

    return detail_image


def create_blur_image(detail_image: Image.Image) -> Image.Image:
    """Create a Gaussian-blurred preview that simulates viewing from far away."""
    blur_source = detail_image
    if detail_image.width * detail_image.height > MAX_FULL_BLUR_PIXELS:
        blur_source = detail_image.copy()
        blur_source.thumbnail(
            (MAX_PREVIEW_SIDE, MAX_PREVIEW_SIDE), Image.Resampling.LANCZOS
        )
        LOGGER.info(
            "Detail image is very large; generating a resized blur preview at "
            "%sx%s.",
            blur_source.width,
            blur_source.height,
        )

    detail_array = np.array(blur_source)
    blurred_array = cv2.GaussianBlur(detail_array, (21, 21), 0)
    return Image.fromarray(blurred_array)


def resize_to_panel(image: Image.Image, panel_size: tuple[int, int]) -> Image.Image:
    """Resize an image to fit one comparison panel on a white background."""
    panel_width, panel_height = panel_size
    resized = image.convert("RGB").copy()
    resized.thumbnail(panel_size, Image.Resampling.LANCZOS)

    panel = Image.new("RGB", panel_size, WHITE)
    x = (panel_width - resized.width) // 2
    y = (panel_height - resized.height) // 2
    panel.paste(resized, (x, y))
    return panel


def create_compare_image(
    original_image: Image.Image,
    detail_image: Image.Image,
    blur_image: Image.Image,
) -> Image.Image:
    """Create a side-by-side comparison image with original, detail, and blur panels."""
    scale = min(
        1.0,
        MAX_COMPARE_PANEL_SIDE / detail_image.width,
        MAX_COMPARE_PANEL_SIDE / detail_image.height,
    )
    panel_width = max(1, int(detail_image.width * scale))
    panel_height = max(1, int(detail_image.height * scale))
    panel_size = (panel_width, panel_height)

    original_panel = resize_to_panel(original_image, panel_size)
    detail_panel = resize_to_panel(detail_image, panel_size)
    blur_panel = resize_to_panel(blur_image, panel_size)

    compare_image = Image.new("RGB", (panel_width * 3, panel_height), WHITE)
    compare_image.paste(original_panel, (0, 0))
    compare_image.paste(detail_panel, (panel_width, 0))
    compare_image.paste(blur_panel, (panel_width * 2, 0))
    return compare_image


def main() -> None:
    """Run the full TextPictures generation workflow."""
    input_path = resolve_input_path()
    if input_path is None:
        LOGGER.error("input.jpg does not exist")
        return

    LOGGER.info("Loading input image: %s", input_path)
    input_image = Image.open(input_path).convert("RGB")
    output_width = ((input_image.width + GRID_SIZE - 1) // GRID_SIZE) * OUTPUT_SCALE
    output_height = ((input_image.height + GRID_SIZE - 1) // GRID_SIZE) * OUTPUT_SCALE
    LOGGER.info("Input size: %sx%s", input_image.width, input_image.height)
    LOGGER.info("Detail output size: %sx%s", output_width, output_height)

    LOGGER.info("Generating detailed character mosaic...")
    detail_image = generate_detail_image(input_image)
    detail_image.save(DETAIL_PATH)
    LOGGER.info("Saved detail image: %s", DETAIL_PATH)

    LOGGER.info("Generating blurred preview...")
    blur_image = create_blur_image(detail_image)
    blur_image.save(BLUR_PATH)
    LOGGER.info("Saved blurred preview: %s", BLUR_PATH)

    LOGGER.info("Generating comparison image...")
    compare_image = create_compare_image(input_image, detail_image, blur_image)
    compare_image.save(COMPARE_PATH)
    LOGGER.info("Saved comparison image: %s", COMPARE_PATH)

    LOGGER.info("Done.")


if __name__ == "__main__":
    main()
