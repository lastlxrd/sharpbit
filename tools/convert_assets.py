#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sharpbit_core import convert_all

VERSION = "1.3.0"
ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert images, GIFs and short videos into monochrome "
            "1-bit C assets."
        )
    )
    parser.add_argument(
        "sources",
        nargs="*",
        type=Path,
        help=(
            "Files or folders. If omitted, the input/ folder is used."
        ),
    )
    parser.add_argument(
        "--name",
        required=True,
        help=(
            "Required asset name. With multiple sources it is used "
            "as a prefix."
        ),
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "input",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config.json",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete all previous generated output first.",
    )

    parser.add_argument(
        "--dither",
        choices=["threshold", "bayer2", "bayer4", "floyd"],
    )
    parser.add_argument("--threshold", type=int)
    parser.add_argument("--invert-image", action="store_true")
    parser.add_argument("--background", type=int)
    parser.add_argument("--bit-order", choices=["msb", "lsb"])
    parser.add_argument("--black-bit", type=int, choices=[0, 1])
    parser.add_argument(
        "--fit",
        choices=["contain", "cover", "stretch"],
    )
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--max-width", type=int)
    parser.add_argument("--max-height", type=int)
    parser.add_argument("--display-width", type=int)
    parser.add_argument("--display-height", type=int)

    parser.add_argument("--video-fps", type=int)
    parser.add_argument("--max-frames", type=int)

    parser.add_argument(
        "--version",
        action="version",
        version=f"SharpBit {VERSION}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    max_width = (
        args.max_width
        if args.max_width is not None
        else args.display_width
    )
    max_height = (
        args.max_height
        if args.max_height is not None
        else args.display_height
    )

    convert_all(
        source_items=[path.resolve() for path in args.sources],
        fallback_input_dir=args.input.resolve(),
        output_dir=args.output.resolve(),
        config_path=args.config.resolve(),
        asset_name=args.name,
        cli_overrides={
            "dither": args.dither,
            "threshold": args.threshold,
            "invert_image": True if args.invert_image else None,
            "background": args.background,
            "bit_order": args.bit_order,
            "black_bit": args.black_bit,
            "fit": args.fit,
            "width": args.width,
            "height": args.height,
            "max_width": max_width,
            "max_height": max_height,
        },
        animation_cli_overrides={
            "video_fps": args.video_fps,
            "max_frames": args.max_frames,
        },
        clean_output=args.clean,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
