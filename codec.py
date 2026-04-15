import struct
import lzma
import time
import os
import tempfile

import cv2

MAGIC = b"STMC"
VERSION = 2
HEADER_FORMAT = "<4sBBdHHBII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

DETECTION_FACE = 0
DETECTION_VEHICLE = 1
DETECTION_BOTH = 2


class SteamicEncoder:
    

    def __init__(self, path, width, height, fps, detection_type):
        self.path = path
        self.width = width
        self.height = height
        self.fps = fps
        self.detection_type = detection_type
        self.timestamp = time.time()
        self.frame_count = 0

        # Write to a temporary MJPEG AVI first
        fd, self._tmp_path = tempfile.mkstemp(suffix=".avi")
        os.close(fd)

        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        self._writer = cv2.VideoWriter(self._tmp_path, fourcc, fps, (width, height))
        if not self._writer.isOpened():
            os.unlink(self._tmp_path)
            raise RuntimeError("Failed to open VideoWriter")

    def write_frame(self, frame):
        
        self._writer.write(frame)
        self.frame_count += 1

    def finalize(self):
        
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def compress(self):
        
        with open(self._tmp_path, "rb") as f:
            raw_data = f.read()
        raw_size = len(raw_data)

        compressed = lzma.compress(raw_data, preset=6)

        header = struct.pack(
            HEADER_FORMAT,
            MAGIC, VERSION, self.detection_type, self.timestamp,
            self.width, self.height, self.fps, self.frame_count, raw_size,
        )
        with open(self.path, "wb") as f:
            f.write(header)
            f.write(compressed)

        os.unlink(self._tmp_path)

        ratio = len(compressed) / raw_size * 100 if raw_size > 0 else 0
        print(f"[Codec] Saved {self.frame_count} frames to {self.path} "
              f"(MJPEG: {raw_size // 1024}KB -> LZMA: {len(compressed) // 1024}KB, {ratio:.0f}%)")

    def close(self):
        
        self.finalize()
        self.compress()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class SteamicDecoder:
    

    def __init__(self, path):
        self.path = path
        self.metadata = None
        self._read_header()

    def _read_header(self):
        with open(self.path, "rb") as f:
            raw = f.read(HEADER_SIZE)

        if len(raw) < HEADER_SIZE:
            raise ValueError("File too small to be a valid .steamic file")

        (magic, version, detection_type, timestamp,
         width, height, fps, frame_count, original_size) = struct.unpack(HEADER_FORMAT, raw)

        if magic != MAGIC:
            raise ValueError(f"Invalid magic bytes: {magic!r}")
        if version != VERSION:
            raise ValueError(f"Unsupported version: {version} (expected {VERSION})")

        detection_names = {0: "face", 1: "vehicle", 2: "both"}
        self.metadata = {
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
            "detection_type": detection_type,
            "detection_name": detection_names.get(detection_type, "unknown"),
            "timestamp": timestamp,
            "original_size": original_size,
        }

    def decompress_to_file(self, output_path=None):
        
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".avi")
            os.close(fd)

        with open(self.path, "rb") as f:
            f.seek(HEADER_SIZE)
            compressed = f.read()

        raw_data = lzma.decompress(compressed)

        with open(output_path, "wb") as f:
            f.write(raw_data)

        return output_path

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
