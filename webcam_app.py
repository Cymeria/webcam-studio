"""
Webcam Studio — Modern Premium Arayüz
Çoklu kamera desteği, tek tıkla ekran görüntüsü, çift tıkla tam ekran
"""

import os

# OpenCV log gürültüsünü ve obsensor arka ucunu kapat (cv2 importundan önce)
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_OBSENSOR", "0")

import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image, ImageTk
import time
from datetime import datetime
from tkinter import filedialog, messagebox
import threading
import sys
import io


# ── Premium koyu tema paleti ─────────────────────────────────────────────
UI = {
    "bg":            "#0b0e14",   # ana arka plan
    "panel":         "#10141d",   # üst bar / durum çubuğu
    "card":          "#151b28",   # kart yüzeyi
    "card_border":   "#242e44",   # kart kenarlığı
    "stage":         "#04060a",   # video sahnesi (siyaha yakın)
    "accent":        "#7c6bff",   # birincil vurgu (mor)
    "accent_hover":  "#6a58f0",
    "accent_soft":   "#1d2137",
    "success":       "#22c55e",
    "success_hover": "#16a34a",
    "danger":        "#ef4444",
    "danger_hover":  "#dc2626",
    "warning":       "#f59e0b",
    "warning_hover": "#d97706",
    "text":          "#e7eaf3",
    "muted":         "#8a93a8",
    "chip":          "#1a2133",
}


class CameraManager:
    """Manages camera detection and a single on-demand capture.

    Kameralar tarama sırasında açılıp hemen kapatılır; yalnızca seçilen
    kamera görüntü sırasında açık tutulur. Bu, MSMF/DSHOW "device busy"
    (grabFrame -1072873821) hatalarını önler.
    """

    BACKENDS = [cv2.CAP_DSHOW, cv2.CAP_MSMF]

    def __init__(self):
        self.cameras = {}          # id -> {"name", "resolution", "backend"}
        self.capture = None        # aktif cv2.VideoCapture (tek)
        self.current_camera = None
        self.current_camera_id = None

    @staticmethod
    def _quiet():
        """Suppress OpenCV console noise during probing"""
        old = (sys.stdout, sys.stderr)
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        return old

    def detect_cameras(self, max_cameras=5):
        """Detect available cameras; probe each index then release it"""
        self.release_all()
        detected = []
        old = self._quiet()

        try:
            for i in range(max_cameras):
                for backend in self.BACKENDS:
                    cap = None
                    try:
                        cap = cv2.VideoCapture(i, backend)
                        if cap.isOpened():
                            ret, frame = cap.read()
                            if ret and frame is not None:
                                h, w = frame.shape[:2]
                                detected.append(i)
                                self.cameras[i] = {
                                    "name": f"Camera {i}",
                                    "resolution": (w, h),
                                    "backend": backend
                                }
                                cap.release()
                                break
                        cap.release()
                    except Exception:
                        if cap is not None:
                            cap.release()
        finally:
            sys.stdout, sys.stderr = old

        return detected

    def get_camera_names(self):
        """Get list of camera names"""
        return [f"Camera {cam_id}" for cam_id in self.cameras.keys()]

    def get_camera_ids(self):
        """Get list of camera IDs"""
        return list(self.cameras.keys())

    def is_open(self):
        """Is the active capture usable?"""
        return self.capture is not None and self.capture.isOpened()

    def open_camera(self, camera_id, size=None):
        """Open (or reopen) the capture for a camera and verify a frame"""
        if camera_id not in self.cameras:
            return False

        self.close_capture()
        info = self.cameras[camera_id]
        backends = dict.fromkeys([info["backend"]] + self.BACKENDS)

        old = self._quiet()
        try:
            for backend in backends:
                cap = cv2.VideoCapture(camera_id, backend)
                if cap.isOpened():
                    if size is not None:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        h, w = frame.shape[:2]
                        info["resolution"] = (w, h)
                        info["backend"] = backend
                        self.capture = cap
                        self.current_camera_id = camera_id
                        self.current_camera = info
                        return True
                cap.release()
        finally:
            sys.stdout, sys.stderr = old

        return False

    def select_camera(self, camera_id, size=None):
        """Select and open a camera"""
        return self.open_camera(camera_id, size)

    def read_frame(self):
        """Read frame from current camera"""
        if self.is_open():
            ret, frame = self.capture.read()
            if ret and frame is not None:
                return True, frame
        return False, None

    def close_capture(self):
        """Release only the active capture (camera list stays)"""
        if self.capture is not None:
            try:
                self.capture.release()
            except Exception:
                pass
            self.capture = None

    def release_all(self):
        """Release the capture and forget all cameras"""
        self.close_capture()
        self.cameras.clear()
        self.current_camera = None
        self.current_camera_id = None


class ScreenshotManager:
    """Manages screenshot saving"""

    def __init__(self, save_dir="screenshots"):
        self.save_dir = save_dir
        self.ensure_save_directory()

    def ensure_save_directory(self):
        """Create save directory if it doesn't exist"""
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def save_screenshot(self, frame, camera_id):
        """Save frame as screenshot"""
        if frame is None:
            return None, "Kaydedilecek kare yok"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_cam{camera_id}_{timestamp}.png"
        filepath = os.path.join(self.save_dir, filename)

        cv2.imwrite(filepath, frame)
        return filepath, f"Kaydedildi: {filename}"


class WebcamApp(ctk.CTk):
    """Main application class — premium redesign"""

    RESOLUTION_OPTIONS = {
        "Otomatik": None,
        "640x480 (VGA)": (640, 480),
        "800x600 (SVGA)": (800, 600),
        "1280x720 (HD)": (1280, 720),
        "1280x960": (1280, 960),
        "1600x900": (1600, 900),
        "1920x1080 (FHD)": (1920, 1080),
        "1920x1440": (1920, 1440),
        "2560x1440 (QHD)": (2560, 1440),
    }

    def __init__(self):
        super().__init__()

        self.title("Webcam Studio")
        self.geometry("1280x820")
        self.minsize(1080, 700)

        ctk.set_appearance_mode("dark")
        self.configure(fg_color=UI["bg"])

        self.camera_manager = CameraManager()
        self.screenshot_manager = ScreenshotManager()
        self.is_streaming = False
        self.current_frame = None
        self.is_fullscreen = False
        self._last_time = time.time()
        self._fail_count = 0

        self._init_fonts()
        self.setup_ui()
        self.detect_cameras()

        self.bind("<Escape>", self.exit_fullscreen)
        self.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _init_fonts(self):
        """Central font definitions"""
        self.f_logo = ctk.CTkFont(family="Segoe UI", size=19, weight="bold")
        self.f_title = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        self.f_body = ctk.CTkFont(family="Segoe UI", size=13)
        self.f_small = ctk.CTkFont(family="Segoe UI", size=11)
        self.f_chip = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        self.f_btn = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")

    # ── UI kurulumu ──────────────────────────────────────────────────────

    def setup_ui(self):
        """Setup the user interface"""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.setup_header()
        self.setup_sidebar()
        self.setup_stage()
        self.setup_status_bar()

    def _card(self, parent, title, icon=""):
        """Create a titled card section, return its inner frame"""
        card = ctk.CTkFrame(
            parent, fg_color=UI["card"], corner_radius=16,
            border_width=1, border_color=UI["card_border"]
        )
        card.pack(fill="x", padx=14, pady=(0, 12))

        header = ctk.CTkLabel(
            card, text=f"{icon}  {title}", font=self.f_title,
            text_color=UI["muted"], anchor="w"
        )
        header.pack(fill="x", padx=16, pady=(12, 6))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=(0, 14))
        return inner

    def setup_header(self):
        """Top header bar with logo and live indicators"""
        self.header = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=UI["panel"])
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.header.grid_propagate(False)

        logo_box = ctk.CTkFrame(self.header, fg_color="transparent")
        logo_box.pack(side="left", padx=20, pady=12)

        self.logo_dot = ctk.CTkLabel(
            logo_box, text="●", font=ctk.CTkFont(size=20),
            text_color=UI["accent"]
        )
        self.logo_dot.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            logo_box, text="WEBCAM STUDIO", font=self.f_logo, text_color=UI["text"]
        ).pack(side="left")

        ctk.CTkLabel(
            logo_box, text="  |  Modern Kamera Arayüzü",
            font=self.f_small, text_color=UI["muted"]
        ).pack(side="left", pady=(4, 0))

        # Sağ taraf: canlı rozeti + FPS + çözünürlük çipleri
        self.live_badge = ctk.CTkLabel(
            self.header, text="○ BEKLEMEDE", font=self.f_chip,
            text_color=UI["muted"], fg_color=UI["chip"],
            corner_radius=14, width=120, height=28
        )
        self.live_badge.pack(side="right", padx=(6, 20), pady=18)

        self.fps_chip = ctk.CTkLabel(
            self.header, text="FPS  --", font=self.f_chip,
            text_color=UI["text"], fg_color=UI["chip"],
            corner_radius=14, width=90, height=28
        )
        self.fps_chip.pack(side="right", padx=6, pady=18)

        self.res_chip = ctk.CTkLabel(
            self.header, text="—", font=self.f_chip,
            text_color=UI["text"], fg_color=UI["chip"],
            corner_radius=14, width=130, height=28
        )
        self.res_chip.pack(side="right", padx=6, pady=18)

    def setup_sidebar(self):
        """Left control panel built from cards"""
        self.sidebar = ctk.CTkFrame(self, width=310, corner_radius=0, fg_color="transparent")
        self.sidebar.grid(row=1, column=0, sticky="nsw", pady=(14, 0))
        self.sidebar.grid_propagate(False)

        # Kamera kartı
        cam_box = self._card(self.sidebar, "KAMERA", "📷")

        self.camera_menu = ctk.CTkOptionMenu(
            cam_box, values=["Kamera algılanamadı"], command=self.on_camera_select,
            height=38, corner_radius=10, font=self.f_body,
            fg_color=UI["accent_soft"], button_color=UI["accent"],
            button_hover_color=UI["accent_hover"], dropdown_fg_color=UI["card"]
        )
        self.camera_menu.pack(fill="x", pady=(0, 8))

        self.refresh_btn = ctk.CTkButton(
            cam_box, text="🔄  Kameraları Yenile", command=self.detect_cameras,
            height=34, corner_radius=10, font=self.f_body,
            fg_color="transparent", hover_color=UI["accent_soft"],
            border_width=1, border_color=UI["card_border"], text_color=UI["muted"]
        )
        self.refresh_btn.pack(fill="x")

        # Kalite kartı
        res_box = self._card(self.sidebar, "GÖRÜNTÜ KALİTESİ", "🎞️")

        self.res_menu = ctk.CTkOptionMenu(
            res_box, values=list(self.RESOLUTION_OPTIONS.keys()),
            command=self.on_resolution_change,
            height=38, corner_radius=10, font=self.f_body,
            fg_color=UI["accent_soft"], button_color=UI["accent"],
            button_hover_color=UI["accent_hover"], dropdown_fg_color=UI["card"]
        )
        self.res_menu.set("Otomatik")
        self.res_menu.pack(fill="x")

        # Kontroller kartı
        ctl_box = self._card(self.sidebar, "KONTROLLER", "🎛️")

        self.stream_btn = ctk.CTkButton(
            ctl_box, text="▶   Yayını Başlat", command=self.toggle_stream,
            height=48, corner_radius=12, font=self.f_btn,
            fg_color=UI["success"], hover_color=UI["success_hover"]
        )
        self.stream_btn.pack(fill="x", pady=(0, 10))

        self.screenshot_btn = ctk.CTkButton(
            ctl_box, text="📸   Ekran Görüntüsü", command=self.take_screenshot,
            height=44, corner_radius=12, font=self.f_btn,
            fg_color=UI["warning"], hover_color=UI["warning_hover"],
            text_color="#1a1a1a", state="disabled"
        )
        self.screenshot_btn.pack(fill="x", pady=(0, 10))

        self.fullscreen_btn = ctk.CTkButton(
            ctl_box, text="⛶   Tam Ekran", command=self.toggle_fullscreen,
            height=44, corner_radius=12, font=self.f_btn,
            fg_color=UI["accent"], hover_color=UI["accent_hover"],
            state="disabled"
        )
        self.fullscreen_btn.pack(fill="x")

        ctk.CTkLabel(
            ctl_box, text="İpucu: Görüntüye çift tıklayarak tam ekrana geçin",
            font=self.f_small, text_color=UI["muted"], wraplength=240, justify="left"
        ).pack(fill="x", pady=(10, 0))

        # Kayıt yolu
        ctk.CTkLabel(
            self.sidebar,
            text=f"💾  {os.path.abspath(self.screenshot_manager.save_dir)}",
            font=self.f_small, text_color=UI["muted"],
            wraplength=270, justify="left", anchor="w"
        ).pack(fill="x", padx=18, pady=(4, 12))

    def setup_stage(self):
        """Main video stage with rounded dark canvas"""
        self.stage = ctk.CTkFrame(
            self, fg_color=UI["card"], corner_radius=18,
            border_width=1, border_color=UI["card_border"]
        )
        self.stage.grid(row=1, column=1, padx=(0, 14), pady=(14, 0), sticky="nsew")
        self.stage.grid_columnconfigure(0, weight=1)
        self.stage.grid_rowconfigure(0, weight=1)

        self.video_label = ctk.CTkLabel(
            self.stage,
            text="📷\n\nKamera bağlantısı bekleniyor...\n\n"
                 "Bir kamera seçin ve  ▶  Yayını Başlat'a tıklayın\n"
                 "Görüntüye çift tıklayarak tam ekrana geçebilirsiniz",
            font=self.f_body, text_color=UI["muted"],
            fg_color=UI["stage"], corner_radius=14
        )
        self.video_label.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Çift tık → tam ekran aç/kapat
        self.video_label.bind("<Double-Button-1>", self.on_video_double_click)

    def setup_status_bar(self):
        """Bottom status bar"""
        self.status_frame = ctk.CTkFrame(self, height=36, corner_radius=0, fg_color=UI["panel"])
        self.status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        self.status_frame.grid_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_frame, text="Hazır — kamera bekleniyor",
            font=self.f_small, text_color=UI["muted"]
        )
        self.status_label.pack(side="left", padx=16)

        self.resolution_label = ctk.CTkLabel(
            self.status_frame, text="", font=self.f_small, text_color=UI["muted"]
        )
        self.resolution_label.pack(side="right", padx=16)

        ctk.CTkLabel(
            self.status_frame, text="Çift tık / F11: Tam ekran   •   ESC: Çıkış",
            font=self.f_small, text_color=UI["muted"]
        ).pack(side="right", padx=16)

    # ── Kamera işlemleri ─────────────────────────────────────────────────

    def detect_cameras(self):
        """Detect and list available cameras"""
        if self.is_streaming:
            self.stop_stream()

        self.status_label.configure(text="Kameralar taranıyor...")
        self.update()

        detected = self.camera_manager.detect_cameras()

        if detected:
            camera_names = self.camera_manager.get_camera_names()
            self.camera_menu.configure(values=camera_names)
            self.camera_menu.set(camera_names[0])
            self.status_label.configure(text=f"{len(detected)} kamera bulundu")
            # İlk kamerayı otomatik seç ve yayını başlat
            self.on_camera_select(camera_names[0])
        else:
            self.camera_menu.configure(values=["Kamera bulunamadı"])
            self.camera_menu.set("Kamera bulunamadı")
            self.status_label.configure(text="Kamera bulunamadı")

    def on_camera_select(self, selection):
        """Handle camera selection — open it and auto-start the preview"""
        if not selection.startswith("Camera"):
            return

        cam_id = int(selection.split()[-1])
        if self.is_streaming:
            self.stop_stream()

        res = self.RESOLUTION_OPTIONS.get(self.res_menu.get())
        self.status_label.configure(text=f"{selection} açılıyor...")
        self.update()

        if self.camera_manager.open_camera(cam_id, res):
            w, h = self.camera_manager.cameras[cam_id]["resolution"]
            self._set_resolution_info(w, h)
            self.status_label.configure(text=f"{selection} seçildi")
            # Görüntü alınabiliyorsa yayını otomatik başlat
            self.start_stream()
        else:
            self.status_label.configure(
                text=f"{selection} açılamadı — başka bir uygulama kullanıyor olabilir")

    def on_resolution_change(self, selection):
        """Reopen the active camera with the selected resolution"""
        cam_id = self.camera_manager.current_camera_id
        if cam_id is None or not self.is_streaming:
            return

        res = self.RESOLUTION_OPTIONS.get(selection)
        self.status_label.configure(text="Çözünürlük uygulanıyor...")
        self.update()

        if self.camera_manager.open_camera(cam_id, res):
            w, h = self.camera_manager.cameras[cam_id]["resolution"]
            self._set_resolution_info(w, h)
            self.status_label.configure(text=f"Çözünürlük değiştirildi: {w}x{h}")
        else:
            self.status_label.configure(text="Çözünürlük uygulanamadı")

    def _set_resolution_info(self, w, h):
        """Update resolution chip + status bar text"""
        self.res_chip.configure(text=f"{w} × {h}")
        self.resolution_label.configure(text=f"Çözünürlük: {w}x{h}")

    # ── Yayın kontrolü ───────────────────────────────────────────────────

    def toggle_stream(self):
        """Single button start/stop toggle"""
        if self.is_streaming:
            self.stop_stream()
        else:
            self.start_stream()

    def start_stream(self):
        """Start video stream"""
        cam_id = self.camera_manager.current_camera_id
        if cam_id is None:
            messagebox.showwarning("Uyarı", "Lütfen önce bir kamera seçin")
            return

        # Kapalıysa seçili çözünürlükle aç
        if not self.camera_manager.is_open():
            res = self.RESOLUTION_OPTIONS.get(self.res_menu.get())
            self.status_label.configure(text="Kamera açılıyor...")
            self.update()
            if not self.camera_manager.open_camera(cam_id, res):
                self.status_label.configure(
                    text="Kamera açılamadı — başka bir uygulama kullanıyor olabilir")
                return
            w, h = self.camera_manager.cameras[cam_id]["resolution"]
            self._set_resolution_info(w, h)

        self.is_streaming = True
        self._fail_count = 0
        self._last_time = time.time()
        self.stream_btn.configure(
            text="⏹   Yayını Durdur",
            fg_color=UI["danger"], hover_color=UI["danger_hover"]
        )
        self.screenshot_btn.configure(state="normal")
        self.fullscreen_btn.configure(state="normal")
        self.live_badge.configure(text="●  CANLI", text_color=UI["danger"])
        self.status_label.configure(text="Yayın başlatıldı")

        self.update_frame()

    def _fit_to_box(self, img, box_w, box_h):
        """Aspect-fit (contain): tüm görüntü kutuya sığar, kırpılma olmaz"""
        if box_w <= 1 or box_h <= 1:
            return img
        ratio = min(box_w / img.width, box_h / img.height)
        new_w = max(1, int(img.width * ratio))
        new_h = max(1, int(img.height * ratio))
        return img.resize((new_w, new_h), Image.Resampling.BILINEAR)

    def update_frame(self):
        """Update video frame"""
        if not self.is_streaming:
            return

        ret, frame = self.camera_manager.read_frame()
        if ret:
            self._fail_count = 0
            self.current_frame = frame

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            # Görüntü alanının gerçek boyutuna göre orantılı sığdır
            pad = 4 if not self.is_fullscreen else 0
            box_w = self.video_label.winfo_width() - pad
            box_h = self.video_label.winfo_height() - pad
            img = self._fit_to_box(img, box_w, box_h)

            imgtk = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.video_label.configure(image=imgtk, text="")
            self.video_label.image = imgtk

            # FPS hesapla
            now = time.time()
            dt = now - self._last_time
            self._last_time = now
            if dt > 0:
                self.fps_chip.configure(text=f"FPS  {1 / dt:.0f}")
        else:
            self._fail_count += 1
            if self._fail_count >= 15:
                # Kamera yanıt vermiyor — yeniden bağlanmayı dene
                self.status_label.configure(text="Kamera yanıt vermiyor, yeniden bağlanılıyor...")
                res = self.RESOLUTION_OPTIONS.get(self.res_menu.get())
                if self.camera_manager.open_camera(self.camera_manager.current_camera_id, res):
                    self._fail_count = 0
                    self.status_label.configure(text="Kamera yeniden bağlandı")
                else:
                    self.stop_stream()
                    self.status_label.configure(
                        text="Kamera bağlantısı kurulamadı — kamerayı kullanan diğer uygulamaları kapatıp yenileyin")
                    return

        self.after(30, self.update_frame)

    def stop_stream(self):
        """Stop video stream"""
        self.is_streaming = False
        self.camera_manager.close_capture()
        self.stream_btn.configure(
            text="▶   Yayını Başlat",
            fg_color=UI["success"], hover_color=UI["success_hover"]
        )
        self.screenshot_btn.configure(state="disabled")
        self.fullscreen_btn.configure(state="disabled")
        self.live_badge.configure(text="○ BEKLEMEDE", text_color=UI["muted"])
        self.fps_chip.configure(text="FPS  --")
        self.status_label.configure(text="Yayın durduruldu")

        if self.is_fullscreen:
            self.exit_fullscreen()

        self.video_label.configure(
            image=None,
            text="📷\n\nKamera bağlantısı kesildi\n\n"
                 "Yeniden başlatmak için  ▶  Yayını Başlat'a tıklayın"
        )

    # ── Tam ekran ────────────────────────────────────────────────────────

    def on_video_double_click(self, event=None):
        """Double-click on video toggles fullscreen"""
        self.toggle_fullscreen()

    def toggle_fullscreen(self):
        """Toggle fullscreen video display"""
        if not self.is_streaming:
            return

        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.is_fullscreen = True
            self.attributes("-fullscreen", True)
            self.header.grid_remove()
            self.sidebar.grid_remove()
            self.status_frame.grid_remove()

            # Sahne tüm ekranı kaplasın, görüntü ekrana sığdırılır
            self.stage.grid(row=0, column=0, rowspan=3, columnspan=2,
                            padx=0, pady=0, sticky="nsew")
            self.stage.configure(corner_radius=0, border_width=0, fg_color=UI["stage"])
            self.video_label.grid_configure(padx=0, pady=0)
            self.video_label.configure(corner_radius=0)
            self.grid_rowconfigure(0, weight=1)
            self.fullscreen_btn.configure(text="⛶   Tam Ekrandan Çık")

    def exit_fullscreen(self, event=None):
        """Exit fullscreen mode"""
        if not self.is_fullscreen:
            return

        self.is_fullscreen = False
        self.attributes("-fullscreen", False)
        self.grid_rowconfigure(0, weight=0)
        self.header.grid()
        self.sidebar.grid()
        self.status_frame.grid()

        self.stage.grid(row=1, column=1, rowspan=1, columnspan=1,
                        padx=(0, 14), pady=(14, 0), sticky="nsew")
        self.stage.configure(corner_radius=18, border_width=1, fg_color=UI["card"])
        self.video_label.grid_configure(padx=10, pady=10)
        self.video_label.configure(corner_radius=14)
        self.fullscreen_btn.configure(text="⛶   Tam Ekran")
        self.status_label.configure(text="Normal mod")

    # ── Ekran görüntüsü ──────────────────────────────────────────────────

    def take_screenshot(self):
        """Take a screenshot"""
        if self.current_frame is not None:
            filepath, message = self.screenshot_manager.save_screenshot(
                self.current_frame,
                self.camera_manager.current_camera_id
            )
            if filepath:
                self.status_label.configure(text=message)
                # Buton üzerinde kısa geri bildirim
                self.screenshot_btn.configure(text="✓   Kaydedildi!")
                self.after(1200, lambda: self.screenshot_btn.configure(
                    text="📸   Ekran Görüntüsü"))
            else:
                messagebox.showerror("Hata", "Ekran görüntüsü kaydedilemedi")
        else:
            messagebox.showwarning("Uyarı", "Kaydedilecek kare yok")

    def on_closing(self):
        """Handle application closing"""
        self.is_streaming = False
        self.camera_manager.release_all()
        self.destroy()


def main():
    app = WebcamApp()
    app.mainloop()


if __name__ == "__main__":
    main()
