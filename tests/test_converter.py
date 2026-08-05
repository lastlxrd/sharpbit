from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "convert_assets.py"
)

spec = importlib.util.spec_from_file_location("sharpbit_converter", MODULE_PATH)
assert spec is not None and spec.loader is not None
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)


class SharpBitTests(unittest.TestCase):
    def test_pack_round_trip_all_modes(self) -> None:
        image = Image.new("1", (9, 3), 255)
        pixels = image.load()

        for x, y in ((0, 0), (8, 0), (4, 1), (1, 2), (7, 2)):
            pixels[x, y] = 0

        for bit_order in ("msb", "lsb"):
            for black_bit in (0, 1):
                data, stride = converter.pack_image(
                    image,
                    bit_order,
                    black_bit,
                )
                decoded = converter.unpack_image(
                    data,
                    image.width,
                    image.height,
                    stride,
                    bit_order,
                    black_bit,
                )
                self.assertEqual(image.tobytes(), decoded.tobytes())

    def test_empty_input_generates_valid_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            output_dir = root / "output"
            config_path = root / "config.json"

            input_dir.mkdir()
            config_path.write_text(
                '{"defaults": {}, "overrides": {}}',
                encoding="utf-8",
            )

            assets = converter.convert_all(
                input_dir,
                output_dir,
                config_path,
            )

            self.assertEqual(assets, [])
            source = (output_dir / "generated" / "assets.c").read_text(
                encoding="utf-8"
            )
            self.assertIn("mono_assets_count = 0", source)
            self.assertIn("NULL", source)

    def test_full_conversion_creates_code_and_preview(self) -> None:
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

            config_path.write_text(
                '{"defaults": {"dither": "threshold"}, "overrides": {}}',
                encoding="utf-8",
            )

            assets = converter.convert_all(
                input_dir,
                output_dir,
                config_path,
            )

            self.assertEqual(len(assets), 1)
            self.assertEqual(assets[0]["name"], "icons/test")
            self.assertTrue(
                (output_dir / "generated" / "assets.c").exists()
            )
            self.assertTrue(
                (output_dir / "generated" / "assets.h").exists()
            )
            self.assertTrue(
                (output_dir / "preview" / "icons" / "test.png").exists()
            )


if __name__ == "__main__":
    unittest.main()
