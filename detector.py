import cv2
import numpy as np
import os
import urllib.request

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


CAR_CASCADE_URL = (
    "https://raw.githubusercontent.com/andrewssobral/vehicle_detection_haarcascades"
    "/master/cars.xml"
)

PROTOTXT_URL = (
    "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD"
    "/master/deploy.prototxt"
)


CAFFEMODEL_URL = (
    "https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel"
)

VEHICLE_CLASSES = {2: "bicycle", 6: "bus", 7: "car", 14: "motorbike"}


class Detector:
    

    def __init__(self):
        self._face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self._vehicle_net = None
        self._vehicle_cascade = None
        self._load_vehicle_model()

    def _download(self, url, dest):
        
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
            f.write(resp.read())

    def _load_vehicle_model(self):
        os.makedirs(MODELS_DIR, exist_ok=True)

        
        if self._try_load_mobilenet():
            return

        
        self._load_car_cascade()

    def _try_load_mobilenet(self):
        prototxt_path = os.path.join(MODELS_DIR, "MobileNetSSD_deploy.prototxt")
        caffemodel_path = os.path.join(MODELS_DIR, "MobileNetSSD_deploy.caffemodel")

        try:
            if not os.path.exists(prototxt_path):
                print("[Detector] Downloading MobileNet SSD prototxt...")
                self._download(PROTOTXT_URL, prototxt_path)

            if not os.path.exists(caffemodel_path):
                print("[Detector] Downloading MobileNet SSD caffemodel (~23MB)...")
                self._download(CAFFEMODEL_URL, caffemodel_path)

            
            size = os.path.getsize(caffemodel_path)
            if size < 1_000_000:  
                print(f"[Detector] Caffemodel too small ({size} bytes), likely bad download")
                os.remove(caffemodel_path)
                return False

            self._vehicle_net = cv2.dnn.readNetFromCaffe(prototxt_path, caffemodel_path)
            print("[Detector] MobileNet SSD loaded for vehicle detection")
            return True

        except Exception as e:
            print(f"[Detector] MobileNet SSD failed: {e}")
            
            for p in (prototxt_path, caffemodel_path):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            return False

    def _load_car_cascade(self):
        cascade_path = os.path.join(MODELS_DIR, "cars.xml")

        try:
            if not os.path.exists(cascade_path):
                print("[Detector] Downloading Haar car cascade...")
                self._download(CAR_CASCADE_URL, cascade_path)

            self._vehicle_cascade = cv2.CascadeClassifier(cascade_path)
            if self._vehicle_cascade.empty():
                self._vehicle_cascade = None
                print("[Detector] Warning: Car cascade failed to load")
            else:
                print("[Detector] Haar car cascade loaded for vehicle detection")

        except Exception as e:
            print(f"[Detector] Car cascade download failed: {e}")
            self._vehicle_cascade = None
            print("[Detector] Warning: No vehicle detection model available")

    def detect_faces(self, frame):
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        if len(faces) == 0:
            return []
        return [tuple(f) for f in faces]

    def detect_vehicles(self, frame):
        
        if self._vehicle_net is not None:
            return self._detect_vehicles_dnn(frame)
        elif self._vehicle_cascade is not None:
            return self._detect_vehicles_haar(frame)
        return []

    def _detect_vehicles_dnn(self, frame):
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5
        )
        self._vehicle_net.setInput(blob)
        detections = self._vehicle_net.forward()

        results = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence < 0.4:
                continue
            class_id = int(detections[0, 0, i, 1])
            if class_id not in VEHICLE_CLASSES:
                continue

            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            x1, y1, x2, y2 = box.astype(int)
            results.append((x1, y1, x2 - x1, y2 - y1, VEHICLE_CLASSES[class_id]))
        return results

    def _detect_vehicles_haar(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        vehicles = self._vehicle_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=3, minSize=(60, 60)
        )
        if len(vehicles) == 0:
            return []
        return [(x, y, w, h, "car") for (x, y, w, h) in vehicles]

    def detect(self, frame):
        
        faces = self.detect_faces(frame)
        vehicles = self.detect_vehicles(frame)
        return {"faces": faces, "vehicles": vehicles}

    def draw_detections(self, frame, detections):
        
        annotated = frame.copy()

        for (x, y, w, h) in detections["faces"]:
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                annotated, "Face", (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
            )

        for det in detections["vehicles"]:
            x, y, w, h, label = det
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (255, 0, 0), 2)
            cv2.putText(
                annotated, label, (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2
            )

        return annotated
