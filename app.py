from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import threading
import uuid
import json
import time
import ssl
import logging
from logging.handlers import RotatingFileHandler

# SSL certificate bypass
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

app = Flask(__name__)
CORS(app)

# Configure Logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
logging.basicConfig(level=logging.INFO)
handler = RotatingFileHandler(log_file, maxBytes=200000, backupCount=1)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
app.logger.addHandler(handler)

# Use a local directory for downloads
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

jobs = {}

class YdlLogger:
    def debug(self, msg):
        if not msg.startswith('[debug] '):
            app.logger.info(f"[yt-dlp] {msg}")
    def info(self, msg):
        app.logger.info(f"[yt-dlp] {msg}")
    def warning(self, msg):
        app.logger.warning(f"[yt-dlp] {msg}")
    def error(self, msg):
        app.logger.error(f"[yt-dlp] {msg}")

@app.route('/debug')
def debug_info():
    import subprocess
    try:
        node_v = subprocess.check_output(['node', '-v'], stderr=subprocess.STDOUT).decode().strip()
    except:
        node_v = "Not Found"
    
    try:
        yt_dlp_v = subprocess.check_output(['yt-dlp', '--version'], stderr=subprocess.STDOUT).decode().strip()
    except:
        try:
            import yt_dlp
            yt_dlp_v = yt_dlp.version.__version__
        except:
            yt_dlp_v = "Not Found"
            
    return jsonify({
        'node_version': node_v,
        'yt_dlp_version': yt_dlp_v,
        'os': os.name,
        'cwd': os.getcwd(),
        'cookies_exist': os.path.exists('cookies.txt')
    })

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
        'quiet': False,
        'no_warnings': False,
        'cachedir': False,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'logger': YdlLogger(),
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'web_embedded'],
                'skip': ['hls', 'dash']
            }
        },
    }

    try:
        app.logger.info(f"Starting job {job_id} for URL: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            mp3_filename = os.path.splitext(os.path.basename(filename))[0] + '.mp3'
            jobs[job_id].update({
                'status': 'done', 
                'title': info.get('title', ''),
                'filename': mp3_filename
            })
            app.logger.info(f"Job {job_id} completed successfully")
    except Exception as e:
        error_msg = str(e)
        app.logger.error(f"Job {job_id} failed: {error_msg}")
        jobs[job_id].update({'status': 'error', 'error': error_msg})


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/logs')
def get_logs():
    if not os.path.exists(log_file):
        return "No logs found."
    with open(log_file, 'r') as f:
        return Response(f.read(), mimetype='text/plain')

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
                time.sleep(2)
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
