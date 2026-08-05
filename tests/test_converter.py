from __future__ import annotations

import importlib.util
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


class SharpBitTests(unittest.TestCase):
    def test_pack_round_trip_all_modes(self) -> None:
        image = Image.new("1", (9, 3), 255)
        pixels = image.load()
        for x, y in ((0, 0), (8, 0), (4, 1), (1, 2), (7, 2)):
            pixels[x, y] = 0

        for bit_order in ("msb", "lsb"):
            for black_bit in (0, 1):
                data, stride = core.pack_image(image, bit_order, black_bit)
                decoded = core.unpack_image(data, image.width, image.height, stride, bit_order, black_bit)
                self.assertEqual(image.tobytes(), decoded.tobytes())

    def test_empty_input_generates_valid_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            output_dir = root / "output"
            config_path = root / "config.json"
            input_dir.mkdir()
            config_path.write_text('{"defaults": {}, "animation_defaults": {}, "overrides": {}}', encoding="utf-8")

            assets, animations = core.convert_all(
                source_items=[],
                fallback_input_dir=input_dir,
                output_dir=output_dir,
                config_path=config_path,
                cli_overrides={},
                animation_cli_overrides={},
            )

            self.assertEqual(assets, [])
            self.assertEqual(animations, [])
            source = (output_dir / "generated" / "assets.c").read_text(encoding="utf-8")
            self.assertIn("mono_assets_count = 0", source)
            self.assertIn("mono_animations_count = 0", source)

    def test_full_image_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            output_dir = root / "output"
            config_path = root / "config.json"

            nested = input_dir / "icons"
            nested.mkdir(parents=True)
            image = Image.new("L", (13, 7), 255)
            for x in range(13):
                image.putpixel((x, x % 7), 0)
            image.save(nested / "test.png")

            config_path.write_text('{"defaults": {"dither": "threshold"}, "animation_defaults": {}, "overrides": {}}', encoding="utf-8")

            assets, animations = core.convert_all(
                source_items=[],
                fallback_input_dir=input_dir,
                output_dir=output_dir,
                config_path=config_path,
                cli_overrides={},
                animation_cli_overrides={},
            )

            self.assertEqual(len(assets), 1)
            self.assertEqual(len(animations), 0)
            self.assertEqual(assets[0].name, "icons/test")
            self.assertTrue((output_dir / "preview" / "icons" / "test.png").exists())

    def test_gif_conversion_creates_animation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output_dir = root / "output"
            config_path = root / "config.json"
            config_path.write_text('{"defaults": {"dither": "threshold"}, "animation_defaults": {"max_frames": 10}, "overrides": {}}', encoding="utf-8")

            gif_path = root / "blink.gif"
            frame1 = Image.new("RGBA", (12, 12), (255, 255, 255, 255))
            frame2 = Image.new("RGBA", (12, 12), (255, 255, 255, 255))
            frame1.putpixel((2, 2), (0, 0, 0, 255))
            frame2.putpixel((8, 8), (0, 0, 0, 255))
            frame1.save(gif_path, save_all=True, append_images=[frame2], duration=[80, 120], loop=0)

            assets, animations = core.convert_all(
                source_items=[gif_path],
                fallback_input_dir=root / "unused",
                output_dir=output_dir,
                config_path=config_path,
                cli_overrides={},
                animation_cli_overrides={},
            )

            self.assertEqual(len(assets), 0)
            self.assertEqual(len(animations), 1)
            anim = animations[0]
            self.assertEqual(anim.name, "blink")
            self.assertEqual(len(anim.frames), 2)
            self.assertTrue((output_dir / "preview" / "animations" / "blink" / "frame_0000.png").exists())
            self.assertTrue((output_dir / "generated" / "animations" / "blink" / "metadata.json").exists())


if __name__ == "__main__":
    unittest.main()
