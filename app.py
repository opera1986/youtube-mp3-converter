from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import yt_dlp
import os
import threading
import uuid
import json
import time
import ssl

# SSL certificate bypass for certain environments where certs are missing
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = os.path.expanduser('~/Downloads')
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
        'nocheckcertificate': True,  # Bypass SSL issues
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            jobs[job_id].update({'status': 'done', 'title': info.get('title', '')})
    except Exception as e:
        print(f"Error downloading: {str(e)}")
        jobs[job_id].update({'status': 'error', 'error': str(e)})


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    if not data:
        return jsonify({'error': 'JSON 데이터가 필요합니다'}), 400
        
    url = data.get('url', '').strip()
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
            
            data = json.dumps(job)
            yield f"data: {data}\n\n"
            
            if job['status'] in ('done', 'error'):
                # Give frontend a moment to receive 'done' or 'error' before cleanup
                time.sleep(1)
                jobs.pop(job_id, None)
                break
            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"서버 시작! 브라우저에서 http://127.0.0.1:{port} 을 열어주세요")
    app.run(debug=True, host='0.0.0.0', port=port, threaded=True)
