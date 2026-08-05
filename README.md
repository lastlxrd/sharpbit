# SharpBit

SharpBit converts images, GIFs and short videos into monochrome 1-bit C assets.

## Install

Run:

```text
install.bat
```

## GUI

Run:

```text
launch-gui.bat
```

The GUI has two tabs:

- **Convert Assets** — image/GIF/video to separate `.c` and `.h` asset files
- **Frames → Video** — image frames back to MP4 or GIF

An asset name is required before conversion.

## Output

Each asset is stored separately:

```text
output/generated/<asset_name>/<asset_name>.c
output/generated/<asset_name>/<asset_name>.h
output/preview/<asset_name>...
```

Common types and the optional registry are stored in:

```text
output/generated/sharpbit_types.h
output/generated/sharpbit_assets.c
output/generated/sharpbit_assets.h
```

Rebuilt videos are stored in:

```text
output/rebuilt_videos/
```

## CLI example

```powershell
python tools\convert_assets.py image.png --name boot_logo --dither bayer4
```

Frames back to video:

```powershell
python tools\frames_to_video.py frames --name demo --fps 12 --format mp4
```

Default display size and conversion settings are in `config.json`.
