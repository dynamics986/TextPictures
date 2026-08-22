# TextPictures

> Demo: https://dynamics986.github.io/TextPictures/ 

TextPictures turns an image into a Chinese-character density mosaic. Viewed up close, the output is made from many small repeated characters. Viewed from a distance, the original image shape appears through the character density. 

## Example

| Input image | TextPictures output |
| --- | --- |
| <img src="input.jpg" alt="Input image" width="420"> | <img src="output.jpg" alt="TextPictures output image" width="420"> |


## Local Website Usage

The website is `index.html`. It runs completely in the browser. Users upload one JPG, PNG, BMP, or WEBP image, preview the generated result, and download PNG outputs.

To test the website locally with a simple static server:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://127.0.0.1:8000
```

The website provides download buttons for:

- `textpicture_detail.png`: the detailed Chinese-character mosaic.
- `textpicture_blur.png`: a blurred far-view preview.
- `textpicture_compare.png`: a side-by-side comparison with the original image, detailed mosaic, and blurred preview.

## CLI Usage

The command-line Python version uses `uv` for dependency management.

```bash
uv sync
```

Place an image named `input.jpg` or `input.png` in this directory, then run:

```bash
uv run python textpictures.py
```

The script checks `input.jpg` first, then `input.png`. If neither file exists, it logs `input.jpg does not exist` and exits without generating output images.

After running the script, it generates:

- `output_detail.png`: the detailed high-resolution text mosaic.
- `output_blur.png`: a Gaussian-blurred preview that simulates viewing the mosaic from far away.
- `output_compare.png`: a side-by-side comparison with the original image on the left, the detailed mosaic in the middle, and the blurred preview on the right.

For very large input images, `output_detail.png` keeps the full high-resolution scale, while `output_blur.png` and `output_compare.png` are generated as resized preview images to avoid impractically large files.

## Principles

Both the static website and the Python script treat the image as a grid of text cells rather than drawing normal pixels. The website uses JavaScript Canvas so it can run on GitHub Pages without a backend. The Python script reads `input.jpg` or `input.png` and uses the Pillow/OpenCV pipeline in `textpictures.py`.

In the Python version, the input image is divided into `15x15` pixel blocks. For each block, the program **calculates the average brightness from the HSV value channel instead of plain grayscale**. This is important because saturated colors such as red can look dark in grayscale even when they should behave like a bright background. The browser version follows the same visual idea with Canvas image data and uses the maximum RGB channel as a static-site-friendly brightness approximation.

Each source block becomes one `30x30` output cell:

- The main image area uses eight brightness tiers: `I`, `港`, `香`, `牛`, `学`, `中`, `文`, and `大`, from darkest to brightest.
- The darkest tier uses bold repeated `I` letters so the cell has enough black ink to read as a true shadow. The remaining tiers are ordered by measured visual ink density, so dense bold characters represent darker tones and simpler regular characters represent lighter tones.
- The exact brightness thresholds are calculated from the current input image using adaptive quantiles. This makes the available character tiers spread across the actual photo instead of relying on fixed values that may be too dark or too bright for a particular image.

All cells use the same `27px` font size. This size was chosen to fill most of each `30x30` cell while still leaving enough margin to prevent neighboring characters from touching or overlapping. The tonal tiering is therefore based on glyph shape, boldness, and adaptive thresholding rather than font-size changes. 


## References

Related tools that explore image-to-character rendering and browser-based ASCII art:

- [Asciify](https://asciify.org/) — browser-based image and video ASCII art engine.
- [Glyphtrix](https://glyphtrix.art/) — local browser tool for image, video, and webcam character art.
- [Cinerune](https://cinerune.com/) — browser-based ASCII video editor with timelines, effects, and Unicode glyphs.
- [ASCII Motion](https://ascii-motion.com/) — browser-based animated ASCII art tool.