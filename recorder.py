import cv2
import os
import time
import threading
import base64
from datetime import datetime

from detector import Detector
from codec import SteamicEncoder, DETECTION_FACE, DETECTION_VEHICLE, DETECTION_BOTH


class Recorder:
    """Captures camera feed, runs detection, and records .steamic clips."""

    def __init__(self, camera_index=0, clip_duration=30, output_dir="clips",
                 detect_interval=3, cooldown=5, target_fps=30):
        self.camera_index = camera_index
        self.clip_duration = clip_duration
        self.output_dir = output_dir
        self.detect_interval = detect_interval
        self.cooldown = cooldown
        self.target_fps = target_fps

        self.detector = Detector()
        self._recording = False
        self._saving = False
        self._encoder = None
        self._record_start = 0
        self._record_frames = 0
        self._record_target_frames = 0
        self._last_record_end = 0
        self._running = False

        
        self._lock = threading.Lock()
        self._latest_jpeg = None
        self._status_text = "MONITORING"
        self._is_recording = False
        self._last_detections = {"faces": [], "vehicles": []}
        self._clips = []

        os.makedirs(output_dir, exist_ok=True)

    def start(self):
        """Main loop: capture -> detect -> record at constant framerate."""
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            print("[Recorder] Error: Could not open camera")
            return

        cam_fps = cap.get(cv2.CAP_PROP_FPS)
        if cam_fps <= 0 or cam_fps > 120:
            cam_fps = 30

        fps = self.target_fps
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"[Recorder] Camera opened: {width}x{height} @ {fps}fps (constant)")
        print("[Recorder] Monitoring for faces and vehicles...")

        self._running = True
        frame_num = 0
        last_detections = {"faces": [], "vehicles": []}
        frame_interval = 1.0 / fps

        try:
            while self._running:
                frame_time = time.monotonic()

                ret, frame = cap.read()
                if not ret:
                    print("[Recorder] Failed to read frame")
                    break

                
                if frame_num % self.detect_interval == 0:
                    last_detections = self.detector.detect(frame)

                
                has_faces = len(last_detections["faces"]) > 0
                has_vehicles = len(last_detections["vehicles"]) > 0

                if (has_faces or has_vehicles) and not self._recording and not self._saving:
                    now = time.time()
                    if now - self._last_record_end >= self.cooldown:
                        detection_type = self._get_detection_type(has_faces, has_vehicles)
                        self._start_recording(width, height, fps, detection_type)

                
                if self._recording:
                    self._encoder.write_frame(frame)
                    self._record_frames += 1

                    if self._record_frames >= self._record_target_frames:
                        self._stop_recording()

                
                display = self.detector.draw_detections(frame, last_detections)
                self._draw_status(display)
                _, jpeg = cv2.imencode(".jpg", display, [cv2.IMWRITE_JPEG_QUALITY, 70])

                with self._lock:
                    self._latest_jpeg = jpeg.tobytes()
                    self._last_detections = last_detections
                    self._is_recording = self._recording
                    if self._recording:
                        elapsed = time.time() - self._record_start
                        remaining = max(0, self.clip_duration - elapsed)
                        self._status_text = f"REC {remaining:.0f}s"
                    elif self._saving:
                        self._status_text = "Saving Clip..."
                    else:
                        self._status_text = "MONITORING"

                frame_num += 1

                
                elapsed = time.monotonic() - frame_time
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        finally:
            if self._recording:
                self._stop_recording()
            cap.release()
            print("[Recorder] Stopped")

    def get_frame_jpeg(self):
        """Return the latest JPEG frame bytes (for the web UI)."""
        with self._lock:
            return self._latest_jpeg

    def get_status(self):
        """Return current status dict (for the web UI)."""
        with self._lock:
            return {
                "status": self._status_text,
                "recording": self._is_recording,
                "faces": len(self._last_detections["faces"]),
                "vehicles": len(self._last_detections["vehicles"]),
                "clips": list(self._clips),
            }

    def _get_detection_type(self, has_faces, has_vehicles):
        if has_faces and has_vehicles:
            return DETECTION_BOTH
        elif has_faces:
            return DETECTION_FACE
        else:
            return DETECTION_VEHICLE

    def _start_recording(self, width, height, fps, detection_type):
        detection_names = {DETECTION_FACE: "face", DETECTION_VEHICLE: "vehicle",
                          DETECTION_BOTH: "both"}
        name = detection_names[detection_type]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{name}.steamic"
        filepath = os.path.join(self.output_dir, filename)

        self._encoder = SteamicEncoder(
            filepath, width, height, fps, detection_type
        )
        self._recording = True
        self._record_start = time.time()
        self._record_frames = 0
        self._record_target_frames = fps * self.clip_duration

        print(f"[Recorder] Recording started: {filename} "
              f"({self.clip_duration}s, {self._record_target_frames} frames)")

    def _stop_recording(self):
        if self._encoder:
            encoder = self._encoder
            self._encoder = None
            self._recording = False
            self._saving = True
            elapsed = time.time() - self._record_start
            frames = self._record_frames
            print(f"[Recorder] Recording stopped ({elapsed:.1f}s, {frames} frames), compressing...")

            
            encoder.finalize()

            
            def _compress():
                try:
                    encoder.compress()
                    filename = os.path.basename(encoder.path)
                    with self._lock:
                        self._clips.append(filename)
                finally:
                    self._saving = False
                    self._last_record_end = time.time()

            threading.Thread(target=_compress, daemon=True).start()
        else:
            self._recording = False

    def _draw_status(self, frame):
        h = frame.shape[0]

        if self._recording:
            elapsed = time.time() - self._record_start
            remaining = max(0, self.clip_duration - elapsed)
            text = f"REC {remaining:.0f}s"
            cv2.circle(frame, (20, 30), 8, (0, 0, 255), -1)
            cv2.putText(frame, text, (35, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        elif self._saving:
            cv2.putText(frame, "Saving Clip...", (10, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 180, 255), 2)
        else:
            cv2.putText(frame, "MONITORING", (10, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    def stop(self):
        self._running = False
