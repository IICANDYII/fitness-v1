import importlib.util
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("pipeline_under_test", HERE / "sd_video_pipeline.py")
pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = pipeline
SPEC.loader.exec_module(pipeline)


def make_artifacts(day: Path) -> None:
    processed = day / "processed"
    audio = day / "audio"
    processed.mkdir(parents=True)
    audio.mkdir(parents=True)
    (processed / "preprocess_complete.json").write_text(
        json.dumps({"complete": True}), encoding="utf-8")
    with zipfile.ZipFile(processed / "frames_low.zip", "w") as zf:
        zf.writestr("frame.jpg", b"frame")
    (audio / "clip.wav").write_bytes(b"audio")


class PipelineSafetyTests(unittest.TestCase):
    def test_incomplete_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            day = Path(td)
            (day / "processed").mkdir()
            (day / "audio").mkdir()
            (day / "processed" / "preprocess_complete.json").write_text("{}", encoding="utf-8")
            (day / "audio" / "clip.wav").write_bytes(b"audio")
            ok, why = pipeline._validate_artifacts(str(day))
            self.assertFalse(ok)
            self.assertIn("frames_low.zip", why)

    def test_complete_artifacts_are_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            day = Path(td)
            make_artifacts(day)
            self.assertEqual((True, "ok"), pipeline._validate_artifacts(str(day)))

    def test_atomic_copy_preserves_existing_destination_on_failure(self):
        class FailingLimiter:
            def acquire(self, _n):
                raise OSError("simulated interruption")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src, dst = root / "src.bin", root / "dst.bin"
            src.write_bytes(b"new content")
            dst.write_bytes(b"old content")
            with self.assertRaises(OSError):
                pipeline._throttled_copy(str(src), str(dst), FailingLimiter())
            self.assertEqual(b"old content", dst.read_bytes())
            self.assertFalse(list(root.glob("dst.bin.part.*")))

    def test_same_size_corruption_is_repaired(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src_dir, dst_dir = root / "src", root / "dst"
            src_dir.mkdir()
            dst_dir.mkdir()
            (src_dir / "item.bin").write_bytes(b"correct")
            (dst_dir / "item.bin").write_bytes(b"broken!")
            ok = pipeline._upload_tree(
                str(src_dir), str(dst_dir), ["item.bin"], pipeline._RateLimiter(0))
            self.assertTrue(ok)
            self.assertEqual(b"correct", (dst_dir / "item.bin").read_bytes())

    def test_local_video_keeps_relative_path_and_refuses_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nas = root / "nas"
            nas.mkdir()
            local = root / "local.avi"
            local.write_bytes(b"new video")
            old_nas = pipeline.NAS_ROOT
            pipeline.NAS_ROOT = str(nas)
            try:
                self.assertTrue(pipeline.upload_local_video_to_nas(
                    str(local), "alice", "20260720", pipeline._RateLimiter(0),
                    relative_path=os.path.join("camera_a", "clip.avi")))
                dest = nas / "alice" / "20260720" / "video" / "camera_a" / "clip.avi"
                self.assertEqual(b"new video", dest.read_bytes())

                local.write_bytes(b"different")
                self.assertFalse(pipeline.upload_local_video_to_nas(
                    str(local), "alice", "20260720", pipeline._RateLimiter(0),
                    relative_path=os.path.join("camera_a", "clip.avi")))
                self.assertEqual(b"new video", dest.read_bytes())
            finally:
                pipeline.NAS_ROOT = old_nas

    def test_upload_day_rejects_non_nas_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nas, local = root / "nas", root / "local"
            nas.mkdir()
            make_artifacts(local)
            old_nas = pipeline.NAS_ROOT
            pipeline.NAS_ROOT = str(nas)
            try:
                day = pipeline.LogicalDay("alice", "20260720", [])
                self.assertFalse(pipeline.upload_day(day, str(local)))
            finally:
                pipeline.NAS_ROOT = old_nas

    def test_legacy_local_artifacts_are_really_uploaded_to_nas(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nas, local = root / "nas", root / "local"
            nas.mkdir()
            make_artifacts(local)
            old_nas = pipeline.NAS_ROOT
            pipeline.NAS_ROOT = str(nas)
            try:
                self.assertTrue(pipeline.upload_local_artifacts_to_nas(
                    str(local), "alice", "20260720"))
                nas_day = nas / "alice" / "20260720"
                self.assertEqual((True, "ok"), pipeline._validate_artifacts(str(nas_day)))
                self.assertEqual(
                    (local / "processed" / "frames_low.zip").read_bytes(),
                    (nas_day / "processed" / "frames_low.zip").read_bytes())
            finally:
                pipeline.NAS_ROOT = old_nas

    def test_low_rate_limiter_can_hold_one_copy_chunk(self):
        limiter = pipeline._RateLimiter(1)
        self.assertGreaterEqual(limiter.burst, 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
