"""
Virtual Camera / Broadcasting Module
Outputs filtered video as a virtual camera for OBS, Zoom, Teams, etc.
"""

import cv2
import numpy as np
import threading
import time
import subprocess
import os


class VirtualCamera:
    """
    Virtual camera that outputs filtered video.

    Two methods:
    1. OBS Virtual Camera (requires OBS 28+ and pyvirtualcam)
    2. Window Capture Mode (works with any OBS version)

    Install: pip install pyvirtualcam
    """

    def __init__(self):
        self.is_active = False
        self.virtual_cam = None
        self.frame_buffer = None
        self.width = 640
        self.height = 480
        self.fps = 30
        self.backend = None
        self.available = False
        self.error_message = None
        self.obs_path = None
        self.obs_running = False
        self.window_name = "WebcamStudioPro - Yayin"
        self.window_mode = False
        self._check_availability()

    def _find_obs(self):
        """Find OBS installation path"""
        paths = [
            r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
            r"C:\Program Files (x86)\obs-studio\bin\32bit\obs32.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\obs-studio\bin\64bit\obs64.exe"),
        ]
        for path in paths:
            if os.path.exists(path):
                return path
        return None

    def _is_obs_running(self):
        """Check if OBS is running"""
        try:
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq obs64.exe'],
                capture_output=True, text=True
            )
            return 'obs64.exe' in result.stdout
        except Exception:
            return False

    def _check_availability(self):
        """Check if pyvirtualcam is available"""
        try:
            import pyvirtualcam
            self.obs_path = self._find_obs()
            self.obs_running = self._is_obs_running()

            if self.obs_path:
                self.available = True
                self.backend = "OBS / Pencere Modu"
            else:
                # Window mode still works without OBS
                self.available = True
                self.backend = "Pencere Yakalama Modu"
        except ImportError:
            # Window mode still works without pyvirtualcam
            self.available = True
            self.backend = "Pencere Yakalama Modu"

    def start(self, width=640, height=480, fps=30):
        """Start virtual camera output"""
        self.width = width
        self.height = height
        self.fps = fps

        # Try OBS Virtual Camera first
        try:
            import pyvirtualcam

            if not self._is_obs_running() and self.obs_path:
                # Try to start OBS
                subprocess.Popen([self.obs_path, '--startvirtualcam'],
                               creationflags=subprocess.DETACHED_PROCESS)
                time.sleep(3)

            self.virtual_cam = pyvirtualcam.Camera(
                width=width,
                height=height,
                fps=fps,
                fmt=pyvirtualcam.PixelFormat.BGR
            )
            self.is_active = True
            self.window_mode = False
            return True, f"OBS Virtual Camera baslatildi: {self.virtual_cam.device}"

        except Exception:
            # Fallback to window mode
            pass

        # Window capture mode - use tkinter for better OBS compatibility
        try:
            self._create_tk_window(width, height)
            self.is_active = True
            self.window_mode = True
            return True, "Pencere modu baslatildi. OBS'de 'Pencere Yakalama' ile secebilirsiniz."

        except Exception as e:
            # Fallback to OpenCV window
            try:
                cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
                cv2.resizeWindow(self.window_name, width, height)
                self.is_active = True
                self.window_mode = True
                return True, "Pencere modu baslatildi. OBS'de 'Pencere Yakalama' ile secebilirsiniz."
            except Exception as e2:
                self.is_active = False
                return False, f"Baslatma hatasi: {str(e2)}"

    def _create_tk_window(self, width, height):
        """Create a tkinter window for better OBS compatibility"""
        import tkinter as tk
        from PIL import Image, ImageTk

        self.tk_root = tk.Tk()
        self.tk_root.title(self.window_name)
        self.tk_root.geometry(f"{width}x{height}")
        self.tk_root.configure(bg='black')
        self.tk_root.attributes('-topmost', True)

        self.tk_label = tk.Label(self.tk_root, bg='black')
        self.tk_label.pack(fill=tk.BOTH, expand=True)

        self.tk_image = None
        self.tk_width = width
        self.tk_height = height

    def send_frame(self, frame):
        """Send a frame to virtual camera"""
        if not self.is_active or frame is None:
            return False

        try:
            # Resize frame
            if frame.shape[1] != self.width or frame.shape[0] != self.height:
                frame = cv2.resize(frame, (self.width, self.height))

            # Try OBS Virtual Camera first
            if not self.window_mode and self.virtual_cam is not None:
                try:
                    self.virtual_cam.send(frame)
                    return True
                except Exception:
                    self.window_mode = True

            # Tkinter window mode
            if self.window_mode and hasattr(self, 'tk_root') and self.tk_root is not None:
                try:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    img = img.resize((self.tk_width, self.tk_height), Image.Resampling.LANCZOS)
                    self.tk_image = ImageTk.PhotoImage(image=img)
                    self.tk_label.configure(image=self.tk_image)
                    self.tk_root.update()
                    return True
                except Exception:
                    pass

            # OpenCV fallback
            if self.window_mode:
                cv2.imshow(self.window_name, frame)
                cv2.waitKey(1)
                return True

            return False

        except Exception:
            return False

    def stop(self):
        """Stop virtual camera"""
        self.is_active = False

        if self.virtual_cam is not None:
            try:
                self.virtual_cam.close()
            except Exception:
                pass
            self.virtual_cam = None

        if self.window_mode:
            # Close tkinter window
            if hasattr(self, 'tk_root') and self.tk_root is not None:
                try:
                    self.tk_root.destroy()
                except Exception:
                    pass
                self.tk_root = None
                self.tk_label = None
                self.tk_image = None
            # Close OpenCV window
            try:
                cv2.destroyWindow(self.window_name)
            except Exception:
                pass
            self.window_mode = False

    def get_info(self):
        """Get virtual camera info"""
        if not self.available:
            return "Mevcut Degil"
        if self.is_active:
            mode = "OBS Virtual" if not self.window_mode else "Pencere"
            return f"Aktif ({mode}) - {self.width}x{self.height}@{self.fps}fps"
        return f"Backend: {self.backend}"


class BroadcastManager:
    """Manages broadcast mode with multiple output options"""

    def __init__(self):
        self.virtual_cam = VirtualCamera()
        self.is_broadcasting = False
        self.frame_count = 0
        self.start_time = 0

    def start_broadcast(self, width=640, height=480, fps=30):
        """Start broadcasting to virtual camera"""
        if not self.virtual_cam.available:
            return False, self.virtual_cam.error_message or "Virtual kamera mevcut degil"

        success, message = self.virtual_cam.start(width, height, fps)
        if success:
            self.is_broadcasting = True
            self.frame_count = 0
            self.start_time = time.time()
        return success, message

    def send_frame(self, frame):
        """Send frame to broadcast"""
        if self.is_broadcasting and frame is not None:
            success = self.virtual_cam.send_frame(frame)
            if success:
                self.frame_count += 1
            return success
        return False

    def stop_broadcast(self):
        """Stop broadcasting"""
        self.virtual_cam.stop()
        self.is_broadcasting = False
        self.frame_count = 0

    def get_duration(self):
        """Get broadcast duration in seconds"""
        if self.is_broadcasting:
            return time.time() - self.start_time
        return 0

    def get_stats(self):
        """Get broadcast statistics"""
        if not self.is_broadcasting:
            return "Yayin Yok"

        duration = self.get_duration()
        avg_fps = self.frame_count / duration if duration > 0 else 0
        return f"Süre: {duration:.0f}s | Kare: {self.frame_count} | Ort. FPS: {avg_fps:.1f}"
