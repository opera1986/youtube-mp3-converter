from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import threading
import uuid
import json
import time
import ssl

# SSL certificate bypass
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

app = Flask(__name__)
CORS(app)

# Use a local directory for downloads to work on both local and cloud (Render)
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

jobs = {}

def run_download(job_id, url):
    def progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            percent = round((downloaded / total) * 100, 1) if total > 0 else 0
            jobs[job_id].update({
                'status': 'downloading',
                'percent': percent,
                'speed': d.get('_speed_str', '').strip(),
                'eta': d.get('_eta_str', '').strip(),
            })
        elif d['status'] == 'finished':
            jobs[job_id].update({'status': 'converting', 'percent': 100})

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
        'nocheckcertificate': True,
        'quiet': True,
        'no_warnings': True,
        'cachedir': False,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Change extension to mp3 as it was post-processed
            mp3_filename = os.path.splitext(os.path.basename(filename))[0] + '.mp3'
            jobs[job_id].update({
                'status': 'done', 
                'title': info.get('title', ''),
                'filename': mp3_filename
            })
    except Exception as e:
        print(f"Error downloading: {str(e)}")
        jobs[job_id].update({'status': 'error', 'error': str(e)})


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    url = data.get('url', '').strip() if data else ''
    if not url:
        return jsonify({'error': 'URL을 입력해주세요'}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'starting', 'percent': 0, 'title': '', 'error': '', 'speed': '', 'eta': ''}

    thread = threading.Thread(target=run_download, args=(job_id, url), daemon=True)
    thread.start()

    return jsonify({'job_id': job_id})


@app.route('/progress/<job_id>')
def progress(job_id):
    def generate():
        while True:
            job = jobs.get(job_id)
            if not job:
                yield f"data: {json.dumps({'status': 'error', 'error': '작업을 찾을 수 없습니다'})}\n\n"
                break
            
            yield f"data: {json.dumps(job)}\n\n"
            
            if job['status'] in ('done', 'error'):
                # Wait a bit so frontend can catch the 'done' state
                time.sleep(2)
                # We don't pop here yet, or we'll lose the filename for the download link
                break
            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port, threaded=True)
