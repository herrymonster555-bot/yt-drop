# YT Drop

YT Drop is a Flask + yt-dlp web app for downloading publicly accessible YouTube media as MP4 video or MP3 audio when available. It includes a responsive dark interface, animated UI, custom SVG logo and favicon.

## Run locally (Windows)

1. Install Python 3.10+ and FFmpeg. Ensure `ffmpeg` is available on your PATH.
2. In PowerShell, open this folder and run:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python app.py
   ```
3. Visit `http://127.0.0.1:5000`.

FFmpeg is needed for MP3 audio extraction and may be needed for merging video/audio streams. The included Dockerfile installs FFmpeg for container deployments.

## API

- `GET /api/health` — health check
- `POST /api/resolve` — resolves supported YouTube media metadata; JSON body: `{"url":"https://www.youtube.com/watch?v=..."}`
- `POST /api/download` — downloads media; JSON body: `{"url":"https://youtu.be/...","format":"mp4"}` or `format` set to `mp3`.

## Notes

- Only use media you own or have permission to download, and comply with YouTube's terms and applicable copyright law. This project does not bypass private access or DRM restrictions.
- Availability depends on YouTube, yt-dlp, video restrictions, network access, and the hosting provider. Downloads are not guaranteed to work for every video.
- Temporary downloads are cleaned up after responses close; stale files are swept periodically.
- This is an independent project and is not affiliated with YouTube or Google.

## Live download progress UI

The downloader now runs each download as a background job and exposes progress through `/api/progress/<job_id>`. The UI polls this endpoint and animates a circular percentage indicator, progress bar, current stage, speed, and ETA when yt-dlp provides them. Percentages come from yt-dlp's actual download hook; during connection/setup or post-processing, the UI shows the current stage rather than pretending those phases have precise byte progress. Completed files are served by `/api/file/<job_id>` and temporary files are cleaned after the response closes.
