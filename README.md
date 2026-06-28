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

- Very dark cells use the main silhouette character `牛` in bold SimHei-style 18px text.
- Dark cells use visually dense characters such as `富`, `强`, `谐`, `敬`, `善`, `港`, and `等` in larger 16px text.
- Middle-tone cells use medium-density characters such as `明`, `和`, `法`, `治`, `爱`, `国`, `诚`, `信`, `香`, and `学` in 14px text.
- Light cells use simpler characters such as `民`, `主`, `文`, `明`, `自`, `由`, `平`, `公`, `正`, `业`, and `友` in 12px text.
- Very bright cells use the simplest characters such as `主`, `文`, `由`, `中`, `大`, `公`, `正`, and `友` in 10px text.

The tiering is based on rough visual stroke density: characters with more strokes and heavier shapes create darker visual weight, while simpler characters leave more white space. Because every output cell is a real Chinese character on a white background, the result is readable up close as a text grid. From farther away, the gradual shift from large dense characters to small simple characters gives the silhouette more tonal detail and a livelier contour. The script also creates a Gaussian-blurred preview with OpenCV to simulate this far-view effect, then combines the original image, the detailed text mosaic, and the blurred preview into one comparison image.
