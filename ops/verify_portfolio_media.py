"""Independent quality gate for genuine portfolio browser evidence.

Checks the exact files produced by Playwright; never generates replacement imagery.
Designed to fail if there is an incomplete/mislabeled archive, duplicate screens,
mismatched SHA, corrupt/low-resolution PNG, static video, or codec/duration drift.
"""
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_SCENES = {
    "iphone-15": ("today", "media", "events", "community", "me"),
    "ipad": ("today", "media", "events"),
    "desktop": ("today", "media", "events", "community", "me"),
}
VIEWPORT_WIDTH = {"iphone-15": 390, "ipad": 820, "desktop": 1440}
EXPECTED_VIDEOS = {
    "live": ("desktop-journey-25s.mp4", "iphone-journey-25s.mp4"),
    "preview": (
        "desktop-journey-25s.mp4",
        "iphone-journey-25s.mp4",
        "iphone-personal-demo-25s.mp4",
    ),
}


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def safe_path(root, name):
    check(isinstance(name, str) and name, "asset missing relative path")
    check(not Path(name).is_absolute(), "absolute asset path forbidden")
    check(".." not in Path(name).parts, "parent traversal forbidden")
    path = (root / name).resolve()
    check(path.is_relative_to(root.resolve()), "asset outside archive")
    check(path.is_file() and not path.is_symlink(), "asset absent/symlink: " + name)
    return path


def screenshot_ok(path, width):
    with path.open("rb") as fh:
        header = fh.read(24)
    check(header[:8] == b"\x89PNG\r\n\x1a\n", "not PNG: " + path.name)
    check(header[12:16] == b"IHDR", "invalid PNG IHDR: " + path.name)
    w, h = struct.unpack(">II", header[16:24])
    check(w == width, "screenshot width mismatch %s (%s, expected %s)" %
          (path.name, w, width))
    check(h >= 540, "unexpectedly short screenshot %s height=%s" % (path.name, h))
    check(h <= 30000, "unexpectedly tall screenshot " + path.name)
    check(path.stat().st_size >= 6000, "screenshot unexpectedly small " + path.name)
    return {"width": w, "height": h}


def run_json(args):
    out = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, check=True, timeout=45)
    return json.loads(out.stdout)


def frames_differ(video):
    tool = shutil.which("ffmpeg")
    check(tool is not None, "ffmpeg is required for non-static video inspection")
    fingerprints = []
    for second in (2, 11, 20):
        proc = subprocess.run(
            [tool, "-hide_banner", "-loglevel", "error", "-ss", str(second),
             "-i", str(video), "-frames:v", "1", "-f", "image2pipe",
             "-vcodec", "png", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=40,
        )
        check(len(proc.stdout) > 1000, "failed to sample video frame " + video.name)
        fingerprints.append(hashlib.sha256(proc.stdout).hexdigest())
    check(len(set(fingerprints)) > 1, "video has no observable scene changes: " + video.name)


def video_ok(path, expected_width):
    tool = shutil.which("ffprobe")
    check(tool is not None, "ffprobe is required for MP4 inspection")
    info = run_json([tool, "-v", "error", "-show_streams", "-show_format",
                     "-of", "json", str(path)])
    streams = info.get("streams") or []
    video_streams = [x for x in streams if x.get("codec_type") == "video"]
    audio_streams = [x for x in streams if x.get("codec_type") == "audio"]
    check(len(video_streams) == 1, "expected one video stream: " + path.name)
    check(not audio_streams, "unreviewed audio track is forbidden: " + path.name)
    video = video_streams[0]
    check(video.get("codec_name") == "h264", "MP4 must use H.264: " + path.name)
    check(video.get("pix_fmt") == "yuv420p", "mobile-safe pixel format missing")
    check(video.get("width") == expected_width, "MP4 width mismatch " + path.name)
    height = int(video.get("height", 0))
    check(height >= 600, "MP4 height unexpected " + path.name)
    seconds = float(info.get("format", {}).get("duration", 0))
    check(24.2 <= seconds <= 25.1, "MP4 duration unexpected %s %.3fs" %
          (path.name, seconds))
    check(path.stat().st_size >= 100000, "MP4 unexpectedly small " + path.name)
    frames_differ(path)
    return {"width": expected_width, "height": height, "duration_seconds": round(seconds, 3)}


def validate_archive(root, source, sha):
    manifest_path = root / "manifest.json"
    check(manifest_path.is_file(), "missing manifest.json")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    check(source in EXPECTED_VIDEOS, "unknown source")
    check(data.get("completed") is True, "incomplete capture: " + str(data.get("error")))
    check(data.get("source") == source, "archive source mismatch")
    check(data.get("production_claim") is False, "unproven production claim")
    check(data.get("published_endpoint_capture") == (source == "live"),
          "published capture flag mismatch")
    check(re.fullmatch(r"[0-9a-f]{40}", data.get("repository_sha", "")) is not None,
          "invalid commit SHA")
    check(data.get("repository_sha") == sha, "source commit SHA mismatch")
    health = data.get("health") or {}
    check(health.get("ok") is True and health.get("app"), "server health not confirmed")
    if source == "preview":
        check(health.get("git_commit") == sha, "preview runtime SHA mismatch")
        check(health.get("backend") == "sqlite", "demo must use isolated SQLite")
        check(health.get("demo_seed") is True, "preview must use demo data")
        check(health.get("durable") is False, "preview cannot be production database")
        check(not data.get("live_sha_verified"), "preview marked as public")
    else:
        check(str(data.get("source_url", "")).startswith("https://"),
              "public capture must use HTTPS")
        expected_live = health.get("git_commit") == sha
        check(data.get("live_sha_verified") == expected_live,
              "incorrect live revision verification")
    items = data.get("assets") or []
    check(len(items) == len({item["file"] for item in items}),
          "duplicate asset paths")
    paths = []
    checked = []
    for item in items:
        file = safe_path(root, item.get("file"))
        check(file.stat().st_size == item.get("bytes"), "file byte count mismatch: " + file.name)
        check(digest(file) == item.get("sha256"), "SHA256 mismatch: " + file.name)
        check(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None, "invalid asset SHA")
        kind = item.get("type")
        check(kind in ("browser-screenshot", "browser-video"), "unapproved asset type")
        if kind == "browser-screenshot":
            check(file.suffix == ".png", "non-PNG screenshot")
            device = item.get("device")
            check(device in VIEWPORT_WIDTH, "unexpected screenshot device")
            attributes = screenshot_ok(file, VIEWPORT_WIDTH[device])
        else:
            check(file.suffix == ".mp4", "non-MP4 video")
            check(file.name in EXPECTED_VIDEOS[source], "unapproved video scene")
            check(bool(item.get("demo_only")) == file.name.startswith("iphone-personal-demo"),
                  "demo video incorrectly marked")
            attributes = video_ok(file, 1440 if file.name.startswith("desktop-") else 390)
        checked.append({"file": item["file"], **attributes})
        paths.append(item["file"])
    required_photos = {
        "screenshots/" + device + "-" + scene + ".png"
        for device, scenes in EXPECTED_SCENES.items() for scene in scenes
    }
    if source == "preview":
        required_photos.add("screenshots/iphone-personal-demo.png")
    expected_paths = required_photos | {"videos/" + name for name in EXPECTED_VIDEOS[source]}
    check(set(paths) == expected_paths,
          "missing or unexpected media: " + str(sorted(expected_paths ^ set(paths))))
    photo_hashes = [item["sha256"] for item in items if item["type"] == "browser-screenshot"]
    check(len(set(photo_hashes)) >= 5, "screenshots do not vary between scenes")

    gallery = root / "index.html"
    check(gallery.is_file() and gallery.stat().st_size > 1000, "missing media gallery")
    gallery_text = gallery.read_text(encoding="utf-8")
    for rel in paths:
        check(rel in gallery_text, "gallery omits " + rel)
    if source == "live":
        check(str(health.get("git_commit", "missing")) in gallery_text,
              "published Git SHA omitted from gallery")
        check("ПУБЛИЧНО" in gallery_text, "gallery missing published revision disclosure")
    else:
        check("ТЕСТОВАЯ" in gallery_text, "preview gallery lacks test label")
    return data, checked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--source", choices=("preview", "live"), required=True)
    ap.add_argument("--sha", required=True)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    data, inspected = validate_archive(root, args.source, args.sha)
    data["quality_gate"] = {
        "passed": True,
        "validated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checked_assets": len(inspected),
        "video_count": sum(x["file"].endswith(".mp4") for x in inspected),
        "screenshot_count": sum(x["file"].endswith(".png") for x in inspected),
        "checks": [
            "source-and-SHA", "all-files-present", "checksum", "PNG-dimensions",
            "H264-yuv420p", "video-25s", "non-static-video", "gallery-coverage",
            "live-vs-preview-labels",
        ],
    }
    (root / "manifest.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"passed": True, "source": args.source,
                      "assets": len(inspected),
                      "sha": args.sha}, ensure_ascii=False))


if __name__ == "__main__":
    main()
