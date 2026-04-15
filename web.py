import os
import time
import threading
import tempfile
from datetime import datetime

import cv2
from flask import Flask, Response, render_template_string, jsonify, send_file

from codec import SteamicDecoder



PAGE_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SteamIC project</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0a0a23; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace; }
  header { background: #16213e; padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #1a508b; }
  header h1 { font-size: 20px; color: #fff; }
  header h1 span { color: #e94560; }
  nav { align-items: center; justify-content: center; display: flex; gap: 12px; }
  nav button { background: #0f3460; color: #fff; border: none; padding: 8px 18px; border-radius: 4px; cursor: pointer; font-size: 13px; }
  nav button:hover { background: #1a508b; }
  nav button.active { background: #e94560; }



  .container { max-width: 1100px; margin: 20px auto; padding: 0 20px; }

  /* ── Camera Page ── */
  #camera-page .video-box { background: #1a1a2e; border-radius: 6px; overflow: hidden; text-align: center; }
  #camera-page .video-box img { width: 100%; max-height: 70vh; object-fit: contain; display: block; margin: 0 auto; }
  #camera-page .video-box .no-feed { color: #666; padding: 120px 20px; font-size: 16px; }
  .status-bar { margin-top: 12px; display: flex; gap: 20px; align-items: center; padding: 10px 16px; background: #16213e; border-radius: 4px; }
  .status-bar .indicator { width: 10px; height: 10px; border-radius: 50%; }
  .status-bar .indicator.monitoring { background: #0f0; }
  .status-bar .indicator.recording { background: #f00; animation: pulse 1s infinite; }
  @keyframes pulse { 50% { opacity: 0.4; } }
  .status-bar .label { font-size: 14px; font-weight: 600; }
  .status-bar .detail { font-size: 13px; color: #aaa; }

  /* ── Viewer Page ── */
  #viewer-page { display: none; }
  .clip-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; max-height: 180px; overflow-y: auto; padding: 10px; background: #16213e; border-radius: 6px; }
  .clip-list .clip-item { background: #0f3460; padding: 8px 14px; border-radius: 4px; cursor: pointer; display: flex; justify-content: space-between; font-size: 13px; }
  .clip-list .clip-item:hover { background: #1a508b; }
  .clip-list .clip-item.active { background: #e94560; }
  .clip-list .empty { color: #666; text-align: center; padding: 20px; }

  .player-box { background: #1a1a2e; border-radius: 6px; overflow: hidden; text-align: center; min-height: 360px; display: flex; align-items: center; justify-content: center; }
  .player-box video { max-width: 100%; max-height: 65vh; background: #000; }
  .player-box .placeholder { color: #666; font-size: 16px; }

  .player-controls { margin-top: 12px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .player-controls button { background: #0f3460; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
  .player-controls button:hover { background: #1a508b; }
  .player-controls button:disabled { background: #333; color: #666; cursor: default; }
  .player-controls input[type=range] { flex: 1; accent-color: #e94560; }
  .player-controls select { background: #0f3460; color: #fff; border: none; padding: 6px 10px; border-radius: 4px; }
  .player-controls .time-info { font-family: monospace; font-size: 13px; color: #aaa; min-width: 120px; text-align: right; }

  .file-info { margin-top: 12px; display: flex; gap: 16px; flex-wrap: wrap; padding: 10px 16px; background: #16213e; border-radius: 4px; font-size: 12px; color: #aaa; }
  .file-info span b { color: #e0e0e0; }

  .decompress-status { color: #e94560; font-size: 13px; margin-top: 8px; min-height: 20px; }
</style>
</head>
<body>
<header>
  <nav>
    <button id="nav-camera" class="active" onclick="showPage('camera')">Camera</button>
    <button id="nav-viewer" onclick="showPage('viewer')">Viewer</button>
  </nav>
</header>

<!-- Camera Page -->
<div id="camera-page" class="container">
  <div class="video-box">
    <img id="live-feed" src="/video_feed" alt="Live Feed" onerror="this.style.display='none'; document.getElementById('no-feed').style.display='block';">
    <div id="no-feed" class="no-feed" style="display:none;">Camera feed not available. Make sure the camera is running.</div>
  </div>
</div>

<!-- Viewer Page -->
<div id="viewer-page" class="container">
  <h3 style="margin-bottom: 10px; font-size: 15px;">Recorded Clips</h3>
  <div id="clip-list" class="clip-list"><div class="empty">No clips found</div></div>

  <div class="player-box">
    <video id="player-video" style="display:none;"></video>
    <div id="player-placeholder" class="placeholder">Select a clip to play</div>
  </div>

  <div id="decompress-status" class="decompress-status"></div>

  <div class="player-controls">
    <button id="btn-play" onclick="togglePlay()" disabled>&#9654; Play</button>
    <button id="btn-stop" onclick="stopPlayback()" disabled>&#9632; Stop</button>
    <button id="btn-prev" onclick="stepFrame(-1)" disabled>&lt;</button>
    <button id="btn-next" onclick="stepFrame(1)" disabled>&gt;</button>
    <input type="range" id="seek-bar" min="0" max="1000" value="0" step="1" oninput="seekTo(this.value)" disabled>
    <select id="speed-select" onchange="setSpeed(this.value)">
      <option value="0.25">0.25x</option>
      <option value="0.5">0.5x</option>
      <option value="1" selected>1x</option>
      <option value="2">2x</option>
      <option value="4">4x</option>
    </select>
    <span id="time-info" class="time-info">--:-- / --:--</span>
  </div>

  <div id="file-info" class="file-info"></div>
</div>

<script>
// ── Page switching ──
function showPage(page) {
  document.getElementById('camera-page').style.display = page === 'camera' ? 'block' : 'none';
  document.getElementById('viewer-page').style.display = page === 'viewer' ? 'block' : 'none';
  document.getElementById('nav-camera').classList.toggle('active', page === 'camera');
  document.getElementById('nav-viewer').classList.toggle('active', page === 'viewer');
  if (page === 'viewer') loadClipList();
}

// ── Camera status polling ──
setInterval(async () => {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const ind = document.getElementById('status-indicator');
    document.getElementById('status-label').textContent = d.status;
    ind.className = 'indicator ' + (d.recording ? 'recording' : 'monitoring');
    let details = [];
    if (d.faces > 0) details.push(d.faces + ' face' + (d.faces > 1 ? 's' : ''));
    if (d.vehicles > 0) details.push(d.vehicles + ' vehicle' + (d.vehicles > 1 ? 's' : ''));
    document.getElementById('status-detail').textContent = details.length ? details.join(', ') + ' detected' : '';
  } catch(e) {}
}, 500);

// ── Viewer ──
let clipFps = 30;
let seeking = false;

const video = document.getElementById('player-video');

video.addEventListener('timeupdate', () => {
  if (!seeking && video.duration) {
    document.getElementById('seek-bar').value = (video.currentTime / video.duration * 1000) | 0;
    updateTimeDisplay();
  }
});

video.addEventListener('ended', () => {
  document.getElementById('btn-play').innerHTML = '&#9654; Play';
});

function updateTimeDisplay() {
  const cur = formatTime(video.currentTime);
  const dur = formatTime(video.duration || 0);
  document.getElementById('time-info').textContent = cur + ' / ' + dur;
}

function formatTime(s) {
  const m = (s / 60) | 0;
  const sec = (s % 60).toFixed(1);
  return m + ':' + (sec < 10 ? '0' : '') + sec;
}

async function loadClipList() {
  const r = await fetch('/api/clips');
  const clips = await r.json();
  const list = document.getElementById('clip-list');
  if (clips.length === 0) {
    list.innerHTML = '<div class="empty">No clips found</div>';
    return;
  }
  list.innerHTML = clips.map(c =>
    `<div class="clip-item" onclick="loadClip('${c.name}')" data-name="${c.name}">
      <span>${c.name}</span><span>${c.size}</span>
    </div>`
  ).join('');
}

async function loadClip(name) {
  stopPlayback();
  const status = document.getElementById('decompress-status');
  status.textContent = 'Decompressing...';

  document.getElementById('player-placeholder').style.display = 'block';
  document.getElementById('player-placeholder').textContent = 'Decompressing clip...';
  video.style.display = 'none';

  document.querySelectorAll('.clip-item').forEach(el => {
    el.classList.toggle('active', el.dataset.name === name);
  });

  // Fetch info
  try {
    const infoResp = await fetch('/api/clip/' + encodeURIComponent(name) + '/info');
    const info = await infoResp.json();
    if (info.error) {
      status.textContent = 'Error: ' + info.error;
      document.getElementById('player-placeholder').textContent = 'Error loading clip';
      return;
    }
    clipFps = info.fps;

    // Trigger decompression and load video
    const videoUrl = '/api/clip/' + encodeURIComponent(name) + '/video';

    video.src = videoUrl;
    video.load();

    video.onloadeddata = () => {
      document.getElementById('player-placeholder').style.display = 'none';
      video.style.display = 'block';
      status.textContent = '';

      document.getElementById('seek-bar').disabled = false;
      document.getElementById('btn-play').disabled = false;
      document.getElementById('btn-stop').disabled = false;
      document.getElementById('btn-prev').disabled = false;
      document.getElementById('btn-next').disabled = false;
      updateTimeDisplay();
    };

    video.onerror = () => {
      status.textContent = 'Error loading video';
      document.getElementById('player-placeholder').textContent = 'Failed to load video';
    };

    // File info panel
    const fileInfo = document.getElementById('file-info');
    fileInfo.innerHTML = [
      `<span><b>Resolution:</b> ${info.width}x${info.height}</span>`,
      `<span><b>FPS:</b> ${info.fps}</span>`,
      `<span><b>Frames:</b> ${info.frame_count}</span>`,
      `<span><b>Detection:</b> ${info.detection}</span>`,
      `<span><b>Recorded:</b> ${info.recorded}</span>`,
      `<span><b>Compressed:</b> ${info.compressed_size}</span>`,
      `<span><b>Original:</b> ${info.original_size}</span>`,
      `<span><b>Ratio:</b> ${info.ratio}</span>`,
    ].join('');

  } catch(e) {
    status.textContent = 'Error: ' + e.message;
  }
}

function togglePlay() {
  if (video.paused) {
    if (video.ended) video.currentTime = 0;
    video.play();
    document.getElementById('btn-play').innerHTML = '&#10074;&#10074; Pause';
  } else {
    video.pause();
    document.getElementById('btn-play').innerHTML = '&#9654; Play';
  }
}

function stopPlayback() {
  video.pause();
  video.currentTime = 0;
  document.getElementById('btn-play').innerHTML = '&#9654; Play';
  updateTimeDisplay();
}

function seekTo(val) {
  if (video.duration) {
    video.currentTime = (val / 1000) * video.duration;
    updateTimeDisplay();
  }
}

function stepFrame(dir) {
  video.pause();
  document.getElementById('btn-play').innerHTML = '&#9654; Play';
  video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + dir / clipFps));
  updateTimeDisplay();
}

function setSpeed(val) {
  video.playbackRate = parseFloat(val);
}
</script>
</body>
</html>
"""


def create_app(recorder, clips_dir="clips"):
    
    app = Flask(__name__)

    
    _temp_cache = {}
    _cache_lock = threading.Lock()

    def _cleanup_temp(exclude=None):
        
        with _cache_lock:
            for name, path in list(_temp_cache.items()):
                if name != exclude:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                    del _temp_cache[name]

    def _get_or_decompress(name):
        
        with _cache_lock:
            if name in _temp_cache and os.path.exists(_temp_cache[name]):
                return _temp_cache[name]

        
        _cleanup_temp(exclude=None)

        path = os.path.join(clips_dir, name)
        decoder = SteamicDecoder(path)
        tmp_path = decoder.decompress_to_file()

        with _cache_lock:
            _temp_cache[name] = tmp_path

        return tmp_path

    @app.route("/")
    def index():
        return render_template_string(PAGE_HTML)

    @app.route("/video_feed")
    def video_feed():
        def generate():
            while True:
                jpeg = recorder.get_frame_jpeg()
                if jpeg:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
                time.sleep(0.03)
        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/api/status")
    def api_status():
        return jsonify(recorder.get_status())

    @app.route("/api/clips")
    def api_clips():
        clips = []
        if os.path.isdir(clips_dir):
            for f in sorted(os.listdir(clips_dir), reverse=True):
                if f.endswith(".steamic"):
                    fpath = os.path.join(clips_dir, f)
                    size = os.path.getsize(fpath)
                    clips.append({"name": f, "size": _format_size(size)})
        return jsonify(clips)

    @app.route("/api/clip/<name>/info")
    def api_clip_info(name):
        path = os.path.join(clips_dir, name)
        if not os.path.exists(path):
            return jsonify({"error": "File not found"})

        try:
            decoder = SteamicDecoder(path)
            meta = decoder.metadata
            compressed_size = os.path.getsize(path) - 27  
            recorded = datetime.fromtimestamp(meta["timestamp"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            ratio = compressed_size / meta["original_size"] * 100 if meta["original_size"] > 0 else 0

            return jsonify({
                "fps": meta["fps"],
                "width": meta["width"],
                "height": meta["height"],
                "frame_count": meta["frame_count"],
                "detection": meta["detection_name"],
                "recorded": recorded,
                "compressed_size": _format_size(os.path.getsize(path)),
                "original_size": _format_size(meta["original_size"]),
                "ratio": f"{ratio:.0f}%",
            })
        except Exception as e:
            return jsonify({"error": str(e)})

    @app.route("/api/clip/<name>/video")
    def api_clip_video(name):
        path = os.path.join(clips_dir, name)
        if not os.path.exists(path):
            return jsonify({"error": "File not found"}), 404

        try:
            tmp_path = _get_or_decompress(name)
            return send_file(tmp_path, mimetype="video/x-msvideo", conditional=True)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


def _format_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"
