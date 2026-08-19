from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GATE = load("production_gate")
VIDEO = load("video_job")


def write(path: Path, value: bytes) -> Path:
    path.write_bytes(value)
    return path


class ProductionGateTests(unittest.TestCase):
    def approval(self, root: Path, continuity: str = "chain") -> Path:
        files = {
            "contract": write(
                root / "contract.yaml",
                f"subject_count: 1\nclip_continuity: {continuity}\n".encode(),
            ),
            "first_frame": write(root / "first.png", b"first"),
            "last_frame": write(root / "last.png", b"last"),
            "video": write(root / "pilot.mp4", b"video"),
            "page_evidence": write(root / "page.png", b"page"),
        }
        output = root / "approval.json"
        GATE.create_pilot_approval(
            Namespace(
                **files,
                identity_bible=None,
                reviewer="visual-review",
                notes="passed",
                decision="pass",
                output=output,
                force=False,
            )
        )
        return output

    def test_pilot_approval_detects_changed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approval = self.approval(root)

            GATE.validate_pilot_approval(approval)
            (root / "page.png").write_bytes(b"changed")

            with self.assertRaisesRegex(ValueError, "批准失效"):
                GATE.validate_pilot_approval(approval)

    def test_contract_continuity_requires_unique_top_level_value(self) -> None:
        invalid_contracts = {
            "nested": "metadata:\n  clip_continuity: independent\n",
            "duplicate": (
                "clip_continuity: chain\n"
                "clip_continuity: independent\n"
            ),
            "string": 'notes: "clip_continuity: independent"\n',
            "comment": "# clip_continuity: independent\nsubject_count: 1\n",
            "missing": "subject_count: 1\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in invalid_contracts.items():
                with self.subTest(name=name):
                    path = root / f"{name}.yaml"
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        GATE.contract_continuity_mode(path)

            valid = root / "valid.yaml"
            valid.write_text(
                "subject_count: 1\nclip_continuity: chain # required\n",
                encoding="utf-8",
            )
            self.assertEqual(GATE.contract_continuity_mode(valid), "chain")

    def test_frame_chain_records_exact_hash_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = write(root / "tail.png", b"same-frame")
            current = write(root / "first.png", b"same-frame")
            manifest = root / "frame-chain.json"

            link = GATE.verify_frame_chain(previous, current, 2, manifest)

            self.assertTrue(link["exactSha256Match"])
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["links"][0]["segmentIndex"], 2)

    def test_frame_chain_rejects_modified_next_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = write(root / "tail.png", b"tail")
            current = write(root / "first.png", b"not-tail")

            with self.assertRaisesRegex(ValueError, "连续帧链断裂"):
                GATE.verify_frame_chain(previous, current, 2)

    def test_video_production_requires_pilot_approval(self) -> None:
        args = Namespace(
            stage="production",
            segment_index=2,
            pilot_approval=None,
            continuity_mode="independent",
            previous_tail=None,
            first_frame=None,
            frame_chain_manifest=None,
        )

        with self.assertRaisesRegex(ValueError, "pilot-approval"):
            VIDEO.validate_production_gate(args)

    def test_video_chain_requires_exact_previous_tail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approval = self.approval(root)
            previous = write(root / "tail.png", b"tail")
            current = write(root / "next.png", b"different")
            args = Namespace(
                stage="production",
                segment_index=2,
                pilot_approval=approval,
                continuity_mode="chain",
                previous_tail=previous,
                first_frame=current,
                frame_chain_manifest=root / "frame-chain.json",
            )

            with self.assertRaisesRegex(ValueError, "连续帧链断裂"):
                VIDEO.validate_production_gate(args)

    def test_continuous_contract_rejects_independent_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approval = self.approval(root, "chain")
            args = Namespace(
                stage="production",
                segment_index=2,
                pilot_approval=approval,
                continuity_mode="independent",
                previous_tail=None,
                first_frame=None,
                frame_chain_manifest=None,
            )

            with self.assertRaisesRegex(ValueError, "合同要求 chain"):
                VIDEO.validate_production_gate(args)

    def test_independent_contract_allows_independent_production(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approval = self.approval(root, "independent")
            args = Namespace(
                stage="production",
                segment_index=2,
                pilot_approval=approval,
                continuity_mode="independent",
                previous_tail=None,
                first_frame=None,
                frame_chain_manifest=None,
            )

            result = VIDEO.validate_production_gate(args)

            self.assertEqual(result["continuityMode"], "independent")


if __name__ == "__main__":
    unittest.main()
