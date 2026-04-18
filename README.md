# CamAI

Camera AI motion detection system that watches a webcam for faces and vehicles, automatically records short clips, compresses them into a custom `.steamic` format, and provides a browser-based UI to decompress and play them back.

## Features

- **Real-time detection** -- faces (Haar cascade) and vehicles (MobileNet SSD) detected via OpenCV
- **Automatic recording** -- starts a clip when a face or vehicle appears, stops after a configurable duration
- **Constant-framerate recording** -- clips are recorded at a steady 30 fps regardless of camera speed
- **MP4 + LZMA compression** -- records to standard MP4, then LZMA-compresses it into a `.steamic` container (like a zip file). The viewer decompresses it back to MP4 for playback.
- **Web-based UI** -- live camera feed and clip viewer accessible from any browser on the local network
- **Hardware-accelerated playback** -- decompressed clips play via the browser's native `<video>` element with no lag

## Requirements

- Python 3.9+
- A webcam

## Setup

```bash
pip install -r requirements.txt
```

On first run, the MobileNet SSD model files (~23 MB) are downloaded automatically to `models/` for vehicle detection.

## Usage

```bash
python main.py
```

Then open **http://localhost:3400** in your browser.

| Flag | Default | Description |
|------|---------|-------------|
| `--camera` | `0` | Camera device index |
| `--output` | `clips` | Directory for recorded clips |
| `--duration` | `30` | Clip length in seconds |
| `--cooldown` | `5` | Min seconds between recordings |
| `--fps` | `30` | Target recording framerate |
| `--port` | `3400` | Web UI port |

### Examples

```bash
python main.py --camera 1 --duration 15 --fps 24
python main.py --port 8080 --output recordings
```

## Web UI

The interface has two pages:

- **Camera** -- live MJPEG feed from the webcam with detection overlays and a status bar showing monitoring/recording state
- **Viewer** -- lists all recorded `.steamic` clips. Click one to decompress and play it with full transport controls (play/pause, seeking, speed 0.25x-4x, frame stepping). Shows compression ratio and file metadata.

## How .steamic Compression Works

1. **Record**: Video is captured at constant fps and written as a standard MP4 file
2. **Compress**: The MP4 is LZMA-compressed and wrapped in a `.steamic` container with a metadata header (detection type, timestamp, resolution, frame count)
3. **Decompress**: When viewing, the `.steamic` file is decompressed back to a temp MP4 and served to the browser's native video player

## Project Structure

```
steamic/
├── main.py          # Entry point -- starts recorder + web server
├── recorder.py      # Camera capture, detection loop, constant-fps recording
├── detector.py      # Face and vehicle detection (Haar + MobileNet SSD)
├── codec.py         # .steamic format: MP4 + LZMA encoder/decoder
├── web.py           # Flask web server and HTML UI
├── requirements.txt
├── models/          # Auto-downloaded detection models
└── clips/           # Recorded .steamic files
```
