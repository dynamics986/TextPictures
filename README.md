# TextPictures

TextPictures turns an input image into a high-resolution Chinese-character density mosaic.
Viewed up close, the output is made from many small repeated characters. Viewed from a distance, the original image shape appears through the character density.

## Requirements

This project uses `uv` for dependency management.

```bash
uv sync
```

## Usage

Place an image named `input.jpg` or `input.png` in this directory, then run:

```bash
uv run python textpictures.py
```

The script checks `input.jpg` first, then `input.png`. If neither file exists, it logs `input.jpg does not exist` and exits without generating output images.

## Outputs

Running the script generates:

- `output_detail.png`: the detailed high-resolution text mosaic.
- `output_blur.png`: a Gaussian-blurred preview that simulates viewing the mosaic from far away.
- `output_compare.png`: a side-by-side comparison with the original image on the left, the detailed mosaic in the middle, and the blurred preview on the right.

For very large input images, `output_detail.png` keeps the full high-resolution scale, while `output_blur.png` and `output_compare.png` are generated as resized preview images to avoid impractically large files.

## How It Works

This version treats the image as a grid of text cells rather than drawing normal pixels. The input image is divided into `15x15` pixel blocks. For each block, the program **calculates the average brightness from the HSV value channel instead of plain grayscale**. This is important because saturated colors such as red can look dark in grayscale even when they should behave like a bright background.

Each source block becomes one `30x30` output cell:

- The main image area uses eight brightness tiers: `IIII`, `港`, `香`, `牛`, `学`, `中`, `文`, and `大`, from darkest to brightest.
- The darkest tier uses bold repeated `I` letters so the cell has enough black ink to read as a true shadow. The remaining tiers are ordered by measured visual ink density, so dense bold characters represent darker tones and simpler regular characters represent lighter tones.
- The exact brightness thresholds are calculated from the current input image using adaptive quantiles. This makes the available character tiers spread across the actual photo instead of relying on fixed values that may be too dark or too bright for a particular image.
- The leftmost and rightmost output columns do not sample the image. Instead, they write `富强民主文明和谐自由平等公正法治爱国敬业诚信友善` from top to bottom, repeating when the image is taller than the phrase.

All cells use the same `27px` font size. This size was chosen to fill most of each `30x30` cell while still leaving enough margin to prevent neighboring characters from touching or overlapping. The tonal tiering is therefore based on glyph shape, boldness, and adaptive thresholding rather than font-size changes. Because every output cell is a real character on a white background, the result is readable up close as a text grid. From farther away, the gradual shift across the eight tiers gives the silhouette more tonal detail and a livelier contour. The script also creates a Gaussian-blurred preview with OpenCV to simulate this far-view effect, then combines the original image, the detailed text mosaic, and the blurred preview into one comparison image.
