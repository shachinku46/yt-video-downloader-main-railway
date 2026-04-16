from flask import Flask, render_template, request, jsonify, send_from_directory
import yt_dlp
import os
import uuid
import threading

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

progress_data = {}

# ✅ No fixed path (Render compatible)
FFMPEG_PATH = None


# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("index.html")


# ---------------- VIDEO INFO ----------------
@app.route("/info")
def info():
    url = request.args.get("url")

    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            data = ydl.extract_info(url, download=False)

        return jsonify({
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "uploader": data.get("uploader"),
            "duration": data.get("duration_string")
        })

    except Exception as e:
        return jsonify({"error": str(e)})


# ---------------- DOWNLOAD TASK ----------------
def download_task(url, file_id, format_type, quality):

    def hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').replace(' ', '')
            speed = d.get('_speed_str', '')

            progress_data[file_id] = {
                "percent": percent,
                "speed": speed
            }

        elif d['status'] == 'finished':
            progress_data[file_id] = {
                "percent": "99%",
                "speed": "Processing..."
            }

    def post_hook(d):
        if d['status'] == 'finished':
            progress_data[file_id] = {
                "percent": "100%",
                "speed": "Completed"
            }

    try:
        if format_type == "mp3":
            ydl_opts = {
                'format': 'bestaudio/best/best',
                'outtmpl': f'{DOWNLOAD_FOLDER}/{file_id}.%(ext)s',

                # 🔥 Anti-block headers
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'Accept-Language': 'en-US,en;q=0.9',
                },

                # 🔥 Retry system
                'retries': 10,
                'fragment_retries': 10,

                # 🔥 Delay (avoid block)
                'sleep_interval': 2,
                'max_sleep_interval': 5,

                # 🔥 Cookie support (optional)
                'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,

                'progress_hooks': [hook],
                'postprocessor_hooks': [post_hook],

                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            }
        else:
            if quality == "max":
                fmt = "bestvideo+bestaudio/best"
            else:
                fmt = f"bestvideo[height<={quality}]+bestaudio/best"

            ydl_opts = {
                'format': fmt,
                'outtmpl': f'{DOWNLOAD_FOLDER}/{file_id}.%(ext)s',

                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                },

                'retries': 10,
                'fragment_retries': 10,

                'progress_hooks': [hook],
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    except Exception as e:
        error_msg = str(e)

        if "Sign in to confirm you're not a bot" in error_msg:
            error_msg = "⚠️ YouTube blocked this request. Try again later or use cookies."

        progress_data[file_id] = {
            "percent": "error",
            "speed": error_msg
        }


# ---------------- START DOWNLOAD ----------------
@app.route("/download", methods=["POST"])
def download():
    data = request.json

    url = data.get("url")
    format_type = data.get("type")
    quality = data.get("quality")

    file_id = str(uuid.uuid4())

    progress_data[file_id] = {"percent": "0%", "speed": ""}

    threading.Thread(target=download_task, args=(url, file_id, format_type, quality)).start()

    return jsonify({"id": file_id})


# ---------------- PROGRESS ----------------
@app.route("/progress/<file_id>")
def progress(file_id):
    return jsonify(progress_data.get(file_id, {"percent": "0%", "speed": ""}))


# ---------------- DOWNLOAD FILE ----------------
@app.route("/file/<file_id>")
def file(file_id):
    for f in os.listdir(DOWNLOAD_FOLDER):
        if f.startswith(file_id):
            return send_from_directory(DOWNLOAD_FOLDER, f, as_attachment=True)
    return "File not found"


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
