# SharpBit

SharpBit converts PNG, JPG, BMP and WebP images into monochrome 1-bit C assets.

It can work in two simple ways:

1. put images into `input/` and run `convert-assets.bat`
2. drag and drop image files or folders onto `drop-assets-here.bat`

SharpBit also generates preview PNG files decoded from the exact output bytes.

## Setup

```bash
python -m pip install -r requirements.txt
```

## Use

### Option 1: input folder

1. Put images into `input/`
2. Run:

```powershell
.\convert-assets.bat
```

### Option 2: drag and drop

Drag one or more image files or folders onto:

```text
drop-assets-here.bat
```

## Output

Generated files:

```text
output/generated/assets.c
output/generated/assets.h
output/preview/
```

## Config

Conversion settings are stored in `config.json`.

Default output:
- MSB first
- black pixel = `1`
- white pixel = `0`
