from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location(
    "compile_scroll_video",
    SCRIPT_DIR / "compile_scroll_video.py",
)
assert SPEC and SPEC.loader
COMPILE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = COMPILE
SPEC.loader.exec_module(COMPILE)


class ChromaVideoCompileTests(unittest.TestCase):
    def test_representative_frames_include_both_ends(self) -> None:
        paths = [Path(f"frame_{index:05d}.png") for index in range(100)]

        sampled = COMPILE.representative_frames(paths)

        self.assertEqual(len(sampled), 48)
        self.assertEqual(sampled[0], paths[0])
        self.assertEqual(sampled[-1], paths[-1])

    def test_uniform_green_frames_pass_key_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths: list[Path] = []
            for index in range(3):
                path = Path(directory) / f"frame_{index:05d}.png"
                image = Image.new("RGB", (32, 32), (0, 255, 0))
                image.paste((255, 0, 0), (8, 8, 24, 24))
                image.save(path)
                paths.append(path)

            result = COMPILE.validate_key_source(paths, (0, 255, 0))

            self.assertEqual(result["kind"], "green")
            self.assertEqual(result["borderSpreadP95Max"], 0)

    def test_non_chroma_background_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.png"
            Image.new("RGB", (32, 32), (255, 255, 255)).save(path)

            with self.assertRaisesRegex(ValueError, "绿色或洋红色键背景"):
                COMPILE.validate_key_source([path], (255, 255, 255))

    def test_video_compiler_rejects_atlas_budget_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "budget.json"
            path.write_text(
                json.dumps(
                    {
                        "passes": True,
                        "delivery": {"selected": "alpha-atlas"},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "没有选择 chroma-video"):
                COMPILE.load_budget_report(path)


if __name__ == "__main__":
    unittest.main()
