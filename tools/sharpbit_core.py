from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageSequence, UnidentifiedImageError

try:
    import imageio.v2 as imageio
except Exception:
    imageio = None  # Loaded lazily for video use.


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


def sanitize_symbol(logical_name: str) -> str:
    symbol = re.sub(r"[^A-Za-z0-9_]", "_", logical_name)
    symbol = re.sub(r"_+", "_", symbol).strip("_").lower()
    if not symbol:
        symbol = "asset"
    if symbol[0].isdigit():
        symbol = f"asset_{symbol}"
    return symbol


def is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def is_supported_animation(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_ANIMATION_EXTENSIONS


def discover_sources(
    source_items: list[Path],
    fallback_input_dir: Path,
) -> list[tuple[Path, str, str, str]]:
    """
    Returns tuples:
      (absolute_path, relative_with_ext, logical_name_without_ext, kind)
    kind is 'image' or 'animation'
    """
    items = [item.resolve() for item in source_items] if source_items else [fallback_input_dir.resolve()]
    discovered: list[tuple[Path, str, str, str]] = []

    for item in items:
        if not item.exists():
            raise RuntimeError(f"Source path does not exist: '{item}'")

        if item.is_dir():
            for path in sorted(item.rglob("*")):
                if is_supported_image(path):
                    relative_with_ext = path.relative_to(item).as_posix()
                    logical_name = Path(relative_with_ext).with_suffix("").as_posix()
                    discovered.append((path, relative_with_ext, logical_name, "image"))
                elif is_supported_animation(path):
                    relative_with_ext = path.relative_to(item).as_posix()
                    logical_name = Path(relative_with_ext).with_suffix("").as_posix()
                    discovered.append((path, relative_with_ext, logical_name, "animation"))
        elif is_supported_image(item):
            discovered.append((item, item.name, item.stem, "image"))
        elif is_supported_animation(item):
            discovered.append((item, item.name, item.stem, "animation"))
        else:
            raise RuntimeError(
                f"Unsupported source path '{item}'. "
                "Use PNG, JPG, JPEG, BMP, WebP, GIF, MP4, MOV, AVI, MKV or WEBM files, "
                "or folders containing them."
            )

    return discovered


def flatten_on_background(path: Path, background: int) -> Image.Image:
    try:
        with Image.open(path) as source:
            source.load()
            rgba = source.convert("RGBA")
    except (OSError, UnidentifiedImageError) as exc:
        raise RuntimeError(f"Cannot open image '{path}': {exc}") from exc

    return flatten_rgba_image(rgba, background)


def flatten_rgba_image(image: Image.Image, background: int) -> Image.Image:
    rgba = image.convert("RGBA")
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

        source_ratio = image.width / image.height
        target_ratio = width / height

        if fit == "cover":
            if source_ratio > target_ratio:
                resized_height = height
                resized_width = round(height * source_ratio)
            else:
                resized_width = width
                resized_height = round(width / source_ratio)

            resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
            left = (resized_width - width) // 2
            top = (resized_height - height) // 2
            return resized.crop((left, top, left + width, top + height))

        if fit != "contain":
            raise RuntimeError(f"Unknown fit mode '{fit}'. Use contain, cover or stretch.")

        copy = image.copy()
        copy.thumbnail((width, height), Image.Resampling.LANCZOS)
        background = max(0, min(255, int(settings.get("background", 255))))
        canvas = Image.new("L", (width, height), background)
        canvas.paste(copy, ((width - copy.width) // 2, (height - copy.height) // 2))
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


def ordered_dither(image: Image.Image, matrix: tuple[tuple[int, ...], ...]) -> Image.Image:
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
        mono = image.point(lambda pixel: 255 if pixel >= threshold else 0, mode="1")
    elif dither == "bayer2":
        mono = ordered_dither(image, BAYER_2)
    elif dither == "bayer4":
        mono = ordered_dither(image, BAYER_4)
    elif dither == "floyd":
        mono = image.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    else:
        raise RuntimeError(
            f"Unknown dither mode '{dither}'. Use threshold, bayer2, bayer4 or floyd."
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
            shift = 7 - (x % 8) if bit_order == "msb" else x % 8
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
                rgba = frame.convert("RGBA")
                frames.append((rgba, max(1, duration)))
    except (OSError, UnidentifiedImageError) as exc:
        raise RuntimeError(f"Cannot open GIF '{path}': {exc}") from exc
    return frames


def load_video_frames(path: Path, video_fps: int, max_frames: int) -> list[tuple[Image.Image, int]]:
    if imageio is None:
        raise RuntimeError(
            "Video support requires imageio and imageio-ffmpeg. "
            "Run: python -m pip install -r requirements.txt"
        )

    try:
        reader = imageio.get_reader(str(path))
    except Exception as exc:
        raise RuntimeError(f"Cannot open video '{path}': {exc}") from exc

    frames: list[tuple[Image.Image, int]] = []
    target_fps = max(1, int(video_fps))
    duration = max(1, round(1000 / target_fps))

    try:
        metadata = reader.get_meta_data()
        source_fps = float(metadata.get("fps", target_fps) or target_fps)
        step = max(1, round(source_fps / target_fps))
    except Exception:
        step = 1

    try:
        for index, frame_array in enumerate(reader):
            if index % step != 0:
                continue
            rgba = Image.fromarray(frame_array).convert("RGBA")
            frames.append((rgba, duration))
            if len(frames) >= max_frames:
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
    relative_with_ext: str,
    logical_name: str,
    settings: dict[str, Any],
) -> MonoAsset:
    bit_order, black_bit = validate_packing(settings)
    grayscale = flatten_on_background(path, int(settings.get("background", 255)))
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
    relative_with_ext: str,
    logical_name: str,
    settings: dict[str, Any],
    animation_settings: dict[str, Any],
) -> MonoAnimation:
    extension = path.suffix.lower()
    if extension == ".gif":
        raw_frames = load_gif_frames(path)
    else:
        raw_frames = load_video_frames(
            path,
            video_fps=int(animation_settings.get("video_fps", 10)),
            max_frames=int(animation_settings.get("max_frames", 120)),
        )

    if not raw_frames:
        raise RuntimeError(f"No frames decoded from '{path}'.")

    bit_order, black_bit = validate_packing(settings)
    frames: list[MonoAnimationFrame] = []

    base_width = None
    base_height = None
    base_stride = None

    for rgba_frame, duration_ms in raw_frames:
        grayscale = flatten_rgba_image(rgba_frame, int(settings.get("background", 255)))
        resized = resize_image(grayscale, settings)
        mono = to_monochrome(resized, settings)
        data, stride = pack_image(mono, bit_order, black_bit)

        if base_width is None:
            base_width = mono.width
            base_height = mono.height
            base_stride = stride
        elif mono.width != base_width or mono.height != base_height or stride != base_stride:
            raise RuntimeError(
                f"Frame size mismatch while processing '{path}'. "
                "Ensure all frames convert to the same output size."
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


def clean_preview_dir(preview_dir: Path) -> None:
    if preview_dir.exists():
        shutil.rmtree(preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)


def format_bytes(data: bytes) -> str:
    lines: list[str] = []
    for offset in range(0, len(data), 12):
        chunk = data[offset : offset + 12]
        values = ", ".join(f"0x{byte:02X}" for byte in chunk)
        lines.append(f"    {values},")
    return "\n".join(lines)


def write_header(path: Path, assets: list[MonoAsset], animations: list[MonoAnimation]) -> None:
    asset_declarations = "\n".join(
        f"extern const mono_asset_t mono_asset_{asset.symbol};" for asset in assets
    )
    animation_declarations = "\n".join(
        f"extern const mono_animation_t mono_animation_{animation.symbol};" for animation in animations
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""#pragma once

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

typedef struct {{
    const uint8_t *data;
    size_t data_size;
    uint16_t duration_ms;
}} mono_animation_frame_t;

typedef struct {{
    const char *name;
    uint16_t width;
    uint16_t height;
    uint16_t stride;
    uint16_t frame_count;
    const mono_animation_frame_t *frames;
}} mono_animation_t;

{asset_declarations}

{animation_declarations}

extern const mono_asset_t *const mono_assets[];
extern const size_t mono_assets_count;

extern const mono_animation_t *const mono_animations[];
extern const size_t mono_animations_count;

const mono_asset_t *mono_asset_find(const char *name);
const mono_animation_t *mono_animation_find(const char *name);

#ifdef __cplusplus
}}
#endif
""",
        encoding="utf-8",
    )


def write_source(path: Path, header_name: str, assets: list[MonoAsset], animations: list[MonoAnimation]) -> None:
    lines = [f'#include "{header_name}"', "", "#include <string.h>", ""]

    for asset in assets:
        lines.extend(
            [
                f"static const uint8_t mono_asset_{asset.symbol}_data[] __attribute__((aligned(4))) = {{",
                format_bytes(asset.data),
                "};",
                "",
                f"const mono_asset_t mono_asset_{asset.symbol} = {{",
                f'    .name = "{asset.name}",',
                f"    .width = {asset.width},",
                f"    .height = {asset.height},",
                f"    .stride = {asset.stride},",
                f"    .data = mono_asset_{asset.symbol}_data,",
                f"    .data_size = sizeof(mono_asset_{asset.symbol}_data),",
                "};",
                "",
            ]
        )

    for animation in animations:
        for index, frame in enumerate(animation.frames):
            lines.extend(
                [
                    f"static const uint8_t mono_animation_{animation.symbol}_frame_{index:04d}[] __attribute__((aligned(4))) = {{",
                    format_bytes(frame.data),
                    "};",
                    "",
                ]
            )

        lines.append(
            f"static const mono_animation_frame_t mono_animation_{animation.symbol}_frames[] = {{"
        )
        for index, frame in enumerate(animation.frames):
            lines.extend(
                [
                    "    {",
                    f"        .data = mono_animation_{animation.symbol}_frame_{index:04d},",
                    f"        .data_size = sizeof(mono_animation_{animation.symbol}_frame_{index:04d}),",
                    f"        .duration_ms = {frame.duration_ms},",
                    "    },",
                ]
            )
        lines.extend(
            [
                "};",
                "",
                f"const mono_animation_t mono_animation_{animation.symbol} = {{",
                f'    .name = "{animation.name}",',
                f"    .width = {animation.width},",
                f"    .height = {animation.height},",
                f"    .stride = {animation.stride},",
                f"    .frame_count = {len(animation.frames)},",
                f"    .frames = mono_animation_{animation.symbol}_frames,",
                "};",
                "",
            ]
        )

    if assets:
        lines.append("const mono_asset_t *const mono_assets[] = {")
        for asset in assets:
            lines.append(f"    &mono_asset_{asset.symbol},")
        lines.append("};")
        lines.extend(["", "const size_t mono_assets_count = sizeof(mono_assets) / sizeof(mono_assets[0]);"])
    else:
        lines.extend(["const mono_asset_t *const mono_assets[] = {", "    NULL,", "};", "", "const size_t mono_assets_count = 0;"])

    if animations:
        lines.append("")
        lines.append("const mono_animation_t *const mono_animations[] = {")
        for animation in animations:
            lines.append(f"    &mono_animation_{animation.symbol},")
        lines.append("};")
        lines.extend(["", "const size_t mono_animations_count = sizeof(mono_animations) / sizeof(mono_animations[0]);"])
    else:
        lines.extend(["", "const mono_animation_t *const mono_animations[] = {", "    NULL,", "};", "", "const size_t mono_animations_count = 0;"])

    lines.extend(
        [
            "",
            "const mono_asset_t *mono_asset_find(const char *name)",
            "{",
            "    if (name == NULL) { return NULL; }",
            "    for (size_t i = 0; i < mono_assets_count; ++i) {",
            "        if (strcmp(mono_assets[i]->name, name) == 0) {",
            "            return mono_assets[i];",
            "        }",
            "    }",
            "    return NULL;",
            "}",
            "",
            "const mono_animation_t *mono_animation_find(const char *name)",
            "{",
            "    if (name == NULL) { return NULL; }",
            "    for (size_t i = 0; i < mono_animations_count; ++i) {",
            "        if (strcmp(mono_animations[i]->name, name) == 0) {",
            "            return mono_animations[i];",
            "        }",
            "    }",
            "    return NULL;",
            "}",
            "",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_animation_metadata(
    generated_dir: Path,
    animation: MonoAnimation,
) -> None:
    metadata_dir = generated_dir / "animations" / animation.name
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "name": animation.name,
        "width": animation.width,
        "height": animation.height,
        "stride": animation.stride,
        "frame_count": len(animation.frames),
        "durations_ms": [frame.duration_ms for frame in animation.frames],
    }
    (metadata_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )


def convert_all(
    source_items: list[Path],
    fallback_input_dir: Path,
    output_dir: Path,
    config_path: Path,
    cli_overrides: dict[str, Any] | None = None,
    animation_cli_overrides: dict[str, Any] | None = None,
) -> tuple[list[MonoAsset], list[MonoAnimation]]:
    config = load_config(config_path)
    discovered = discover_sources(source_items, fallback_input_dir)

    generated_dir = output_dir / "generated"
    preview_dir = output_dir / "preview"
    output_h = generated_dir / "assets.h"
    output_c = generated_dir / "assets.c"

    generated_dir.mkdir(parents=True, exist_ok=True)
    clean_preview_dir(preview_dir)

    animation_generated_dir = generated_dir / "animations"
    if animation_generated_dir.exists():
        shutil.rmtree(animation_generated_dir)
    animation_generated_dir.mkdir(parents=True, exist_ok=True)

    assets: list[MonoAsset] = []
    animations: list[MonoAnimation] = []
    used_names: set[str] = set()
    used_symbols: set[str] = set()

    for path, relative_with_ext, logical_name, kind in discovered:
        if logical_name in used_names:
            raise RuntimeError(f"Asset name collision: '{logical_name}'.")
        used_names.add(logical_name)

        symbol = sanitize_symbol(logical_name)
        if symbol in used_symbols:
            raise RuntimeError(f"Asset symbol collision: '{logical_name}' becomes '{symbol}'.")
        used_symbols.add(symbol)

        settings = merge_settings(relative_with_ext, config, cli_overrides)
        if kind == "image":
            asset = convert_static_image(path, relative_with_ext, logical_name, settings)
            assets.append(asset)

            bit_order, black_bit = validate_packing(settings)
            preview = unpack_image(asset.data, asset.width, asset.height, asset.stride, bit_order, black_bit)
            preview_path = preview_dir / Path(logical_name).with_suffix(".png")
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview.save(preview_path)
            print(f"[OK] image {relative_with_ext} -> {logical_name} ({asset.width}x{asset.height}, {len(asset.data)} bytes)")
        else:
            animation_settings = merge_animation_settings(config, animation_cli_overrides)
            animation = convert_animation(path, relative_with_ext, logical_name, settings, animation_settings)
            animations.append(animation)

            bit_order, black_bit = validate_packing(settings)
            preview_anim_dir = preview_dir / "animations" / logical_name
            preview_anim_dir.mkdir(parents=True, exist_ok=True)
            for frame_index, frame in enumerate(animation.frames):
                preview = unpack_image(
                    frame.data,
                    frame.width,
                    frame.height,
                    frame.stride,
                    bit_order,
                    black_bit,
                )
                preview.save(preview_anim_dir / f"frame_{frame_index:04d}.png")

            write_animation_metadata(generated_dir, animation)
            print(f"[OK] animation {relative_with_ext} -> {logical_name} ({len(animation.frames)} frames, {animation.width}x{animation.height})")

    write_header(output_h, assets, animations)
    write_source(output_c, output_h.name, assets, animations)

    print()
    print(f"Static images:    {len(assets)}")
    print(f"Animations:       {len(animations)}")
    print(f"Generated code:   {output_c}")
    print(f"Generated header: {output_h}")
    print(f"Preview folder:   {preview_dir}")

    return assets, animations
