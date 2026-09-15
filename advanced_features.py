"""
Advanced Webcam Features - Recording, Filters, Motion Detection, Face Detection
"""

import cv2
import numpy as np
from datetime import datetime
import os
import threading
import time


class RecordingManager:
    """Manages video recording"""

    def __init__(self, save_dir="recordings"):
        self.save_dir = save_dir
        self.is_recording = False
        self.video_writer = None
        self.ensure_save_directory()

    def ensure_save_directory(self):
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def start_recording(self, frame, camera_id, fps=30):
        if self.is_recording:
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_cam{camera_id}_{timestamp}.avi"
        filepath = os.path.join(self.save_dir, filename)

        h, w = frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.video_writer = cv2.VideoWriter(filepath, fourcc, fps, (w, h))

        self.is_recording = True
        return True

    def write_frame(self, frame):
        if self.is_recording and self.video_writer is not None:
            self.video_writer.write(frame)
            return True
        return False

    def stop_recording(self):
        if not self.is_recording:
            return None

        self.is_recording = False
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

        return True


class FilterManager:
    """Manages video filters"""

    def __init__(self):
        self.filters = {
            "Yok": self.no_filter,
            "Gri": self.grayscale,
            "Sepya": self.sepia,
            "Negatif": self.negative,
            "Bulanik": self.blur,
            "Keskin": self.sharpen,
            "Parlak": self.brighten,
            "Kontrast": self.high_contrast
        }
        self.current_filter = "Yok"

    def get_filter_names(self):
        return list(self.filters.keys())

    def apply_filter(self, frame):
        if self.current_filter in self.filters:
            return self.filters[self.current_filter](frame)
        return frame

    def set_filter(self, filter_name):
        if filter_name in self.filters:
            self.current_filter = filter_name
            return True
        return False

    def no_filter(self, frame):
        return frame

    def grayscale(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    def sepia(self, frame):
        kernel = np.array([[0.272, 0.534, 0.131],
                           [0.349, 0.686, 0.168],
                           [0.393, 0.769, 0.189]])
        sepia_frame = cv2.transform(frame, kernel)
        return np.clip(sepia_frame, 0, 255).astype(np.uint8)

    def negative(self, frame):
        return 255 - frame

    def blur(self, frame):
        return cv2.GaussianBlur(frame, (15, 15), 0)

    def sharpen(self, frame):
        kernel = np.array([[-1, -1, -1],
                           [-1, 9, -1],
                           [-1, -1, -1]])
        return cv2.filter2D(frame, -1, kernel)

    def brighten(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] + 50, 0, 255)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    def high_contrast(self, frame):
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


class FaceDetector:
    """Face detection using DNN or contour-based fallback"""

    def __init__(self):
        self.is_enabled = False
        self.available = True
        self.net = None
        self.use_dnn = False
        self.load_model()

    def load_model(self):
        """Try to load DNN model, fallback to contour-based detection"""
        try:
            model_file = cv2.data.haarcascades + "opencv_face_detector_uint8.pb"
            config_file = cv2.data.haarcascades + "opencv_face_detector.pbtxt"

            if os.path.exists(model_file) and os.path.exists(config_file):
                self.net = cv2.dnn.readNetFromTensorflow(model_file, config_file)
                self.use_dnn = True
                return
        except Exception:
            pass

        # Fallback: use simple skin-color based detection
        self.use_dnn = False
        self.available = True

    def detect_faces(self, frame):
        if not self.is_enabled or not self.available:
            return frame

        if self.use_dnn and self.net is not None:
            return self._detect_dnn(frame)
        else:
            return self._detect_contour(frame)

    def _detect_dnn(self, frame):
        """DNN-based face detection"""
        try:
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(
                cv2.resize(frame, (300, 300)),
                1.0, (300, 300),
                (104.0, 177.0, 123.0)
            )
            self.net.setInput(blob)
            detections = self.net.forward()

            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > 0.5:
                    x1 = int(detections[0, 0, i, 3] * w)
                    y1 = int(detections[0, 0, i, 4] * h)
                    x2 = int(detections[0, 0, i, 5] * w)
                    y2 = int(detections[0, 0, i, 6] * h)

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, "Yuz", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        except Exception:
            pass
        return frame

    def _detect_contour(self, frame):
        """Simple skin-color based face detection as fallback"""
        try:
            h, w = frame.shape[:2]
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # Stricter skin color range in HSV
            lower_skin = np.array([0, 30, 60], dtype=np.uint8)
            upper_skin = np.array([20, 170, 255], dtype=np.uint8)

            mask = cv2.inRange(hsv, lower_skin, upper_skin)

            # Apply morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            detected_faces = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 15000:  # Larger minimum area
                    x, y, cw, ch = cv2.boundingRect(contour)
                    aspect_ratio = cw / ch

                    # Stricter face-like aspect ratio (0.6 to 1.0) and size
                    if 0.6 < aspect_ratio < 1.0 and cw > 80 and ch > 80:
                        # Check if face is in upper 70% of frame (faces usually not at bottom)
                        if y < h * 0.7:
                            # Check if not too close to edges
                            if x > 20 and x + cw < w - 20:
                                detected_faces.append((x, y, cw, ch))

            # Draw only the largest face-like region
            if detected_faces:
                largest = max(detected_faces, key=lambda f: f[2] * f[3])
                x, y, cw, ch = largest
                cv2.rectangle(frame, (x, y), (x + cw, y + ch), (0, 255, 0), 2)
                cv2.putText(frame, "Yuz", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        except Exception:
            pass
        return frame

    def toggle_detection(self):
        self.is_enabled = not self.is_enabled
        return self.is_enabled

    def get_status(self):
        return "Açık" if self.is_enabled else "Kapalı"


class MotionDetector:
    """Motion detection using frame differencing"""

    def __init__(self):
        self.is_enabled = False
        self.previous_frame = None
        self.sensitivity = 25  # Motion sensitivity threshold
        self.min_area = 5000  # Minimum contour area to consider as motion
        self.on_motion_callback = None
        self.last_motion_time = 0
        self.motion_cooldown = 2  # seconds between motion alerts

    def detect_motion(self, frame):
        """Detect motion in frame"""
        if not self.is_enabled:
            return frame, False

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        motion_detected = False

        if self.previous_frame is None:
            self.previous_frame = gray
            return frame, False

        # Calculate frame difference
        frame_delta = cv2.absdiff(self.previous_frame, gray)
        thresh = cv2.threshold(frame_delta, self.sensitivity, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            if cv2.contourArea(contour) > self.min_area:
                motion_detected = True
                (x, y, w, h) = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # Draw motion status
        status = "HAREKET ALGILANDI!" if motion_detected else "Hareket Yok"
        color = (0, 0, 255) if motion_detected else (0, 255, 0)
        cv2.putText(frame, status, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # Callback on motion
        if motion_detected:
            current_time = time.time()
            if current_time - self.last_motion_time > self.motion_cooldown:
                self.last_motion_time = current_time
                if self.on_motion_callback:
                    self.on_motion_callback(frame)

        self.previous_frame = gray
        return frame, motion_detected

    def set_sensitivity(self, value):
        self.sensitivity = max(5, min(100, value))

    def set_min_area(self, value):
        self.min_area = max(500, min(50000, value))

    def toggle_detection(self):
        self.is_enabled = not self.is_enabled
        self.previous_frame = None  # Reset when toggling
        return self.is_enabled

    def get_status(self):
        return "Açık" if self.is_enabled else "Kapalı"


class ScheduledRecorder:
    """Manages scheduled recording based on motion or time"""

    def __init__(self, recording_manager):
        self.recording_manager = recording_manager
        self.is_scheduled = False
        self.schedule_type = "motion"  # "motion" or "time"
        self.record_duration = 10  # seconds
        self.time_interval = 60  # seconds between recordings for time-based
        self.last_record_time = 0
        self.is_recording_active = False
        self.record_start_time = 0
        self.camera_id = 0

    def start_schedule(self, camera_id, schedule_type="motion"):
        self.is_scheduled = True
        self.schedule_type = schedule_type
        self.camera_id = camera_id
        self.last_record_time = 0

    def stop_schedule(self):
        self.is_scheduled = False
        self.is_recording_active = False
        if self.recording_manager.is_recording:
            self.recording_manager.stop_recording()

    def on_motion_detected(self, frame):
        """Called when motion is detected"""
        if not self.is_scheduled or self.schedule_type != "motion":
            return

        current_time = time.time()
        if not self.is_recording_active:
            if current_time - self.last_record_time > self.time_interval:
                self._start_timed_recording(frame)

    def check_time_based_recording(self, frame):
        """Check if it's time to record for time-based scheduling"""
        if not self.is_scheduled or self.schedule_type != "time":
            return

        current_time = time.time()
        if not self.is_recording_active:
            if current_time - self.last_record_time > self.time_interval:
                self._start_timed_recording(frame)
        else:
            # Check if recording duration exceeded
            if current_time - self.record_start_time >= self.record_duration:
                self._stop_timed_recording()

    def _start_timed_recording(self, frame):
        """Start a timed recording"""
        success = self.recording_manager.start_recording(frame, self.camera_id)
        if success:
            self.is_recording_active = True
            self.record_start_time = time.time()
            self.last_record_time = time.time()

    def _stop_timed_recording(self):
        """Stop the current timed recording"""
        self.recording_manager.stop_recording()
        self.is_recording_active = False

    def set_duration(self, seconds):
        self.record_duration = max(1, min(300, seconds))

    def set_interval(self, seconds):
        self.time_interval = max(10, min(3600, seconds))


class TimerManager:
    """Manages screenshot timer"""

    def __init__(self):
        self.timer_seconds = 0
        self.is_timer_active = False
        self.callback = None

    def set_timer(self, seconds):
        self.timer_seconds = seconds

    def start_timer(self, callback):
        if self.timer_seconds > 0:
            self.is_timer_active = True
            self.callback = callback
            threading.Timer(self.timer_seconds, self.timer_callback).start()
            return True
        return False

    def timer_callback(self):
        if self.is_timer_active and self.callback:
            self.callback()
            self.is_timer_active = False

    def cancel_timer(self):
        self.is_timer_active = False
