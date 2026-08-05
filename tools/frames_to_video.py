#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sharpbit_core import build_video_from_frames

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an MP4 or GIF from image frames."
    )
    parser.add_argument(
        "frames",
        nargs="+",
        type=Path,
        help="Frame image files or folders.",
    )
    parser.add_argument("--name", required=True)
    parser.add_argument("--fps", required=True, type=int)
    parser.add_argument(
        "--format",
        choices=["mp4", "gif"],
        default="mp4",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "rebuilt_videos",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = build_video_from_frames(
        frame_items=args.frames,
        output_dir=args.output,
        video_name=args.name,
        fps=args.fps,
        output_format=args.format,
    )
    print(f"Created: {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
