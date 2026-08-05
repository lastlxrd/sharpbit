from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageSequence, UnidentifiedImageError

try:
    import imageio.v2 as imageio
except Exception:
    imageio = None


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
SUPPORTED_ANIMATION_EXTENSIONS = {".gif", ".mp4", ".mov", ".avi", ".mkv", ".webm"}
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_ANIMATION_EXTENSIONS

DEFAULTS: dict[str, Any] = {
    "dither": "bayer4",
    "threshold": 128,
    "invert_image": False,
    "background": 255,
    "max_width": 400,
    "max_height": 240,
    "fit": "contain",
    "bit_order": "msb",
    "black_bit": 1,
}

ANIMATION_DEFAULTS: dict[str, Any] = {
    "video_fps": 10,
    "max_frames": 120,
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


@dataclass
class MonoAsset:
    name: str
    symbol: str
    width: int
    height: int
    stride: int
    data: bytes


@dataclass
class MonoAnimationFrame:
    width: int
    height: int
    stride: int
    data: bytes
    duration_ms: int


@dataclass
class MonoAnimation:
    name: str
    symbol: str
    width: int
    height: int
    stride: int
    frames: list[MonoAnimationFrame]


def natural_sort_key(value: str | Path) -> list[Any]:
    text = str(value)
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", text)
    ]


def sanitize_symbol(value: str) -> str:
    symbol = re.sub(r"[^A-Za-z0-9_]", "_", value.strip())
    symbol = re.sub(r"_+", "_", symbol).strip("_").lower()
    if not symbol:
        raise RuntimeError("Asset name cannot be empty.")
    if symbol[0].isdigit():
        symbol = f"asset_{symbol}"
    return symbol


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"defaults": {}, "animation_defaults": {}, "overrides": {}}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read config '{path}': {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Config root must be an object.")

    defaults = data.get("defaults", {})
    animation_defaults = data.get("animation_defaults", {})
    overrides = data.get("overrides", {})

    if not isinstance(defaults, dict):
        raise RuntimeError("'defaults' must be an object.")
    if not isinstance(animation_defaults, dict):
        raise RuntimeError("'animation_defaults' must be an object.")
    if not isinstance(overrides, dict):
        raise RuntimeError("'overrides' must be an object.")

    return {
        "defaults": defaults,
        "animation_defaults": animation_defaults,
        "overrides": overrides,
    }


def merge_settings(
    relative_path: str,
    config: dict[str, Any],
    cli_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = dict(DEFAULTS)
    result.update(config.get("defaults", {}))

    override = config.get("overrides", {}).get(relative_path)
    if override is None:
        override = config.get("overrides", {}).get(Path(relative_path).name)

    if override is not None:
        if not isinstance(override, dict):
            raise RuntimeError(f"Override for '{relative_path}' must be an object.")
        result.update(override)

    if cli_overrides:
        for key, value in cli_overrides.items():
            if value is not None:
                result[key] = value

    return result


def merge_animation_settings(
    config: dict[str, Any],
    cli_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = dict(ANIMATION_DEFAULTS)
    result.update(config.get("animation_defaults", {}))
    if cli_overrides:
        for key, value in cli_overrides.items():
            if value is not None:
                result[key] = value
    return result


def is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def is_supported_animation(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_ANIMATION_EXTENSIONS


def discover_sources(
    source_items: list[Path],
    fallback_input_dir: Path,
) -> list[tuple[Path, str, str, str]]:
    items = (
        [item.resolve() for item in source_items]
        if source_items
        else [fallback_input_dir.resolve()]
    )
    discovered: list[tuple[Path, str, str, str]] = []

    for item in items:
        if not item.exists():
            raise RuntimeError(f"Source path does not exist: '{item}'")

        if item.is_dir():
            for path in sorted(item.rglob("*"), key=natural_sort_key):
                if is_supported_image(path):
                    relative = path.relative_to(item).as_posix()
                    logical = Path(relative).with_suffix("").as_posix()
                    discovered.append((path, relative, logical, "image"))
                elif is_supported_animation(path):
                    relative = path.relative_to(item).as_posix()
                    logical = Path(relative).with_suffix("").as_posix()
                    discovered.append((path, relative, logical, "animation"))
        elif is_supported_image(item):
            discovered.append((item, item.name, item.stem, "image"))
        elif is_supported_animation(item):
            discovered.append((item, item.name, item.stem, "animation"))
        else:
            raise RuntimeError(
                f"Unsupported source '{item}'. Use PNG, JPG, JPEG, BMP, WebP, "
                "GIF, MP4, MOV, AVI, MKV or WEBM."
            )

    return discovered


def assign_output_names(
    discovered: list[tuple[Path, str, str, str]],
    requested_name: str,
) -> list[tuple[Path, str, str, str]]:
    base = sanitize_symbol(requested_name)
    if not discovered:
        return []

    result: list[tuple[Path, str, str, str]] = []
    used: set[str] = set()

    for path, relative, original_logical, kind in discovered:
        if len(discovered) == 1:
            logical_name = base
        else:
            suffix = sanitize_symbol(original_logical.replace("/", "_"))
            logical_name = f"{base}_{suffix}"

        if logical_name in used:
            raise RuntimeError(
                f"Generated asset name collision: '{logical_name}'. "
                "Rename the input files or choose another base name."
            )
        used.add(logical_name)
        result.append((path, relative, logical_name, kind))

    return result


def flatten_rgba_image(image: Image.Image, background: int) -> Image.Image:
    rgba = image.convert("RGBA")
    bg = max(0, min(255, int(background)))
    canvas = Image.new("RGBA", rgba.size, (bg, bg, bg, 255))
    canvas.alpha_composite(rgba)
    return canvas.convert("L")


def flatten_on_background(path: Path, background: int) -> Image.Image:
    try:
        with Image.open(path) as source:
            source.load()
            return flatten_rgba_image(source, background)
    except (OSError, UnidentifiedImageError) as exc:
        raise RuntimeError(f"Cannot open image '{path}': {exc}") from exc


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

        source_ratio = image.width / image.height
        target_ratio = width / height

        if fit == "cover":
            if source_ratio > target_ratio:
                resized_height = height
                resized_width = round(height * source_ratio)
            else:
                resized_width = width
                resized_height = round(width / source_ratio)
            resized = image.resize(
                (resized_width, resized_height),
                Image.Resampling.LANCZOS,
            )
            left = (resized_width - width) // 2
            top = (resized_height - height) // 2
            return resized.crop((left, top, left + width, top + height))

        if fit != "contain":
            raise RuntimeError(
                f"Unknown fit mode '{fit}'. Use contain, cover or stretch."
            )

        copy = image.copy()
        copy.thumbnail((width, height), Image.Resampling.LANCZOS)
        background = max(0, min(255, int(settings.get("background", 255))))
        canvas = Image.new("L", (width, height), background)
        canvas.paste(
            copy,
            ((width - copy.width) // 2, (height - copy.height) // 2),
        )
        return canvas

    max_width = int(settings.get("max_width", 400))
    max_height = int(settings.get("max_height", 240))
    if max_width <= 0 or max_height <= 0:
        raise RuntimeError("Maximum dimensions must be positive.")

    if image.width <= max_width and image.height <= max_height:
        return image

    copy = image.copy()
    copy.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return copy


def ordered_dither(
    image: Image.Image,
    matrix: tuple[tuple[int, ...], ...],
) -> Image.Image:
    width, height = image.size
    output = Image.new("1", (width, height))
    source = image.load()
    destination = output.load()
    size = len(matrix)
    denominator = size * size

    for y in range(height):
        row = matrix[y % size]
        for x in range(width):
            threshold = ((row[x % size] + 0.5) * 255.0) / denominator
            destination[x, y] = 255 if source[x, y] >= threshold else 0

    return output


def to_monochrome(image: Image.Image, settings: dict[str, Any]) -> Image.Image:
    dither = str(settings.get("dither", "bayer4")).lower()

    if dither == "threshold":
        threshold = max(0, min(255, int(settings.get("threshold", 128))))
        mono = image.point(
            lambda pixel: 255 if pixel >= threshold else 0,
            mode="1",
        )
    elif dither == "bayer2":
        mono = ordered_dither(image, BAYER_2)
    elif dither == "bayer4":
        mono = ordered_dither(image, BAYER_4)
    elif dither == "floyd":
        mono = image.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    else:
        raise RuntimeError(
            f"Unknown dither mode '{dither}'. "
            "Use threshold, bayer2, bayer4 or floyd."
        )

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


def pack_image(
    image: Image.Image,
    bit_order: str,
    black_bit: int,
) -> tuple[bytes, int]:
    width, height = image.size
    stride = (width + 7) // 8
    default_byte = 0x00 if black_bit == 1 else 0xFF
    data = bytearray([default_byte] * (stride * height))
    pixels = image.load()

    for y in range(height):
        for x in range(width):
            is_black = pixels[x, y] == 0
            bit_value = black_bit if is_black else 1 - black_bit
            shift = 7 - (x % 8) if bit_order == "msb" else x % 8
            index = y * stride + x // 8
            if bit_value:
                data[index] |= 1 << shift
            else:
                data[index] &= ~(1 << shift)

    return bytes(data), stride


def unpack_image(
    data: bytes,
    width: int,
    height: int,
    stride: int,
    bit_order: str,
    black_bit: int,
) -> Image.Image:
    image = Image.new("1", (width, height), 255)
    pixels = image.load()

    for y in range(height):
        for x in range(width):
            shift = 7 - (x % 8) if bit_order == "msb" else x % 8
            value = (data[y * stride + x // 8] >> shift) & 1
            pixels[x, y] = 0 if value == black_bit else 255

    return image


def load_gif_frames(path: Path) -> list[tuple[Image.Image, int]]:
    frames: list[tuple[Image.Image, int]] = []
    try:
        with Image.open(path) as image:
            for frame in ImageSequence.Iterator(image):
                duration = int(frame.info.get("duration", 100))
                frames.append((frame.convert("RGBA"), max(1, duration)))
    except (OSError, UnidentifiedImageError) as exc:
        raise RuntimeError(f"Cannot open GIF '{path}': {exc}") from exc
    return frames


def load_video_frames(
    path: Path,
    video_fps: int,
    max_frames: int,
) -> list[tuple[Image.Image, int]]:
    if imageio is None:
        raise RuntimeError(
            "Video support requires imageio and imageio-ffmpeg. "
            "Run install.bat first."
        )

    try:
        reader = imageio.get_reader(str(path))
    except Exception as exc:
        raise RuntimeError(f"Cannot open video '{path}': {exc}") from exc

    target_fps = max(1, int(video_fps))
    duration = max(1, round(1000 / target_fps))
    frames: list[tuple[Image.Image, int]] = []

    try:
        metadata = reader.get_meta_data()
        source_fps = float(metadata.get("fps", target_fps) or target_fps)
        step = max(1, round(source_fps / target_fps))
    except Exception:
        step = 1

    try:
        for index, frame_array in enumerate(reader):
            if index % step:
                continue
            frames.append(
                (Image.fromarray(frame_array).convert("RGBA"), duration)
            )
            if len(frames) >= max(1, int(max_frames)):
                break
    except Exception as exc:
        raise RuntimeError(f"Cannot decode video '{path}': {exc}") from exc
    finally:
        try:
            reader.close()
        except Exception:
            pass

    return frames


def convert_static_image(
    path: Path,
    logical_name: str,
    settings: dict[str, Any],
) -> MonoAsset:
    bit_order, black_bit = validate_packing(settings)
    grayscale = flatten_on_background(
        path,
        int(settings.get("background", 255)),
    )
    resized = resize_image(grayscale, settings)
    mono = to_monochrome(resized, settings)
    data, stride = pack_image(mono, bit_order, black_bit)

    return MonoAsset(
        name=logical_name,
        symbol=sanitize_symbol(logical_name),
        width=mono.width,
        height=mono.height,
        stride=stride,
        data=data,
    )


def convert_animation(
    path: Path,
    logical_name: str,
    settings: dict[str, Any],
    animation_settings: dict[str, Any],
) -> MonoAnimation:
    if path.suffix.lower() == ".gif":
        raw_frames = load_gif_frames(path)
    else:
        raw_frames = load_video_frames(
            path,
            video_fps=int(animation_settings.get("video_fps", 10)),
            max_frames=int(animation_settings.get("max_frames", 120)),
        )

    max_frames = max(1, int(animation_settings.get("max_frames", 120)))
    raw_frames = raw_frames[:max_frames]

    if not raw_frames:
        raise RuntimeError(f"No frames decoded from '{path}'.")

    bit_order, black_bit = validate_packing(settings)
    frames: list[MonoAnimationFrame] = []
    base_width: int | None = None
    base_height: int | None = None
    base_stride: int | None = None

    for rgba_frame, duration_ms in raw_frames:
        grayscale = flatten_rgba_image(
            rgba_frame,
            int(settings.get("background", 255)),
        )
        resized = resize_image(grayscale, settings)
        mono = to_monochrome(resized, settings)
        data, stride = pack_image(mono, bit_order, black_bit)

        if base_width is None:
            base_width = mono.width
            base_height = mono.height
            base_stride = stride
        elif (
            mono.width != base_width
            or mono.height != base_height
            or stride != base_stride
        ):
            raise RuntimeError(
                f"Frame size mismatch while processing '{path}'."
            )

        frames.append(
            MonoAnimationFrame(
                width=mono.width,
                height=mono.height,
                stride=stride,
                data=data,
                duration_ms=max(1, int(duration_ms)),
            )
        )

    return MonoAnimation(
        name=logical_name,
        symbol=sanitize_symbol(logical_name),
        width=base_width or 0,
        height=base_height or 0,
        stride=base_stride or 0,
        frames=frames,
    )


def format_bytes(data: bytes) -> str:
    lines: list[str] = []
    for offset in range(0, len(data), 12):
        chunk = data[offset : offset + 12]
        lines.append(
            "    " + ", ".join(f"0x{byte:02X}" for byte in chunk) + ","
        )
    return "\n".join(lines)


def write_types_header(generated_dir: Path) -> None:
    generated_dir.mkdir(parents=True, exist_ok=True)
    (generated_dir / "sharpbit_types.h").write_text(
        """#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    const char *name;
    uint16_t width;
    uint16_t height;
    uint16_t stride;
    const uint8_t *data;
    size_t data_size;
} mono_asset_t;

typedef struct {
    const uint8_t *data;
    size_t data_size;
    uint16_t duration_ms;
} mono_animation_frame_t;

typedef struct {
    const char *name;
    uint16_t width;
    uint16_t height;
    uint16_t stride;
    uint16_t frame_count;
    const mono_animation_frame_t *frames;
} mono_animation_t;

#ifdef __cplusplus
}
#endif
""",
        encoding="utf-8",
    )


def write_static_asset(generated_dir: Path, asset: MonoAsset) -> None:
    asset_dir = generated_dir / asset.symbol
    if asset_dir.exists():
        shutil.rmtree(asset_dir)
    asset_dir.mkdir(parents=True)

    header_name = f"{asset.symbol}.h"
    source_name = f"{asset.symbol}.c"
    variable = f"sharpbit_asset_{asset.symbol}"

    (asset_dir / header_name).write_text(
        f"""#pragma once

#include "../sharpbit_types.h"

#ifdef __cplusplus
extern "C" {{
#endif

extern const mono_asset_t {variable};

#ifdef __cplusplus
}}
#endif
""",
        encoding="utf-8",
    )

    (asset_dir / source_name).write_text(
        f"""#include "{header_name}"

static const uint8_t {variable}_data[] __attribute__((aligned(4))) = {{
{format_bytes(asset.data)}
}};

const mono_asset_t {variable} = {{
    .name = "{asset.name}",
    .width = {asset.width},
    .height = {asset.height},
    .stride = {asset.stride},
    .data = {variable}_data,
    .data_size = sizeof({variable}_data),
}};
""",
        encoding="utf-8",
    )


def write_animation_asset(
    generated_dir: Path,
    animation: MonoAnimation,
) -> None:
    asset_dir = generated_dir / animation.symbol
    if asset_dir.exists():
        shutil.rmtree(asset_dir)
    asset_dir.mkdir(parents=True)

    header_name = f"{animation.symbol}.h"
    source_name = f"{animation.symbol}.c"
    variable = f"sharpbit_animation_{animation.symbol}"

    (asset_dir / header_name).write_text(
        f"""#pragma once

#include "../sharpbit_types.h"

#ifdef __cplusplus
extern "C" {{
#endif

extern const mono_animation_t {variable};

#ifdef __cplusplus
}}
#endif
""",
        encoding="utf-8",
    )

    lines = [f'#include "{header_name}"', ""]
    for index, frame in enumerate(animation.frames):
        frame_var = f"{variable}_frame_{index:04d}"
        lines.extend(
            [
                f"static const uint8_t {frame_var}[] __attribute__((aligned(4))) = {{",
                format_bytes(frame.data),
                "};",
                "",
            ]
        )

    lines.append(
        f"static const mono_animation_frame_t {variable}_frames[] = {{"
    )
    for index, frame in enumerate(animation.frames):
        frame_var = f"{variable}_frame_{index:04d}"
        lines.extend(
            [
                "    {",
                f"        .data = {frame_var},",
                f"        .data_size = sizeof({frame_var}),",
                f"        .duration_ms = {frame.duration_ms},",
                "    },",
            ]
        )
    lines.extend(
        [
            "};",
            "",
            f"const mono_animation_t {variable} = {{",
            f'    .name = "{animation.name}",',
            f"    .width = {animation.width},",
            f"    .height = {animation.height},",
            f"    .stride = {animation.stride},",
            f"    .frame_count = {len(animation.frames)},",
            f"    .frames = {variable}_frames,",
            "};",
            "",
        ]
    )
    (asset_dir / source_name).write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    metadata = {
        "name": animation.name,
        "symbol": animation.symbol,
        "width": animation.width,
        "height": animation.height,
        "stride": animation.stride,
        "frame_count": len(animation.frames),
        "durations_ms": [frame.duration_ms for frame in animation.frames],
    }
    (asset_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )


def manifest_path(generated_dir: Path) -> Path:
    return generated_dir / "manifest.json"


def load_manifest(generated_dir: Path) -> dict[str, dict[str, str]]:
    path = manifest_path(generated_dir)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    entries = raw.get("assets", [])
    result: dict[str, dict[str, str]] = {}
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            symbol = str(entry.get("symbol", "")).strip()
            kind = str(entry.get("kind", "")).strip()
            name = str(entry.get("name", symbol)).strip()
            if symbol and kind in {"image", "animation"}:
                result[symbol] = {
                    "symbol": symbol,
                    "kind": kind,
                    "name": name,
                }
    return result


def save_manifest(
    generated_dir: Path,
    entries: dict[str, dict[str, str]],
) -> None:
    ordered = [
        entries[key]
        for key in sorted(entries, key=natural_sort_key)
    ]
    manifest_path(generated_dir).write_text(
        json.dumps({"version": 1, "assets": ordered}, indent=2) + "\n",
        encoding="utf-8",
    )


def write_registry(
    generated_dir: Path,
    entries: dict[str, dict[str, str]],
) -> None:
    ordered = [
        entries[key]
        for key in sorted(entries, key=natural_sort_key)
    ]

    header_lines = [
        "#pragma once",
        "",
        '#include "sharpbit_types.h"',
        "",
    ]
    for entry in ordered:
        symbol = entry["symbol"]
        header_lines.append(f'#include "{symbol}/{symbol}.h"')
    header_lines.extend(
        [
            "",
            "#ifdef __cplusplus",
            'extern "C" {',
            "#endif",
            "",
            "extern const mono_asset_t *const sharpbit_assets[];",
            "extern const size_t sharpbit_assets_count;",
            "extern const mono_animation_t *const sharpbit_animations[];",
            "extern const size_t sharpbit_animations_count;",
            "",
            "const mono_asset_t *sharpbit_asset_find(const char *name);",
            "const mono_animation_t *sharpbit_animation_find(const char *name);",
            "",
            "#ifdef __cplusplus",
            "}",
            "#endif",
            "",
        ]
    )
    (generated_dir / "sharpbit_assets.h").write_text(
        "\n".join(header_lines),
        encoding="utf-8",
    )

    static_entries = [e for e in ordered if e["kind"] == "image"]
    animation_entries = [e for e in ordered if e["kind"] == "animation"]

    source_lines = [
        '#include "sharpbit_assets.h"',
        "",
        "#include <string.h>",
        "",
        "const mono_asset_t *const sharpbit_assets[] = {",
    ]
    if static_entries:
        for entry in static_entries:
            source_lines.append(
                f'    &sharpbit_asset_{entry["symbol"]},'
            )
    else:
        source_lines.append("    NULL,")
    source_lines.extend(
        [
            "};",
            "",
            (
                "const size_t sharpbit_assets_count = "
                "sizeof(sharpbit_assets) / sizeof(sharpbit_assets[0]);"
                if static_entries
                else "const size_t sharpbit_assets_count = 0;"
            ),
            "",
            "const mono_animation_t *const sharpbit_animations[] = {",
        ]
    )
    if animation_entries:
        for entry in animation_entries:
            source_lines.append(
                f'    &sharpbit_animation_{entry["symbol"]},'
            )
    else:
        source_lines.append("    NULL,")
    source_lines.extend(
        [
            "};",
            "",
            (
                "const size_t sharpbit_animations_count = "
                "sizeof(sharpbit_animations) / "
                "sizeof(sharpbit_animations[0]);"
                if animation_entries
                else "const size_t sharpbit_animations_count = 0;"
            ),
            "",
            "const mono_asset_t *sharpbit_asset_find(const char *name)",
            "{",
            "    if (name == NULL) { return NULL; }",
            "    for (size_t i = 0; i < sharpbit_assets_count; ++i) {",
            "        if (strcmp(sharpbit_assets[i]->name, name) == 0) {",
            "            return sharpbit_assets[i];",
            "        }",
            "    }",
            "    return NULL;",
            "}",
            "",
            "const mono_animation_t *sharpbit_animation_find(const char *name)",
            "{",
            "    if (name == NULL) { return NULL; }",
            "    for (size_t i = 0; i < sharpbit_animations_count; ++i) {",
            "        if (strcmp(sharpbit_animations[i]->name, name) == 0) {",
            "            return sharpbit_animations[i];",
            "        }",
            "    }",
            "    return NULL;",
            "}",
            "",
        ]
    )
    (generated_dir / "sharpbit_assets.c").write_text(
        "\n".join(source_lines),
        encoding="utf-8",
    )


def save_static_preview(
    preview_dir: Path,
    asset: MonoAsset,
    settings: dict[str, Any],
) -> None:
    bit_order, black_bit = validate_packing(settings)
    preview = unpack_image(
        asset.data,
        asset.width,
        asset.height,
        asset.stride,
        bit_order,
        black_bit,
    )
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview.save(preview_dir / f"{asset.symbol}.png")


def save_animation_preview(
    preview_dir: Path,
    animation: MonoAnimation,
    settings: dict[str, Any],
) -> None:
    bit_order, black_bit = validate_packing(settings)
    target = preview_dir / animation.symbol
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    decoded: list[Image.Image] = []
    durations: list[int] = []
    for index, frame in enumerate(animation.frames):
        image = unpack_image(
            frame.data,
            frame.width,
            frame.height,
            frame.stride,
            bit_order,
            black_bit,
        )
        image.save(target / f"frame_{index:04d}.png")
        decoded.append(image.convert("P"))
        durations.append(frame.duration_ms)

    if decoded:
        decoded[0].save(
            target / f"{animation.symbol}_preview.gif",
            save_all=True,
            append_images=decoded[1:],
            duration=durations,
            loop=0,
            optimize=False,
        )


def convert_all(
    source_items: list[Path],
    fallback_input_dir: Path,
    output_dir: Path,
    config_path: Path,
    asset_name: str,
    cli_overrides: dict[str, Any] | None = None,
    animation_cli_overrides: dict[str, Any] | None = None,
    clean_output: bool = False,
) -> tuple[list[MonoAsset], list[MonoAnimation]]:
    config = load_config(config_path)
    discovered = discover_sources(source_items, fallback_input_dir)
    if not discovered:
        raise RuntimeError("No supported source files found.")
    discovered = assign_output_names(discovered, asset_name)

    generated_dir = output_dir / "generated"
    preview_dir = output_dir / "preview"

    if clean_output and output_dir.exists():
        shutil.rmtree(output_dir)

    generated_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    write_types_header(generated_dir)

    manifest = load_manifest(generated_dir)
    assets: list[MonoAsset] = []
    animations: list[MonoAnimation] = []

    for path, relative, logical_name, kind in discovered:
        settings = merge_settings(relative, config, cli_overrides)
        symbol = sanitize_symbol(logical_name)

        old_entry = manifest.get(symbol)
        if old_entry:
            old_preview_file = preview_dir / f"{symbol}.png"
            old_preview_dir = preview_dir / symbol
            if old_preview_file.exists():
                old_preview_file.unlink()
            if old_preview_dir.exists():
                shutil.rmtree(old_preview_dir)

        if kind == "image":
            asset = convert_static_image(path, logical_name, settings)
            write_static_asset(generated_dir, asset)
            save_static_preview(preview_dir, asset, settings)
            assets.append(asset)
            manifest[symbol] = {
                "name": asset.name,
                "symbol": asset.symbol,
                "kind": "image",
            }
            print(
                f"[OK] image {relative} -> {asset.symbol} "
                f"({asset.width}x{asset.height}, {len(asset.data)} bytes)"
            )
        else:
            animation_settings = merge_animation_settings(
                config,
                animation_cli_overrides,
            )
            animation = convert_animation(
                path,
                logical_name,
                settings,
                animation_settings,
            )
            write_animation_asset(generated_dir, animation)
            save_animation_preview(preview_dir, animation, settings)
            animations.append(animation)
            manifest[symbol] = {
                "name": animation.name,
                "symbol": animation.symbol,
                "kind": "animation",
            }
            print(
                f"[OK] animation {relative} -> {animation.symbol} "
                f"({len(animation.frames)} frames, "
                f"{animation.width}x{animation.height})"
            )

    save_manifest(generated_dir, manifest)
    write_registry(generated_dir, manifest)

    print()
    print(f"Static images:  {len(assets)}")
    print(f"Animations:     {len(animations)}")
    print(f"Generated:      {generated_dir}")
    print(f"Preview:        {preview_dir}")

    return assets, animations


def collect_frame_paths(items: list[Path]) -> list[Path]:
    frames: list[Path] = []
    for item in items:
        item = item.resolve()
        if not item.exists():
            raise RuntimeError(f"Frame path does not exist: '{item}'")
        if item.is_dir():
            frames.extend(
                path
                for path in item.rglob("*")
                if is_supported_image(path)
            )
        elif is_supported_image(item):
            frames.append(item)
        else:
            raise RuntimeError(
                f"Unsupported frame '{item}'. "
                "Use PNG, JPG, JPEG, BMP or WebP."
            )

    unique = sorted(set(frames), key=natural_sort_key)
    if not unique:
        raise RuntimeError("No image frames selected.")
    return unique


def fit_rgb_frame(
    image: Image.Image,
    target_size: tuple[int, int],
) -> Image.Image:
    target_w, target_h = target_size
    rgb = image.convert("RGB")
    if rgb.size == target_size:
        return rgb

    copy = rgb.copy()
    copy.thumbnail(target_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", target_size, "white")
    canvas.paste(
        copy,
        ((target_w - copy.width) // 2, (target_h - copy.height) // 2),
    )
    return canvas


def build_video_from_frames(
    frame_items: list[Path],
    output_dir: Path,
    video_name: str,
    fps: int,
    output_format: str = "mp4",
) -> Path:
    name = sanitize_symbol(video_name)
    fps = int(fps)
    if fps <= 0 or fps > 120:
        raise RuntimeError("FPS must be between 1 and 120.")

    output_format = output_format.lower()
    if output_format not in {"mp4", "gif"}:
        raise RuntimeError("Output format must be MP4 or GIF.")

    frame_paths = collect_frame_paths(frame_items)
    loaded: list[Image.Image] = []
    try:
        first = Image.open(frame_paths[0]).convert("RGB")
        target_w, target_h = first.size

        if output_format == "mp4":
            target_w += target_w % 2
            target_h += target_h % 2

        target_size = (target_w, target_h)
        loaded.append(fit_rgb_frame(first, target_size))

        for path in frame_paths[1:]:
            with Image.open(path) as image:
                loaded.append(fit_rgb_frame(image, target_size))
    except (OSError, UnidentifiedImageError) as exc:
        raise RuntimeError(f"Cannot read frame images: {exc}") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}.{output_format}"

    if output_format == "gif":
        duration = max(1, round(1000 / fps))
        gif_frames = [frame.convert("P") for frame in loaded]
        gif_frames[0].save(
            output_path,
            save_all=True,
            append_images=gif_frames[1:],
            duration=duration,
            loop=0,
            optimize=False,
        )
    else:
        if imageio is None:
            raise RuntimeError(
                "MP4 support requires imageio and imageio-ffmpeg. "
                "Run install.bat first."
            )
        try:
            writer = imageio.get_writer(
                str(output_path),
                fps=fps,
                codec="libx264",
                pixelformat="yuv420p",
                macro_block_size=1,
                ffmpeg_log_level="error",
            )
            try:
                for frame in loaded:
                    writer.append_data(np.asarray(frame))
            finally:
                writer.close()
        except Exception as exc:
            raise RuntimeError(f"Cannot create MP4 video: {exc}") from exc

    return output_path
