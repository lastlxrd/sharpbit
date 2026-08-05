# Sharp Asset Converter (standalone)

Standalone image-to-C converter for monochrome displays such as Sharp Memory LCD.

This project is fully separate from PogopoOS.

## Usage

1. Put images into `input/`
2. Install requirements:
   `python -m pip install -r requirements.txt`
3. Run:
   `./convert-assets.bat`

Generated files:
- `output/generated/assets.c`
- `output/generated/assets.h`
- `output/preview/...`

The generated previews are built back from the exact packed bytes.
