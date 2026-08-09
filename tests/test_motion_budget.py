from __future__ import annotations

import importlib.util
import sys
import unittest
from argparse import Namespace
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "motion_budget.py"
SPEC = importlib.util.spec_from_file_location("motion_budget", MODULE_PATH)
assert SPEC and SPEC.loader
MOTION_BUDGET = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOTION_BUDGET
SPEC.loader.exec_module(MOTION_BUDGET)


def arguments(**overrides: object) -> Namespace:
    values: dict[str, object] = {
        "frames": 96,
        "display": (240, 240),
        "dpr": 1.0,
        "max_texture": 4096,
        "driver": "pointer",
        "parameter_space": "circular",
        "access": "auto",
        "atlas_max_memory_mib": 192.0,
        "linear_video_min_frames": 180,
        "source": None,
        "cell": None,
        "scroll_pages": None,
        "frames_per_page": 24.0,
    }
    values.update(overrides)
    return Namespace(**values)


class MotionBudgetSelectionTests(unittest.TestCase):
    def test_small_random_sequence_selects_alpha_atlas(self) -> None:
        report = MOTION_BUDGET.build_report(arguments())

        self.assertEqual(report["delivery"]["selected"], "alpha-atlas")
        self.assertEqual(report["delivery"]["runtime"], "css-alpha-atlas")
        self.assertTrue(report["passes"])

    def test_large_linear_scroll_selects_chroma_video(self) -> None:
        report = MOTION_BUDGET.build_report(
            arguments(
                frames=551,
                display=(1536, 864),
                driver="scroll",
                parameter_space="linear",
            )
        )

        self.assertEqual(report["delivery"]["selected"], "chroma-video")
        self.assertEqual(report["delivery"]["runtime"], "webgl-chroma-video")
        self.assertIn("long-linear-sequence", report["delivery"]["reasonCodes"])
        self.assertTrue(report["passes"])

    def test_two_dimensional_input_is_never_flattened_to_video(self) -> None:
        report = MOTION_BUDGET.build_report(
            arguments(
                frames=400,
                display=(900, 900),
                parameter_space="2d",
            )
        )

        self.assertEqual(report["delivery"]["selected"], "alpha-atlas")
        self.assertIn(
            "two-dimensional-parameter-needs-discrete-frames",
            report["delivery"]["reasonCodes"],
        )
        self.assertFalse(report["passes"])

    def test_discrete_states_are_split_instead_of_flattened(self) -> None:
        report = MOTION_BUDGET.build_report(
            arguments(
                frames=400,
                display=(900, 900),
                driver="state",
                parameter_space="discrete",
            )
        )

        self.assertEqual(report["delivery"]["selected"], "alpha-atlas")
        self.assertIn(
            "discrete-states-need-independent-assets",
            report["delivery"]["reasonCodes"],
        )
        self.assertFalse(report["passes"])


if __name__ == "__main__":
    unittest.main()
