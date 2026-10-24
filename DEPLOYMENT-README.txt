PinDrop deployment notes

1. Runtime: Python
2. Framework: Flask
3. Startup command (if the host asks for one):
   gunicorn --bind 0.0.0.0:$PORT app:app
4. Dependencies are listed in requirements.txt.
5. FFmpeg is not bundled in this ZIP. Confirm that the host provides FFmpeg or lets you install it.
6. After deployment, test /api/health and try a public Pinterest video Pin.
7. This app is intended for public Pins you are allowed to download. Do not use it to bypass private content or access controls.

Security note:
- Keep .env files, credentials, and private tokens out of GitHub.
- Free hosting may sleep, limit runtime, or remove temporary files. Large downloads may fail depending on host limits.
