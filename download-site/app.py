from flask import Flask, render_template, redirect
import os

app = Flask(__name__)

# Upload YT-Drop-Setup.exe as an asset on a GitHub Release.
# This stable URL will work once the release asset exists.
INSTALLER_URL = "https://github.com/herrymonster555-bot/yt-drop/releases/latest/download/YT-Drop-Setup.exe"

@app.get("/")
def home():
    return render_template("index.html", version="1.0.0", size_mb=108)

@app.get("/download/windows")
def download_windows():
    return redirect(INSTALLER_URL, code=302)

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
