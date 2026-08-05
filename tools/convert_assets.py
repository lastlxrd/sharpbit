#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:
    print(
        "ERROR: Pillow is missing.\n"
        "Install it with:\n"
        "  python -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
GENERATED_DIR = OUTPUT_DIR / "generated"
PREVIEW_DIR = OUTPUT_DIR / "preview"
CONFIG_PATH = ROOT / "config.json"
OUT_H = GENERATED_DIR / "assets.h"
OUT_C = GENERATED_DIR / "assets.c"

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

DEFAULTS: dict[str, Any] = {
    "dither": "bayer4",
    "threshold": 128,
    "invert_image": False,
    "background": 255,
    "max_width": 400,
    "max_height": 240,
    "bit_order": "msb",
    "black_bit": 1,
}

BAYER_2 = (
    (0, 2),
    (3, 1),
)

BAYER_4 = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)

def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"defaults": {}, "overrides": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("Config root must be an object.")
    defaults = data.get("defaults", {})
    overrides = data.get("overrides", {})
    if not isinstance(defaults, dict) or not isinstance(overrides, dict):
        raise RuntimeError("Both 'defaults' and 'overrides' must be objects.")
    return {"defaults": defaults, "overrides": overrides}

def settings_for(relative_path: str, config: dict[str, Any]) -> dict[str, Any]:
    result = dict(DEFAULTS)
    result.update(config.get("defaults", {}))
    override = config.get("overrides", {}).get(relative_path)
    if override is None:
        override = config.get("overrides", {}).get(Path(relative_path).name)
    if override is not None:
        if not isinstance(override, dict):
            raise RuntimeError(f"Override for {relative_path!r} must be an object.")
        result.update(override)
    return result

def discover_images(directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    return sorted(
        path for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )

def sanitize_symbol(logical_name: str) -> str:
    symbol = re.sub(r"[^A-Za-z0-9_]", "_", logical_name)
    symbol = re.sub(r"_+", "_", symbol).strip("_").lower()
    if not symbol:
        symbol = "asset"
    if symbol[0].isdigit():
        symbol = f"asset_{symbol}"
    return symbol

def flatten_on_background(path: Path, background: int) -> Image.Image:
    with Image.open(path) as source:
        source.load()
        rgba = source.convert("RGBA")
    bg = max(0, min(255, int(background)))
    canvas = Image.new("RGBA", rgba.size, (bg, bg, bg, 255))
    canvas.alpha_composite(rgba)
    return canvas.convert("L")

def resize_image(image: Image.Image, settings: dict[str, Any]) -> Image.Image:
    width = settings.get("width")
    height = settings.get("height")
    fit = str(settings.get("fit", "contain")).lower()

    if (width is None) != (height is None):
        raise RuntimeError("'width' and 'height' must be specified together.")

    if width is not None and height is not None:
        width = int(width)
        height = int(height)
        if width <= 0 or height <= 0:
            raise RuntimeError("Width and height must be positive.")

        if fit == "stretch":
            return image.resize((width, height), Image.Resampling.LANCZOS)

        src_ratio = image.width / image.height
        dst_ratio = width / height

        if fit == "cover":
            if src_ratio > dst_ratio:
                resized_height = height
                resized_width = round(height * src_ratio)
            else:
                resized_width = width
                resized_height = round(width / src_ratio)

            resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
            left = (resized_width - width) // 2
            top = (resized_height - height) // 2
            return resized.crop((left, top, left + width, top + height))

        if fit != "contain":
            raise RuntimeError(f"Unknown fit mode: {fit}")

        copy = image.copy()
        copy.thumbnail((width, height), Image.Resampling.LANCZOS)
        background = max(0, min(255, int(settings.get("background", 255))))
        canvas = Image.new("L", (width, height), background)
        canvas.paste(copy, ((width - copy.width) // 2, (height - copy.height) // 2))
        return canvas

    max_width = int(settings.get("max_width", 400))
    max_height = int(settings.get("max_height", 240))
    if image.width <= max_width and image.height <= max_height:
        return image

    copy = image.copy()
    copy.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return copy

def ordered_dither(image: Image.Image, matrix: tuple[tuple[int, ...], ...]) -> Image.Image:
    width, height = image.size
    output = Image.new("1", (width, height))
    src = image.load()
    dst = output.load()
    size = len(matrix)
    denom = size * size

    for y in range(height):
        row = matrix[y % size]
        for x in range(width):
            threshold = ((row[x % size] + 0.5) * 255.0) / denom
            dst[x, y] = 255 if src[x, y] >= threshold else 0
    return output

def to_monochrome(image: Image.Image, settings: dict[str, Any]) -> Image.Image:
    dither = str(settings.get("dither", "bayer4")).lower()
    if dither == "threshold":
        threshold = max(0, min(255, int(settings.get("threshold", 128))))
        mono = image.point(lambda pixel: 255 if pixel >= threshold else 0, mode="1")
    elif dither == "bayer2":
        mono = ordered_dither(image, BAYER_2)
    elif dither == "bayer4":
        mono = ordered_dither(image, BAYER_4)
    elif dither == "floyd":
        mono = image.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    else:
        raise RuntimeError(f"Unknown dither mode: {dither}")

    if bool(settings.get("invert_image", False)):
        mono = mono.point(lambda pixel: 0 if pixel else 255, mode="1")

    return mono

def validate_packing(settings: dict[str, Any]) -> tuple[str, int]:
    bit_order = str(settings.get("bit_order", "msb")).lower()
    black_bit = int(settings.get("black_bit", 1))
    if bit_order not in {"msb", "lsb"}:
        raise RuntimeError("'bit_order' must be 'msb' or 'lsb'.")
    if black_bit not in {0, 1}:
        raise RuntimeError("'black_bit' must be 0 or 1.")
    return bit_order, black_bit

def pack_image(image: Image.Image, bit_order: str, black_bit: int) -> tuple[bytes, int]:
    width, height = image.size
    stride = (width + 7) // 8
    default_byte = 0x00 if black_bit == 1 else 0xFF
    data = bytearray([default_byte] * (stride * height))
    pixels = image.load()

    for y in range(height):
        for x in range(width):
            is_black = pixels[x, y] == 0
            bit_value = black_bit if is_black else 1 - black_bit
            shift = 7 - (x % 8) if bit_order == "msb" else (x % 8)
            index = y * stride + x // 8
            if bit_value:
                data[index] |= 1 << shift
            else:
                data[index] &= ~(1 << shift)

    return bytes(data), stride

def unpack_image(data: bytes, width: int, height: int, stride: int, bit_order: str, black_bit: int) -> Image.Image:
    image = Image.new("1", (width, height), 255)
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            shift = 7 - (x % 8) if bit_order == "msb" else (x % 8)
            value = (data[y * stride + x // 8] >> shift) & 1
            pixels[x, y] = 0 if value == black_bit else 255
    return image

def format_bytes(data: bytes) -> str:
    lines = []
    for offset in range(0, len(data), 12):
        chunk = data[offset:offset + 12]
        lines.append("    " + ", ".join(f"0x{b:02X}" for b in chunk) + ",")
    return "\n".join(lines)

def write_header(path: Path, assets: list[dict[str, Any]]) -> None:
    externs = "\n".join(
        f"extern const mono_asset_t mono_asset_{asset['symbol']};"
        for asset in assets
    )
    path.write_text(f"""#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {{
#endif

typedef struct {{
    const char *name;
    uint16_t width;
    uint16_t height;
    uint16_t stride;
    const uint8_t *data;
    size_t data_size;
}} mono_asset_t;

{externs}

extern const mono_asset_t *const mono_assets[];
extern const size_t mono_assets_count;

const mono_asset_t *mono_asset_find(const char *name);

#ifdef __cplusplus
}}
#endif
""", encoding="utf-8")

def write_source(path: Path, header_name: str, assets: list[dict[str, Any]]) -> None:
    lines = [f'#include "{header_name}"', "", "#include <string.h>", ""]
    for asset in assets:
        symbol = asset["symbol"]
        lines.extend([
            f"static const uint8_t mono_asset_{symbol}_data[] __attribute__((aligned(4))) = {{",
            format_bytes(asset["data"]),
            "};",
            "",
            f"const mono_asset_t mono_asset_{symbol} = {{",
            f'    .name = "{asset["name"]}",',
            f"    .width = {asset['width']},",
            f"    .height = {asset['height']},",
            f"    .stride = {asset['stride']},",
            f"    .data = mono_asset_{symbol}_data,",
            f"    .data_size = sizeof(mono_asset_{symbol}_data),",
            "};",
            "",
        ])
    lines.append("const mono_asset_t *const mono_assets[] = {")
    for asset in assets:
        lines.append(f"    &mono_asset_{asset['symbol']},")
    lines.extend([
        "};",
        "",
        "const size_t mono_assets_count =",
        "    sizeof(mono_assets) / sizeof(mono_assets[0]);",
        "",
        "const mono_asset_t *mono_asset_find(const char *name)",
        "{",
        "    if (name == NULL) {",
        "        return NULL;",
        "    }",
        "",
        "    for (size_t i = 0; i < mono_assets_count; ++i) {",
        "        if (strcmp(mono_assets[i]->name, name) == 0) {",
        "            return mono_assets[i];",
        "        }",
        "    }",
        "",
        "    return NULL;",
        "}",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")

def clean_preview_dir(preview_dir: Path) -> None:
    if preview_dir.exists():
        for path in sorted(preview_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
    preview_dir.mkdir(parents=True, exist_ok=True)

def main() -> int:
    config = load_config(CONFIG_PATH)
    images = discover_images(INPUT_DIR)

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    clean_preview_dir(PREVIEW_DIR)

    assets: list[dict[str, Any]] = []
    used_symbols: set[str] = set()

    for image_path in images:
        relative_path = image_path.relative_to(INPUT_DIR).as_posix()
        logical_name = Path(relative_path).with_suffix("").as_posix()
        symbol = sanitize_symbol(logical_name)

        if symbol in used_symbols:
            raise RuntimeError(f"Symbol collision for {relative_path!r}: {symbol!r}")
        used_symbols.add(symbol)

        settings = settings_for(relative_path, config)
        bit_order, black_bit = validate_packing(settings)

        grayscale = flatten_on_background(image_path, int(settings.get("background", 255)))
        resized = resize_image(grayscale, settings)
        mono = to_monochrome(resized, settings)
        data, stride = pack_image(mono, bit_order, black_bit)

        round_trip = unpack_image(data, mono.width, mono.height, stride, bit_order, black_bit)
        preview_path = PREVIEW_DIR / Path(relative_path).with_suffix(".png")
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        round_trip.save(preview_path)

        assets.append({
            "name": logical_name,
            "symbol": symbol,
            "width": mono.width,
            "height": mono.height,
            "stride": stride,
            "data": data,
        })

        print(f"[OK] {relative_path} -> {logical_name} ({mono.width}x{mono.height}, {len(data)} bytes, {bit_order}, black={black_bit})")

    write_header(OUT_H, assets)
    write_source(OUT_C, OUT_H.name, assets)

    print()
    print(f"Assets converted: {len(assets)}")
    print(f"Generated code:   {OUT_C}")
    print(f"Generated header: {OUT_H}")
    print(f"Preview folder:   {PREVIEW_DIR}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
