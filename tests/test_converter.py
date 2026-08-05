from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "sharpbit_core.py"

spec = importlib.util.spec_from_file_location("sharpbit_core", MODULE_PATH)
assert spec is not None and spec.loader is not None
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


def write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "defaults": {"dither": "threshold"},
                "animation_defaults": {"max_frames": 20},
                "overrides": {},
            }
        ),
        encoding="utf-8",
    )


class SharpBitTests(unittest.TestCase):
    def test_pack_round_trip_all_modes(self) -> None:
        image = Image.new("1", (9, 3), 255)
        pixels = image.load()
        for x, y in ((0, 0), (8, 0), (4, 1), (1, 2), (7, 2)):
            pixels[x, y] = 0

        for bit_order in ("msb", "lsb"):
            for black_bit in (0, 1):
                data, stride = core.pack_image(
                    image,
                    bit_order,
                    black_bit,
                )
                decoded = core.unpack_image(
                    data,
                    image.width,
                    image.height,
                    stride,
                    bit_order,
                    black_bit,
                )
                self.assertEqual(image.tobytes(), decoded.tobytes())

    def test_single_asset_uses_required_name_and_separate_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            image_path = base / "random_source_name.png"
            Image.new("L", (13, 7), 255).save(image_path)
            config_path = base / "config.json"
            write_config(config_path)
            output = base / "output"

            assets, animations = core.convert_all(
                source_items=[image_path],
                fallback_input_dir=base / "unused",
                output_dir=output,
                config_path=config_path,
                asset_name="Boot Logo",
            )

            self.assertEqual(len(assets), 1)
            self.assertEqual(animations, [])
            self.assertEqual(assets[0].name, "boot_logo")
            asset_dir = output / "generated" / "boot_logo"
            self.assertTrue((asset_dir / "boot_logo.c").exists())
            self.assertTrue((asset_dir / "boot_logo.h").exists())
            self.assertTrue(
                (output / "preview" / "boot_logo.png").exists()
            )
            source = (asset_dir / "boot_logo.c").read_text(
                encoding="utf-8"
            )
            self.assertIn("sharpbit_asset_boot_logo", source)

    def test_multiple_sources_use_name_as_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            first = base / "play.png"
            second = base / "settings.png"
            Image.new("L", (8, 8), 0).save(first)
            Image.new("L", (8, 8), 255).save(second)
            config_path = base / "config.json"
            write_config(config_path)

            assets, _ = core.convert_all(
                source_items=[first, second],
                fallback_input_dir=base / "unused",
                output_dir=base / "output",
                config_path=config_path,
                asset_name="menu",
            )

            self.assertEqual(
                sorted(asset.name for asset in assets),
                ["menu_play", "menu_settings"],
            )

    def test_new_conversion_preserves_previous_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config_path = base / "config.json"
            write_config(config_path)
            output = base / "output"

            one = base / "one.png"
            two = base / "two.png"
            Image.new("L", (8, 8), 0).save(one)
            Image.new("L", (8, 8), 255).save(two)

            core.convert_all(
                [one],
                base / "unused",
                output,
                config_path,
                asset_name="first",
            )
            core.convert_all(
                [two],
                base / "unused",
                output,
                config_path,
                asset_name="second",
            )

            self.assertTrue(
                (output / "generated" / "first" / "first.c").exists()
            )
            self.assertTrue(
                (output / "generated" / "second" / "second.c").exists()
            )
            registry = (
                output / "generated" / "sharpbit_assets.h"
            ).read_text(encoding="utf-8")
            self.assertIn('"first/first.h"', registry)
            self.assertIn('"second/second.h"', registry)

    def test_gif_creates_separate_animation_and_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            gif_path = base / "input.gif"
            frame1 = Image.new("RGBA", (12, 12), "white")
            frame2 = Image.new("RGBA", (12, 12), "white")
            frame1.putpixel((2, 2), (0, 0, 0, 255))
            frame2.putpixel((8, 8), (0, 0, 0, 255))
            frame1.save(
                gif_path,
                save_all=True,
                append_images=[frame2],
                duration=[80, 120],
                loop=0,
            )
            config_path = base / "config.json"
            write_config(config_path)
            output = base / "output"

            assets, animations = core.convert_all(
                [gif_path],
                base / "unused",
                output,
                config_path,
                asset_name="blink",
            )

            self.assertEqual(assets, [])
            self.assertEqual(len(animations), 1)
            asset_dir = output / "generated" / "blink"
            self.assertTrue((asset_dir / "blink.c").exists())
            self.assertTrue((asset_dir / "blink.h").exists())
            self.assertTrue((asset_dir / "metadata.json").exists())
            preview = output / "preview" / "blink"
            self.assertTrue((preview / "frame_0000.png").exists())
            self.assertTrue((preview / "blink_preview.gif").exists())

    def test_frames_can_be_rebuilt_as_gif(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            frames = base / "frames"
            frames.mkdir()
            Image.new("RGB", (16, 10), "white").save(
                frames / "frame_10.png"
            )
            Image.new("RGB", (16, 10), "black").save(
                frames / "frame_2.png"
            )

            output = core.build_video_from_frames(
                frame_items=[frames],
                output_dir=base / "videos",
                video_name="My Preview",
                fps=12,
                output_format="gif",
            )

            self.assertEqual(output.name, "my_preview.gif")
            self.assertTrue(output.exists())
            with Image.open(output) as image:
                self.assertEqual(image.n_frames, 2)


if __name__ == "__main__":
    unittest.main()
