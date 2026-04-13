"""Download videos from X CDN, extract WebP thumbnails, compress MP4."""

from __future__ import annotations

import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MEDIA_DIR = ROOT / "web" / "public" / "media"
THUMBS_DIR = MEDIA_DIR / "thumbs"
VIDEOS_DIR = MEDIA_DIR / "videos"

_FFMPEG = shutil.which("ffmpeg")


def _ensure_dirs() -> None:
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


def _download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://x.com/",
        })
        with urllib.request.urlopen(req, timeout=60) as r, dest.open("wb") as f:
            shutil.copyfileobj(r, f)
        return dest.stat().st_size > 1024
    except Exception as exc:  # noqa: BLE001
        print(f"  media: download failed {url[:80]}… → {exc}", flush=True)
        dest.unlink(missing_ok=True)
        return False


def _extract_thumb(video: Path, thumb: Path) -> bool:
    """Extract first frame as WebP, scaled to 640px wide."""
    if not _FFMPEG:
        return False
    try:
        r = subprocess.run(
            [
                _FFMPEG, "-y", "-i", str(video),
                "-vframes", "1",
                "-vf", "scale=640:-2",
                "-quality", "82",
                str(thumb),
            ],
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        print(f"  media: ffmpeg thumbnail timed out for {video.name}", flush=True)
        thumb.unlink(missing_ok=True)
        return False
    return r.returncode == 0 and thumb.exists()


def _compress_video(src: Path, dest: Path) -> bool:
    """Re-encode to H.264 720p with faststart for streaming."""
    if not _FFMPEG:
        shutil.copy2(src, dest)
        return True
    try:
        r = subprocess.run(
            [
                _FFMPEG, "-y", "-i", str(src),
                "-c:v", "libx264", "-crf", "28",
                "-preset", "fast",
                "-vf", "scale='min(720,iw)':-2",
                "-c:a", "aac", "-b:a", "96k",
                "-movflags", "+faststart",
                "-t", "15",
                str(dest),
            ],
            capture_output=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print(f"  media: ffmpeg compress timed out for {src.name}", flush=True)
        dest.unlink(missing_ok=True)
        return False
    return r.returncode == 0 and dest.exists()


def process_video(
    tweet_id: str, video_url: str
) -> dict[str, str | None]:
    """Download, thumbnail, compress. Returns paths relative to web/public/."""
    _ensure_dirs()

    clean_id = tweet_id.replace("x:", "")
    thumb_rel = f"media/thumbs/{clean_id}.webp"
    video_rel = f"media/videos/{clean_id}.mp4"
    thumb_path = ROOT / "web" / "public" / thumb_rel
    video_path = ROOT / "web" / "public" / video_rel

    if thumb_path.exists() and video_path.exists():
        return {"thumbnail": thumb_rel, "video": video_rel}

    tmp = VIDEOS_DIR / f"{clean_id}_raw.mp4"
    try:
        if not _download(video_url, tmp):
            return {"thumbnail": None, "video": None}

        thumb_ok = _extract_thumb(tmp, thumb_path)
        video_ok = _compress_video(tmp, video_path)

        return {
            "thumbnail": thumb_rel if thumb_ok else None,
            "video": video_rel if video_ok else None,
        }
    finally:
        tmp.unlink(missing_ok=True)


def process_prompts_media(
    prompts: list[dict[str, Any]], *, force: bool = False
) -> int:
    """Process video media for prompts that have a video_url but no media yet."""
    count = 0
    to_process = []
    for p in prompts:
        url = p.get("video_url")
        if not url:
            continue
        if not force and p.get("thumbnail") and p.get("video"):
            continue
        to_process.append(p)

    if not to_process:
        return 0

    print(f"Media: processing {len(to_process)} videos…", flush=True)
    for i, p in enumerate(to_process):
        result = process_video(p["id"], p["video_url"])
        if result["thumbnail"]:
            p["thumbnail"] = result["thumbnail"]
        if result["video"]:
            p["video"] = result["video"]
        count += 1
        if (i + 1) % 10 == 0:
            print(f"  … {i + 1}/{len(to_process)}", flush=True)

    print(f"Media: done — {count} videos processed.", flush=True)
    return count
