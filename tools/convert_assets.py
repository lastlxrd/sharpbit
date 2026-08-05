#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sharpbit_core import convert_all

VERSION = "1.2.1"
ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert images, GIFs and short videos into monochrome 1-bit C assets."
    )
    parser.add_argument(
        "sources",
        nargs="*",
        type=Path,
        help="Optional files or folders. If omitted, the default input/ folder is used.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "input",
        help="Default source directory when no positional sources are provided.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output",
        help="Output directory.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config.json",
        help="JSON configuration file.",
    )

    # Global conversion overrides.
    parser.add_argument("--dither", choices=["threshold", "bayer2", "bayer4", "floyd"])
    parser.add_argument("--threshold", type=int)
    parser.add_argument("--invert-image", action="store_true")
    parser.add_argument("--background", type=int)
    parser.add_argument("--bit-order", choices=["msb", "lsb"])
    parser.add_argument("--black-bit", type=int, choices=[0, 1])
    parser.add_argument("--fit", choices=["contain", "cover", "stretch"])
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--max-width", type=int)
    parser.add_argument("--max-height", type=int)
    parser.add_argument("--display-width", type=int, help="Alias for --max-width.")
    parser.add_argument("--display-height", type=int, help="Alias for --max-height.")

    # Animation/video overrides.
    parser.add_argument("--video-fps", type=int, help="Target FPS for decoded video frames.")
    parser.add_argument("--max-frames", type=int, help="Maximum decoded frames for GIF/video.")

    parser.add_argument(
        "--version",
        action="version",
        version=f"SharpBit {VERSION}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    effective_max_width = args.max_width if args.max_width is not None else args.display_width
    effective_max_height = args.max_height if args.max_height is not None else args.display_height

    cli_overrides = {
        "dither": args.dither,
        "threshold": args.threshold,
        "invert_image": True if args.invert_image else None,
        "background": args.background,
        "bit_order": args.bit_order,
        "black_bit": args.black_bit,
        "fit": args.fit,
        "width": args.width,
        "height": args.height,
        "max_width": effective_max_width,
        "max_height": effective_max_height,
    }

    animation_cli_overrides = {
        "video_fps": args.video_fps,
        "max_frames": args.max_frames,
    }

    convert_all(
        source_items=[path.resolve() for path in args.sources],
        fallback_input_dir=args.input.resolve(),
        output_dir=args.output.resolve(),
        config_path=args.config.resolve(),
        cli_overrides=cli_overrides,
        animation_cli_overrides=animation_cli_overrides,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
