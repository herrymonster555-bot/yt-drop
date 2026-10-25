import os
import re
import uuid
import threading
import mimetypes
import time
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, jsonify, request, send_file, render_template
import yt_dlp

APP_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = APP_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
    "youtu.be", "www.youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com"
}
JOBS = {}
LOCK = threading.Lock()


def cleanup_job_files(job_id):
    """Remove all final and intermediate files created for one download job."""
    if not job_id:
        return
    for path in DOWNLOAD_DIR.glob(f"{job_id}.*"):
        try:
            if path.is_file():
                path.unlink(missing_ok=True)
        except OSError:
            app.logger.warning("Could not remove temporary file: %s", path, exc_info=True)


def cleanup_stale_downloads(max_age_seconds=2 * 60 * 60):
    """Remove abandoned temporary files older than two hours, including .part files."""
    cutoff = time.time() - max_age_seconds
    try:
        for path in DOWNLOAD_DIR.iterdir():
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:
                app.logger.warning("Could not remove stale temporary file: %s", path, exc_info=True)
    except OSError:
        app.logger.warning("Could not scan temporary download directory.", exc_info=True)


# Clean up files left behind by interrupted downloads when the app starts.
cleanup_stale_downloads()


def validate_youtube_url(raw_url):
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise ValueError("Paste a YouTube video link first.")
    raw_url = raw_url.strip()
    if not raw_url.startswith(("https://", "http://")):
        raw_url = "https://" + raw_url
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or host not in ALLOWED_HOSTS:
        raise ValueError("Please enter a valid YouTube link (youtube.com or youtu.be).")
    if parsed.username or parsed.password:
        raise ValueError("This URL is not supported.")
    return raw_url


# YouTube extractor config to bypass "Failed to extract any player response" on cloud IPs.
# Try multiple player clients in order of reliability for server-side extraction.
YT_PLAYER_CLIENTS = ["android", "web", "mweb", "tv_embedded"]

# Realistic desktop Chrome user agent; YouTube serves player response more reliably to known browsers.
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def ydl_options(outtmpl=None, download=False, player_clients=None):
    """Return yt-dlp options tuned for YouTube on cloud hosts.

    player_clients: list of client names to try (default: YT_PLAYER_CLIENTS).
    """
    clients = player_clients or YT_PLAYER_CLIENTS
    opts = {
        "quiet": True,
        "no_warnings": False,  # Keep warnings for diagnostics
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 3,
        "extractor_retries": 3,
        "skip_download": not download,
        "restrictfilenames": True,
        "http_headers": {"User-Agent": DEFAULT_UA, "Accept-Language": "en-US,en;q=0.9"},
        "extractor_args": {
            "youtube": {
                "player_client": clients,
                "player_skip": ["configs", "webpage"],
                "skip": ["dash", "hls"],  # Let yt-dlp pick best; dash/hls sometimes fail on cloud
            }
        },
    }
    if outtmpl:
        opts["outtmpl"] = outtmpl
    return opts


def make_download_filename(title, filepath):
    """Return a useful filename and ensure the extension appears exactly once."""
    suffix = filepath.suffix.lower()
    if not suffix:
        suffix = ".mp4"

    # Keep filenames portable across Windows/macOS/Linux and strip trailing dots/spaces.
    raw_title = str(title or "")
    safe_title = re.sub(r"[^A-Za-z0-9._ -]+", "", raw_title)
    safe_title = re.sub(r"\s+", " ", safe_title).strip(" ._-")

    # Some titles contain only emoji/non-ASCII characters; use a stable fallback name.
    if not safe_title or safe_title.lower() in {"mp4", "video", "media"}:
        safe_title = "yt-drop-video"

    # Remove an extension already present in the title to avoid name.mp4.mp4.
    if suffix and safe_title.lower().endswith(suffix):
        safe_title = safe_title[:-len(suffix)].rstrip(" ._-")
    if not safe_title:
        safe_title = "yt-drop-video"

    safe_title = safe_title[:90].rstrip(" ._-") or "yt-drop-video"
    return f"{safe_title}{suffix}"


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/diagnose")
def diagnose():
    """Diagnostic endpoint: checks yt-dlp version, FFmpeg, and tests a quick extraction."""
    import subprocess
    import shutil

    ytdlp_version = "unknown"
    try:
        import yt_dlp
        ytdlp_version = yt_dlp.version.__version__
    except Exception:
        pass

    ffmpeg_path = shutil.which("ffmpeg")
    ffmpeg_version = "not found"
    if ffmpeg_path:
        try:
            result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=5)
            ffmpeg_version = result.stdout.split("\n")[0] if result.stdout else "unknown"
        except Exception:
            ffmpeg_version = "error getting version"

    # Quick test extraction (no download) on a known-public video
    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" - first YouTube video
    test_result = {"ok": False, "error": None}
    try:
        with yt_dlp.YoutubeDL(ydl_options()) as ydl:
            info = ydl.extract_info(test_url, download=False)
        test_result = {"ok": True, "title": info.get("title"), "id": info.get("id")}
    except Exception as e:
        test_result = {"ok": False, "error": str(e)}

    return jsonify({
        "yt_dlp_version": ytdlp_version,
        "ffmpeg": {"path": ffmpeg_path, "version": ffmpeg_version},
        "test_extraction": test_result,
        "python_version": subprocess.run(["python", "--version"], capture_output=True, text=True).stdout.strip(),
        "player_clients_tried": YT_PLAYER_CLIENTS,
    })


def _is_player_response_error(exc: Exception) -> bool:
    """Detect YouTube's 'Failed to extract any player response' error."""
    msg = str(exc).lower()
    return "player response" in msg or "extract any player" in msg


def _friendly_youtube_error(exc: Exception) -> str:
    """Return a user-friendly error message for common YouTube/yt-dlp failures."""
    msg = str(exc).lower()
    if "player response" in msg or "extract any player" in msg:
        return (
            "YouTube blocked this request from our server. This happens on cloud hosts. "
            "Try a different video, or try again later — YouTube may unblock the IP."
        )
    if "private" in msg or "unavailable" in msg:
        return "This video is private, deleted, or unavailable."
    if "age" in msg and "restrict" in msg:
        return "This video is age-restricted and cannot be downloaded without authentication."
    if "region" in msg or "geo" in msg or "country" in msg:
        return "This video is not available in your region."
    if "live" in msg:
        return "Live streams cannot be downloaded while they are live."
    if "copyright" in msg or "drm" in msg or "protected" in msg:
        return "This video is protected by copyright or DRM and cannot be downloaded."
    if "sign in" in msg or "login" in msg or "auth" in msg:
        return "This video requires sign-in and cannot be accessed."
    return "We couldn't access this video. It may be private, unavailable, age-restricted, or unsupported. Try another public YouTube video."


@app.post("/api/resolve")
def resolve():
    data = request.get_json(silent=True) or {}
    try:
        url = validate_youtube_url(data.get("url", ""))
        with yt_dlp.YoutubeDL(ydl_options()) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("No media was found for this Pin.")
        formats = info.get("formats") or []
        media_url = info.get("url")
        # Advertise only heights that yt-dlp actually found for this video.
        heights = sorted({
            int(f.get("height")) for f in formats
            if f.get("height") and f.get("vcodec") not in (None, "none")
        })
        mp4_heights = sorted({
            int(f.get("height")) for f in formats
            if f.get("height") and f.get("vcodec") not in (None, "none")
            and f.get("ext") == "mp4"
        })
        # We deliberately let yt-dlp handle downloading rather than exposing source URLs.
        return jsonify({
            "ok": True,
            "id": str(info.get("id") or ""),
            "title": info.get("title") or "YouTube video",
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "media_type": "video" if (info.get("duration") or heights) else "media",
            "formats_available": bool(formats or media_url),
            "available_heights": heights,
            "available_mp4_heights": mp4_heights,
            "message": "Media found. Choose a quality available for this video."
        })
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        app.logger.exception("YouTube resolve failed: %s", e)
        return jsonify({"ok": False, "error": _friendly_youtube_error(e)}), 422


def run_download_job(job_id, url, media_format, quality, bitrate):
    """Run yt-dlp in a worker and publish real progress for the UI to poll."""
    outtmpl = str(DOWNLOAD_DIR / f"{job_id}.%(ext)s")
    filepath = None

    def update_job(**updates):
        with LOCK:
            if job_id in JOBS:
                JOBS[job_id].update(updates)

    def progress_hook(data):
        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes") or 0
            # Downloading accounts for 5–90%; reserve the final section for post-processing.
            percent = 5 + (min(100.0, downloaded * 100.0 / total) * 0.85 if total else 0)
            update_job(percent=round(percent, 1), stage="Downloading media", state="running",
                       speed=data.get("_speed_str") or "", eta=data.get("_eta_str") or "")
        elif status == "finished":
            update_job(percent=91, stage="Processing and preparing file", state="processing", speed="", eta="")

    try:
        options = ydl_options(outtmpl=outtmpl, download=True)
        options["progress_hooks"] = [progress_hook]
        options["postprocessor_hooks"] = [lambda data: update_job(percent=95, stage="Finalizing media", state="processing")]
        if media_format == "mp3":
            options.update({
                "format": "bestaudio/best",
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": bitrate}],
            })
        else:
            if quality == "best":
                selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            else:
                height = int(quality)
                selector = (f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                            f"bestvideo[height<={height}]+bestaudio/"
                            f"best[height<={height}][ext=mp4]/best[height<={height}]")
            options.update({"format": selector, "merge_output_format": "mp4"})

        update_job(state="running", percent=2, stage="Connecting to YouTube", title="Preparing your download")
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            prepared_path = Path(ydl.prepare_filename(info))
            if media_format == "mp3":
                prepared_path = prepared_path.with_suffix(".mp3")
        filepath = prepared_path
        if not filepath.exists():
            matches = list(DOWNLOAD_DIR.glob(f"{job_id}.*"))
            if matches:
                filepath = matches[0]
        if not filepath.exists() or not filepath.is_file():
            raise RuntimeError("The media download did not produce a file.")
        filename = make_download_filename(info.get("title"), filepath)
        with LOCK:
            JOBS[job_id].update(state="complete", percent=100, stage="Download ready", filename=filename,
                                filepath=str(filepath), filesize=filepath.stat().st_size, title=info.get("title") or filename)
    except Exception as exc:
        app.logger.exception("YT Drop job %s failed", job_id)
        cleanup_job_files(job_id)
        with LOCK:
            if job_id in JOBS:
                JOBS[job_id].update(state="error", stage="Download failed", error=_friendly_youtube_error(exc))


@app.post("/api/download")
def download():
    data = request.get_json(silent=True) or {}
    try:
        url = validate_youtube_url(data.get("url", ""))
        cleanup_stale_downloads()
        media_format = str(data.get("format", "mp4")).lower()
        if media_format not in {"mp4", "mp3"}:
            raise ValueError("Choose MP4 video or MP3 audio.")
        quality = str(data.get("quality", "best")).lower()
        bitrate = str(data.get("bitrate", "192"))
        if media_format == "mp3" and bitrate not in {"320", "256", "192", "128", "96", "64"}:
            raise ValueError("Choose a supported MP3 bitrate: 320, 256, 192, 128, 96, or 64 kbps.")
        if media_format == "mp4" and quality != "best":
            if not quality.isdigit() or int(quality) not in {240, 360, 480, 720, 1080, 1440, 2160, 4320}:
                raise ValueError("Choose a valid video quality.")
        job_id = uuid.uuid4().hex
        with LOCK:
            JOBS[job_id] = {"state": "queued", "percent": 1, "stage": "Starting download", "created": time.time()}
        thread = threading.Thread(target=run_download_job, args=(job_id, url, media_format, quality, bitrate), daemon=True)
        thread.start()
        return jsonify({"ok": True, "job_id": job_id})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.get("/api/progress/<job_id>")
def download_progress(job_id):
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"ok": False, "error": "Download job not found or expired."}), 404
        public = {key: value for key, value in job.items() if key not in {"filepath", "created"}}
    return jsonify({"ok": True, **public})


@app.get("/api/file/<job_id>")
def download_file(job_id):
    with LOCK:
        job = JOBS.get(job_id)
        if not job or job.get("state") != "complete" or not job.get("filepath"):
            return jsonify({"ok": False, "error": "The download is not ready yet."}), 404
        filepath = Path(job["filepath"])
        filename = job.get("filename") or filepath.name
    if not filepath.is_file():
        return jsonify({"ok": False, "error": "The prepared file is no longer available. Please try again."}), 404
    response = send_file(filepath, as_attachment=True, download_name=filename,
                         mimetype=mimetypes.guess_type(filename)[0] or "application/octet-stream")
    @response.call_on_close
    def cleanup():
        cleanup_job_files(job_id)
        with LOCK:
            JOBS.pop(job_id, None)
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
