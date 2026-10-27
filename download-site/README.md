# YT Drop Download Website

A standalone animated Flask landing page for the Windows installer. It is designed to deploy as a **new Render service**, separate from the existing downloader website.

## Deploy to Render
1. Open Render and choose **New → Web Service**.
2. Connect `herrymonster555-bot/yt-drop`.
3. Select branch `windows-download-site`.
4. Set **Root Directory** to `download-site`.
5. Build command: `pip install -r requirements.txt`
6. Start command: `gunicorn app:app`
7. Deploy. The `/health` route returns the health status.

## Windows installer
The installer is intentionally not committed to the repository because it is about 108 MB. Upload `YT-Drop-Setup.exe` as an asset to a GitHub Release in this repository, named exactly `YT-Drop-Setup.exe`. The download button redirects to:

`https://github.com/herrymonster555-bot/yt-drop/releases/latest/download/YT-Drop-Setup.exe`

Until that release asset exists, the download button will not provide the installer. This page's animated progress card is a visual demo, not a live download meter.

## Local run
From this directory: `pip install -r requirements.txt` then `python app.py`. Open `http://127.0.0.1:10000`.
