# SharpBit

SharpBit converts images, GIFs and short videos into monochrome 1-bit C assets.

You can:
- drag and drop files or folders onto `drop-assets-here.bat`
- use `input/` + `convert-assets.bat`
- launch a simple GUI with `launch-gui.bat`

## Install

On Windows, run:

```text
install.bat
```

Or install manually:

```bash
python -m pip install -r requirements.txt
```

## Quick use

### Drag and drop
Drop one or more files or folders onto:

```text
drop-assets-here.bat
```

### GUI
Run:

```powershell
.\launch-gui.bat
```

The launcher checks Python and installs missing packages automatically. If startup fails, the console stays open and shows the error.

### Classic folder mode
1. Put files into `input/`
2. Run:

```powershell
.\convert-assets.bat
```

## Output

Generated files:
- `output/generated/assets.c`
- `output/generated/assets.h`
- `output/generated/animations/...`
- `output/preview/...`

## Config

Edit `config.json` to change default dithering, threshold and target display size.
The GUI can also override these settings.
