from flask import Flask, render_template, jsonify, request, send_file, Response
import os
import urllib.parse
import mimetypes  
import subprocess
import time
import psutil 
import threading
import atexit
import sqlite3
import hashlib
from waitress import serve

app = Flask(__name__)

VIDEO_FOLDER = r'J\\Channels'      # CHANGE IT TO YOUR DOWNLOAD LOCATION!!!
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watched_videos.db")
SKIP_LAST_VIEWED = True

files_to_delete = []
files_in_use = set()

def create_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watched_videos (
            video_hash TEXT PRIMARY KEY
        )
    """)

    conn.commit()
    conn.close()

def generate_video_hash(file_path):
    filesize = os.path.getsize(file_path)
    filename = os.path.basename(file_path)
    hash_input = f"{filename}_{filesize}".encode('utf-8')
    return hashlib.md5(hash_input).hexdigest()

def mark_video_as_watched(filename):
    """Mark a video as watched by inserting its hash into the database."""
    video_hash = generate_video_hash(filename)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO watched_videos (video_hash) VALUES (?)', (video_hash,))
    conn.commit()
    conn.close()

@app.route('/update_file_list')
def update_file_list():
    videos = get_video_files()
    return jsonify(videos)

def get_watched_videos():
    """Retrieve the list of watched video hashes."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT video_hash FROM watched_videos')
    watched_videos = [row[0].strip() for row in cursor.fetchall()]
    conn.close()
    return watched_videos

def get_video_files():
    """Retrieve all video files from the folder and subfolders, excluding watched videos."""
    video_files = []
    if SKIP_LAST_VIEWED:
        watched_videos = get_watched_videos()
    else:
        watched_videos = []
    for root, dirs, files in os.walk(VIDEO_FOLDER):
        for file in files:
            if not file.endswith((
                '.mp4', '.avi', '.mov', '.webm', '.flv', '.wmv', 
                '.mpg', '.mpeg', '.3gp', '.ogg'
            )):
                continue
            full_path = os.path.abspath(os.path.join(root, file))
            video_hash = generate_video_hash(full_path)
            if video_hash in watched_videos:
                continue
            video_files.append(full_path)
    return video_files

@app.route('/')
def index():
    """Render the video page."""
    videos = get_video_files()
    encoded_videos = [urllib.parse.quote(video) for video in videos]
    video_types = {}
    for video in videos:
        mime_type, _ = mimetypes.guess_type(video)
        if mime_type is None: 
            mime_type = 'application/octet-stream'
        video_types[video] = mime_type
    return render_template('index.html', videos=encoded_videos, video_types=video_types)

@app.route('/video/<path:filename>')
def stream_video(filename):
    filename = urllib.parse.unquote(filename)
    print(f"Get /video {filename}")
    video_path = os.path.join(VIDEO_FOLDER, filename)
    if not os.path.exists(video_path):
        return "Video not found", 404
    files_in_use.add(video_path)
    mark_video_as_watched(filename)
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type is None:
        mime_type = 'application/octet-stream'
    response = send_file(video_path, mimetype=mime_type)
    files_in_use.remove(video_path)
    threading.Timer(0, attempt_deletion).start()
    return response

def attempt_deletion():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for video_path in files_to_delete[:]:
        if video_path not in files_in_use:
            try:
                video_hash = generate_video_hash(video_path)
                if os.path.exists(video_path):
                    os.remove(video_path)
                    print(f"Deleted {video_path}")
                    cursor.execute("DELETE FROM watched_videos WHERE video_hash = ?", (video_hash,))
                    conn.commit()
                    print(f"Removed video hash {video_hash} from database")
                files_to_delete.remove(video_path)
            except Exception as e:
                print(f"Error deleting {video_path}: {str(e)}")
    conn.close()

@app.route('/delete', methods=['POST'])
def delete_video():
    video_path = request.json.get('video')
    if video_path:
        try:
            decoded_path = urllib.parse.unquote(video_path)
            full_path = os.path.join(decoded_path)
            if os.path.exists(full_path):
                files_to_delete.append(full_path)
                return jsonify({"status": "success", "message": "Video marked for deletion"})
            else:
                return jsonify({"status": "error", "message": "File not found"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    return jsonify({"status": "error", "message": "No video specified"})

create_db()

def shutdown_cleanup():
    print("App shutting down, attempting to clean up files.")
    attempt_deletion()

atexit.register(shutdown_cleanup)

if __name__ == '__main__':

    serve(app, host='127.0.0.1', port=5000)

