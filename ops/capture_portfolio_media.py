"""Capture versioned, genuine browser evidence of SOSTOYANIE.

Public mode never authenticates. Preview mode uses only seeded CI demo accounts.
A screenshot/video is accepted only when the app, navigation and source health pass.
Never interpret these assets as proof of a production PostgreSQL rollout.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright

SCENES = ("today", "media", "events", "community", "me")
DEVICES = (
    ("iphone-15", 390, 844, ("today", "media", "events", "community", "me")),
    ("ipad", 820, 1180, ("today", "media", "events")),
    ("desktop", 1440, 900, ("today", "media", "events", "community", "me")),
)
VIDEO_SCENES = ("today", "media", "events", "community", "me")
VIDEO_DURATION = 25.0


def probe(url: str, attempts: int = 4) -> dict:
    errors = []
    for index in range(attempts):
        try:
            with urlopen(Request(url + "/health", headers={"User-Agent": "Promomed-Portfolio-Evidence/1.0"}), timeout=30) as res:
                if res.status != 200:
                    raise RuntimeError("unexpected health HTTP " + str(res.status))
                raw = res.read(16384)
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, dict) or data.get("ok") is not True:
                    raise RuntimeError("health payload did not confirm app")
                return data
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            errors.append(type(exc).__name__ + ": " + str(exc)[:160])
            if index + 1 < attempts:
                time.sleep((10, 15, 20)[index])
    raise RuntimeError("live health unavailable after retries: " + " / ".join(errors))


def goto_public(page, base):
    response = page.goto(base + "/", wait_until="domcontentloaded", timeout=45000)
    if response is None or response.status != 200:
        raise RuntimeError("public landing HTTP is not 200")
    page.locator("#today.on").wait_for(timeout=20000)
    if not page.locator('#nav button[data-s="today"]').count():
        raise RuntimeError("required navigation missing")


def choose(page, scene):
    if scene != "today":
        button = page.locator('#nav button[data-s="' + scene + '"]')
        button.click(timeout=12000)
        page.locator("#" + scene + ".on").wait_for(timeout=10000)
    else:
        page.locator('#nav button[data-s="today"]').click(timeout=12000)
        page.locator("#today.on").wait_for(timeout=10000)
    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    page.wait_for_timeout(350)


def sha256(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            hasher.update(block)
    return hasher.hexdigest()


def metadata(path, root, kind, **more):
    info = {"file": str(path.relative_to(root)).replace(os.sep, "/"), "type": kind,
            "bytes": path.stat().st_size, "sha256": sha256(path)}
    info.update(more)
    return info


def transcode(webm, target, out):
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe are required to publish MP4")
    subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(webm),
                    "-t", str(VIDEO_DURATION), "-an", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "22",
                    "-movflags", "+faststart", str(target)], check=True, timeout=160)
    check = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(target)],
                           text=True, capture_output=True, check=True)
    duration = float(check.stdout.strip())
    if not (24.2 <= duration <= 25.1):
        raise RuntimeError("MP4 duration is not 25 seconds: " + str(duration))
    if target.stat().st_size < 10000:
        raise RuntimeError("Video too small to be credible evidence")
    return metadata(target, out, "browser-video", duration_seconds=round(duration, 3))


def photos(browser, base, root, assets):
    for name, width, height, scenes in DEVICES:
        context = browser.new_context(viewport={"width": width, "height": height},
                                      locale="ru-RU", device_scale_factor=1,
                                      reduced_motion="reduce")
        page = context.new_page()
        problems = []
        page.on("pageerror", lambda err: problems.append(str(err)))
        try:
            goto_public(page, base)
            for scene in scenes:
                choose(page, scene)
                filename = root / "screenshots" / (name + "-" + scene + ".png")
                page.screenshot(path=str(filename), full_page=True, animations="disabled")
                assets.append(metadata(filename, root, "browser-screenshot",
                                       device=name, viewport={"width": width, "height": height},
                                       scene=scene))
            if problems:
                raise RuntimeError(name + " JavaScript errors: " + " / ".join(problems[:3]))
        finally:
            context.close()


def film_public(browser, base, root, name, width, height, assets):
    with tempfile.TemporaryDirectory() as temp:
        context = browser.new_context(viewport={"width": width, "height": height},
                                      locale="ru-RU", device_scale_factor=1,
                                      record_video_dir=temp,
                                      record_video_size={"width": width, "height": height})
        page = context.new_page()
        try:
            goto_public(page, base)
            for scene in VIDEO_SCENES:
                choose(page, scene)
                page.wait_for_timeout(5100)
            recording = page.video
            page.close()
        finally:
            context.close()
        if recording is None:
            raise RuntimeError("Playwright did not create a recording")
        target = root / "videos" / (name + "-journey-25s.mp4")
        assets.append(transcode(recording.path(), target, root))


def preview_account(browser, base, root, assets):
    # This path runs only against a fresh, isolated seeded CI SQLite database.
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="ru-RU",
                              device_scale_factor=1)
    page = ctx.new_page()
    try:
        response = page.goto(base + "/personal/", wait_until="domcontentloaded", timeout=45000)
        if response is None or response.status != 200:
            raise RuntimeError("personal workspace unavailable")
        page.locator("#email").fill("participant@demo.ru")
        page.locator("#password").fill("demo2027")
        page.locator("#login-button").click(timeout=12000)
        page.locator("#workspace").wait_for(state="visible", timeout=20000)
        path = root / "screenshots" / "iphone-personal-demo.png"
        page.screenshot(path=str(path), full_page=True, animations="disabled")
        assets.append(metadata(path, root, "browser-screenshot", device="iphone-15",
                               scene="personal-signed-in-demo-only"))
    finally:
        ctx.close()


def gallery(root, assets, source, sha, stamp):
    images = [v for v in assets if v["type"] == "browser-screenshot"]
    videos = [v for v in assets if v["type"] == "browser-video"]
    from html import escape
    images_html = "".join("<figure><img loading='lazy' src='" + escape(x["file"], quote=True) +
                          "'><figcaption>" + escape(x.get("device", "")) + " · " +
                          escape(x.get("scene", "")) + "</figcaption></figure>" for x in images)
    videos_html = "".join("<figure><video controls playsinline preload='metadata' src='" +
                          escape(x["file"], quote=True) + "'></video><figcaption>" +
                          escape(x["file"]) + "</figcaption></figure>" for x in videos)
    title = "PUBLISHED WEB" if source == "live" else "CI PREVIEW · NOT PRODUCTION"
    html = ("<!doctype html><html lang='ru'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>СОСТОЯНИЕ — доказательства интерфейса</title>"
            "<style>body{font:16px/1.5 system-ui;background:#071b31;color:#f4f7fb;margin:0;padding:4vw}"
            "h1{font-size:clamp(26px,4vw,54px)}p{max-width:850px}section{margin:55px 0}"
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,310px),1fr));gap:26px}"
            "figure{margin:0;background:#102f54;padding:12px;border-radius:18px}"
            "img,video{display:block;width:100%;max-height:650px;object-fit:contain;border-radius:10px}"
            "figcaption{padding:10px;font-size:14px;color:#c8d9ea}</style><h1>СОСТОЯНИЕ</h1>"
            "<p>" + title + " · " + escape(stamp) + " · SHA " + escape(sha[:12]) + "</p>"
            "<p>Кадры записаны Playwright из браузера. Для публикации на лендинге проверяйте "
            "источник, лицензию медиа и отсутствие персональных данных.</p>"
            "<section><h2>Видео · 25 секунд</h2><div class='grid'>" + videos_html +
            "</div></section><section><h2>Скриншоты</h2><div class='grid'>" + images_html +
            "</div></section></html>")
    (root / "index.html").write_text(html, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--source", choices=("preview", "live"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sha", required=True)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    output = Path(args.out).resolve()
    (output / "screenshots").mkdir(parents=True, exist_ok=True)
    (output / "videos").mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {"product": "SOSTOYANIE / Promomed",
                "captured_at_utc": stamp, "source": args.source,
                "source_url": base, "repository_sha": args.sha,
                "production_claim": args.source == "live",
                "completed": False, "assets": []}
    try:
        health = probe(base)
        manifest["health"] = {key: health.get(key) for key in
                              ("app", "git_commit", "backend", "durable", "demo_seed", "ok")}
        if args.source == "preview" and health.get("git_commit") != args.sha:
            raise RuntimeError("preview health SHA did not match checked-out code")
        manifest["live_sha_verified"] = args.source == "live" and health.get("git_commit") == args.sha
        if args.source == "live" and manifest["health"]["git_commit"] in (None, "local"):
            manifest["live_sha_verified"] = False
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                photos(browser, base, output, manifest["assets"])
                film_public(browser, base, output, "desktop", 1440, 900, manifest["assets"])
                film_public(browser, base, output, "iphone", 390, 844, manifest["assets"])
                if args.source == "preview":
                    preview_account(browser, base, output, manifest["assets"])
            finally:
                browser.close()
        manifest["completed"] = True
        gallery(output, manifest["assets"], args.source, args.sha, stamp)
        print(json.dumps({"ok": True, "source": args.source,
                          "screenshots": sum(a["type"] == "browser-screenshot" for a in manifest["assets"]),
                          "videos": sum(a["type"] == "browser-video" for a in manifest["assets"]),
                          "sha": args.sha, "live_sha_verified": manifest.get("live_sha_verified")}))
    except Exception as exc:
        manifest["error"] = type(exc).__name__ + ": " + str(exc)[:500]
        print(json.dumps({"ok": False, "error": manifest["error"]}))
        raise
    finally:
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                               encoding="utf-8")


if __name__ == "__main__":
    main()
