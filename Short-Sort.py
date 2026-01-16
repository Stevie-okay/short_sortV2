from flask import Flask, render_template, jsonify, request, send_file
import os
import urllib.parse
import mimetypes  
import threading
import atexit
import sqlite3
import hashlib
from waitress import serve

app = Flask(__name__)

############################
############################

VIDEO_FOLDER = r'J:\channels'      # CHANGE IT TO YOUR DOWNLOAD LOCATION!!!

############################
############################

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watched_videos.db")
SKIP_LAST_VIEWED = True

files_to_delete = []
files_in_use = set()
deletionsCounter = 0;

def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        return conn
    except sqlite3.Error as e:
        print(f"Failed to connect to the database: {e}")
        return None

def close_connection(conn):
    if conn and isinstance(conn, sqlite3.Connection):
        try:
            conn.close()
        except sqlite3.Error as e:
            print(f"Error closing database connection: {e}")
    else:
        print("No valid database connection to close.")

def create_db():
    conn = get_connection()
    if not conn:
        print("Database connection failed. (create_db)")
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watched_videos (
                video_hash TEXT PRIMARY KEY
            )
        """)
        conn.commit()
        print("Database Table 'watched_videos' created successfully.")
    except sqlite3.Error as e:
        print("Error creating table: {e}")
    finally:
        close_connection(conn) 

def get_watched_videos():
    conn = get_connection()
    if not conn:
        print("Database connection failed. (get_watched_videos)")
        return
    cursor = conn.cursor()
    cursor.execute('SELECT video_hash FROM watched_videos')
    watched_videos = [row[0].strip() for row in cursor.fetchall()]
    close_connection(conn)
    return watched_videos    

@app.route('/update_file_list')
def update_file_list():
    videos = get_video_files()
    return jsonify(videos)
    
def generate_video_hash(file_path):
    try:
        stat_info = os.stat(file_path)
        filename = os.path.basename(file_path)
        filesize = stat_info.st_size
        filemodtime = stat_info.st_mtime
        hash_input = f"{filename}_{filesize}_{filemodtime}".encode('utf-8')
        return hashlib.md5(hash_input).hexdigest()
    except (FileNotFoundError, OSError) as e:
        print(f"Error generating hash for {file_path}: as {e}")
    except UnicodeEncodeError as e:
        print(f"Unicode encoding error for {file_path}: {e}")
        return None

def get_video_files():
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
            try:
                full_path = os.path.abspath(os.path.join(root, file))
            except (TypeError, ValueError) as e:
                print(f"Invalid path: {root}/{file} - {e}")
                continue
            video_hash = generate_video_hash(full_path)
            if video_hash is None:
                print(f"Could not create hash for {full_path}")
                continue
            if video_hash in watched_videos:
                continue
            video_files.append(full_path)
    return video_files

def mark_video_as_watched(video_path):
    video_hash = generate_video_hash(video_path)
    if video_hash is None:
        print(f"Could not generate hash for {video_path}")
        return
    conn = get_connection()
    if not conn:
        print("Database connection failed. (mark_video_as_watched)")
        return
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT OR IGNORE INTO watched_videos (video_hash) VALUES (?)', (video_hash,))
        conn.commit()
    except Exception as e:
        print(f"Error marking video as watched: {e}")
        conn.rollback()
    finally:
        close_connection(conn)

@app.route('/video/<path:filename>')
def stream_video(filename):
    try:
        filename = urllib.parse.unquote(filename)
        if '..' in filename or filename.startswith('/'):
            return jsonify({"error": "Invalid filename"}), 400
        video_path = os.path.join(VIDEO_FOLDER, filename)
        if not os.path.isfile(video_path):
            return jsonify({"error": "Video not found"}), 404
        files_in_use.add(video_path)
        try:
            mark_video_as_watched(video_path)
        except Exception as e:
            print(f"Failed to mark video as watched: {e}")
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        response = send_file(video_path, mimetype=mime_type)
        threading.Timer(0, attempt_deletion).start()
        return response
    except Exception as e:
        print(f"Error in stream_video: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        try:
            files_in_use.discard(video_path)
        except Exception as e:
            print(f"Failed to remove video from files_in_use: {e}")   

def attempt_deletion():
    global deletionsCounter
    conn = None
    try:
        conn = get_connection()
        if not conn:
            print("Database connection failed. (attempt_deletion)")
            return
        cursor = conn.cursor()
        for video_path in list(files_to_delete):
            if video_path not in files_in_use:
                try:
                    video_hash = generate_video_hash(video_path)
                    if video_hash is None:
                        print(f"Could not generate hash for {video_path}")
                        continue
                    if os.path.exists(video_path):
                        os.remove(video_path)
                        cursor.execute("DELETE FROM watched_videos WHERE video_hash = ?", (video_hash,))
                        conn.commit()
                        print(f"Deleted {video_path}, Removed video hash {video_hash} from database")
                        deletionsCounter += 1
                    files_to_delete.remove(video_path)
                except Exception as e:
                    print(f"Error deleting {video_path}: {str(e)}")
                    conn.rollback()
    except Exception as e:
        print(f"Unexpected error in attempt_deletion: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            close_connection(conn)

@app.route('/')
def index():
    try:
        videos = get_video_files()
    except Exception as e:
        print(f"Error retrieving video files: {e}")
        videos = []
    encoded_videos = [urllib.parse.quote(video) for video in videos]
    video_types = {}
    for video in videos:
        try:
            mime_type, _ = mimetypes.guess_type(video)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            video_types[video] = mime_type
        except Exception as e:
            print(f"Error determining MIME type for {video}: {e}")
            video_types[video] = 'application/octet-stream'
    return render_template('index.html', videos=encoded_videos, video_types=video_types)

@app.route('/delete', methods=['POST'])
def delete_video():
    try:
        video_path = request.json.get('video')
        if not video_path:
            print("No video specified in the request.")
            return jsonify({"status": "error", "message": "No video specified"})
        decoded_path = urllib.parse.unquote(video_path)
        full_path = os.path.join(decoded_path)
        if not os.path.exists(full_path):
            print(f"File not found: {full_path}")
            return jsonify({"status": "error", "message": "File not found"})
        if not full_path.startswith(VIDEO_FOLDER):
            print("Attempted to delete file outside of allowed directory.")
            return jsonify({"status": "error", "message": "Invalid file path"})
        files_to_delete.append(full_path)
        return jsonify({"status": "success", "message": "Video marked for deletion"})
    except Exception as e:
        print(f"Error during video deletion: {e}")
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    create_db()
    def shutdown_cleanup():
        print("App shutting down, attempting to clean up files.")
        attempt_deletion()
        print(f"Total Deletion in this Session {deletionsCounter}")
    atexit.register(shutdown_cleanup)
    serve(app, host='127.0.0.1', port=5000)
