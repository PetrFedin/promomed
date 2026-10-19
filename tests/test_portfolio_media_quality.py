"""Adversarial QA for portable, real-browser media archives."""
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from ops import verify_portfolio_media as media


def chunk(kind, data):
    value = kind + data
    return (struct.pack(">I", len(data)) + value
            + struct.pack(">I", zlib.crc32(value) & 0xffffffff))


def genuine_png(width=390, height=540):
    """Produce a real RGB PNG using only the Python standard library."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    scanlines = b"".join(b"\x00" + os.urandom(width * 3) for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(scanlines))
            + chunk(b"IEND", b""))


class ArchiveIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "screenshots").mkdir()
        self.real = self.root / "screenshots" / "genuine.png"
        self.real.write_bytes(genuine_png())

    def test_normal_file_passes_archive_boundary(self):
        self.assertEqual(media.safe_path(self.root, "screenshots/genuine.png"),
                         self.real.resolve())

    def test_absolute_parent_and_outside_paths_are_rejected(self):
        for name in (str(self.real), "../outside.png", "screenshots/../../etc/passwd"):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                media.safe_path(self.root, name)

    def test_symlinked_file_and_parent_directory_fail_closed(self):
        (self.root / "screenshots" / "alias.png").symlink_to(self.real)
        (self.root / "aliases").symlink_to(self.root / "screenshots", target_is_directory=True)
        for name in ("screenshots/alias.png", "aliases/genuine.png"):
            with self.subTest(name=name), self.assertRaisesRegex(
                AssertionError, "symlink"
            ):
                media.safe_path(self.root, name)

    def test_real_png_is_decodable_and_has_correct_geometry(self):
        actual = media.screenshot_ok(self.real, 390)
        self.assertEqual(actual, {"width": 390, "height": 540})

    def test_forged_header_incomplete_stream_and_modified_crc_rejected(self):
        original = self.real.read_bytes()
        invalid_header_only = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR"
                               + struct.pack(">II", 390, 540) + b"\x00" * 7000)
        corrupted = bytearray(original)
        corrupted[-1] ^= 1
        for payload in (invalid_header_only, original[:120], bytes(corrupted)):
            self.real.write_bytes(payload)
            with self.subTest(size=len(payload)), self.assertRaises(AssertionError):
                media.screenshot_ok(self.real, 390)

    def test_reject_video_with_wrong_height_even_if_codec_duration_match(self):
        video = self.root / "iphone-journey-25s.mp4"
        video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 100001)
        details = {
            "streams": [{
                "codec_type": "video", "codec_name": "h264",
                "pix_fmt": "yuv420p", "width": 390, "height": 600,
            }],
            "format": {"duration": "25.000"},
        }
        with patch.object(media, "run_json", return_value=details), patch.object(
            media.shutil, "which", return_value="ffprobe"
        ), patch.object(media, "frames_differ"):
            with self.assertRaisesRegex(AssertionError, "viewport height"):
                media.video_ok(video, 390)
            details["streams"][0]["height"] = 844
            result = media.video_ok(video, 390)
            self.assertEqual(result["height"], 844)

    def test_non_mp4_container_rejected_before_ffprobe(self):
        video = self.root / "bad.mp4"
        video.write_bytes(b"not-mp4-data")
        with self.assertRaisesRegex(AssertionError, "MP4 container"):
            media.video_ok(video, 390)


if __name__ == "__main__":
    unittest.main()
