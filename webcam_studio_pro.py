"""
Webcam Studio Pro — Modern Premium Arayüz
Kayıt, Efektler, Hareket Algılama, Zamanlı Kayıt, Sanal Kamera
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

from advanced_features import (
    RecordingManager, TimerManager,
    MotionDetector, ScheduledRecorder
)
from camera_filters import CameraFilters
from virtual_camera import BroadcastManager


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
    "info":          "#38bdf8",
    "info_hover":    "#0ea5e9",
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

    def _get_camera_name(self, cap, index):
        """Get camera name from driver"""
        try:
            name = cap.getBackendName()
            if name and name != "":
                return f"{name} ({index})"
        except Exception:
            pass

        # Try to get device name via DirectShow
        try:
            import subprocess
            result = subprocess.run(
                ['powershell', '-Command',
                 f"Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | Select-Object -Property FriendlyName | ConvertTo-Json"],
                capture_output=True, text=True, timeout=3
            )
            if result.stdout:
                import json
                devices = json.loads(result.stdout)
                if isinstance(devices, list) and index < len(devices):
                    name = devices[index].get('FriendlyName', '')
                    if name:
                        return name
                elif isinstance(devices, dict):
                    name = devices.get('FriendlyName', '')
                    if name:
                        return name
        except Exception:
            pass

        return f"Kamera {index}"

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
                                name = self._get_camera_name(cap, i)
                                self.cameras[i] = {
                                    "name": name,
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
        return [cam["name"] for cam in self.cameras.values()]

    def get_camera_ids(self):
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
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def save_screenshot(self, frame, camera_id):
        if frame is None:
            return None, "Kaydedilecek kare yok"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_cam{camera_id}_{timestamp}.png"
        filepath = os.path.join(self.save_dir, filename)

        cv2.imwrite(filepath, frame)
        return filepath, f"Kaydedildi: {filename}"


class EnhancedWebcamApp(ctk.CTk):
    """Enhanced application class — premium redesign"""

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

        self.title("Webcam Studio Pro")
        self.geometry("1440x900")
        self.minsize(1200, 780)

        ctk.set_appearance_mode("dark")
        self.configure(fg_color=UI["bg"])

        self.camera_manager = CameraManager()
        self.screenshot_manager = ScreenshotManager()
        self.recording_manager = RecordingManager()
        self.filter_manager = CameraFilters()
        self.motion_detector = MotionDetector()
        self.scheduled_recorder = ScheduledRecorder(self.recording_manager)
        self.timer_manager = TimerManager()
        self.broadcast_manager = BroadcastManager()

        self.is_streaming = False
        self.current_frame = None
        self.frame_count = 0
        self.auto_camera_selected = False
        self.is_fullscreen = False
        self.last_time = time.time()
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
        self.f_title = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        self.f_body = ctk.CTkFont(family="Segoe UI", size=13)
        self.f_small = ctk.CTkFont(family="Segoe UI", size=11)
        self.f_chip = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        self.f_btn = ctk.CTkFont(family="Segoe UI", size=13, weight="bold")

    # ── UI kurulumu ──────────────────────────────────────────────────────

    def setup_ui(self):
        """Setup the user interface"""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.setup_header()
        self.setup_sidebar()
        self.setup_stage()
        self.setup_status_bar()

    def _card(self, title, icon=""):
        """Create a titled card inside the sidebar, return its inner frame"""
        card = ctk.CTkFrame(
            self.sidebar, fg_color=UI["card"], corner_radius=14,
            border_width=1, border_color=UI["card_border"]
        )
        card.pack(fill="x", padx=6, pady=(0, 10))

        ctk.CTkLabel(
            card, text=f"{icon}  {title}", font=self.f_title,
            text_color=UI["muted"], anchor="w"
        ).pack(fill="x", padx=14, pady=(10, 4))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=(0, 12))
        return inner

    def _dropdown(self, parent, values, command=None, height=34):
        """Styled option menu"""
        return ctk.CTkOptionMenu(
            parent, values=values, command=command,
            height=height, corner_radius=10, font=self.f_body,
            fg_color=UI["accent_soft"], button_color=UI["accent"],
            button_hover_color=UI["accent_hover"], dropdown_fg_color=UI["card"]
        )

    def setup_header(self):
        """Top header bar with logo and live indicator chips"""
        self.header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color=UI["panel"])
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.header.grid_propagate(False)

        logo_box = ctk.CTkFrame(self.header, fg_color="transparent")
        logo_box.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            logo_box, text="●", font=ctk.CTkFont(size=20), text_color=UI["accent"]
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            logo_box, text="WEBCAM STUDIO", font=self.f_logo, text_color=UI["text"]
        ).pack(side="left")

        ctk.CTkLabel(
            logo_box, text=" PRO", font=self.f_logo, text_color=UI["accent"]
        ).pack(side="left")

        # Sağ taraf bilgi çipleri
        self.live_badge = ctk.CTkLabel(
            self.header, text="○ BEKLEMEDE", font=self.f_chip,
            text_color=UI["muted"], fg_color=UI["chip"],
            corner_radius=14, width=118, height=28
        )
        self.live_badge.pack(side="right", padx=(6, 20), pady=16)

        self.rec_chip = ctk.CTkLabel(
            self.header, text="● KAYIT YOK", font=self.f_chip,
            text_color=UI["muted"], fg_color=UI["chip"],
            corner_radius=14, width=120, height=28
        )
        self.rec_chip.pack(side="right", padx=6, pady=16)

        self.fps_chip = ctk.CTkLabel(
            self.header, text="FPS  --", font=self.f_chip,
            text_color=UI["text"], fg_color=UI["chip"],
            corner_radius=14, width=86, height=28
        )
        self.fps_chip.pack(side="right", padx=6, pady=16)

        self.frame_chip = ctk.CTkLabel(
            self.header, text="Kare  0", font=self.f_chip,
            text_color=UI["text"], fg_color=UI["chip"],
            corner_radius=14, width=110, height=28
        )
        self.frame_chip.pack(side="right", padx=6, pady=16)

        self.res_chip = ctk.CTkLabel(
            self.header, text="—", font=self.f_chip,
            text_color=UI["text"], fg_color=UI["chip"],
            corner_radius=14, width=126, height=28
        )
        self.res_chip.pack(side="right", padx=6, pady=16)

    def setup_sidebar(self):
        """Left scrollable control panel built from cards"""
        self.sidebar = ctk.CTkScrollableFrame(
            self, width=318, corner_radius=0, fg_color="transparent",
            scrollbar_button_color=UI["card_border"],
            scrollbar_button_hover_color=UI["accent_soft"]
        )
        self.sidebar.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(12, 0))

        # ── Kamera kartı ──
        cam_box = self._card("KAMERA", "📷")

        self.camera_menu = self._dropdown(
            cam_box, ["Kamera algılanamadı"], self.on_camera_select, height=36
        )
        self.camera_menu.pack(fill="x", pady=(0, 6))

        row = ctk.CTkFrame(cam_box, fg_color="transparent")
        row.pack(fill="x")
        row.grid_columnconfigure((0, 1), weight=1)

        self.refresh_btn = ctk.CTkButton(
            row, text="🔄  Yenile", command=self.detect_cameras,
            height=32, corner_radius=10, font=self.f_body,
            fg_color="transparent", hover_color=UI["accent_soft"],
            border_width=1, border_color=UI["card_border"], text_color=UI["muted"]
        )
        self.refresh_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.res_menu = self._dropdown(
            row, list(self.RESOLUTION_OPTIONS.keys()), self.on_resolution_change, height=32
        )
        self.res_menu.set("Otomatik")
        self.res_menu.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # ── Kontroller kartı ──
        ctl_box = self._card("KONTROLLER", "🎛️")

        self.stream_btn = ctk.CTkButton(
            ctl_box, text="▶   Yayını Başlat", command=self.toggle_stream_btn,
            height=44, corner_radius=12, font=self.f_btn,
            fg_color=UI["success"], hover_color=UI["success_hover"]
        )
        self.stream_btn.pack(fill="x", pady=(0, 8))

        shot_row = ctk.CTkFrame(ctl_box, fg_color="transparent")
        shot_row.pack(fill="x", pady=(0, 8))
        shot_row.grid_columnconfigure(0, weight=1)

        self.screenshot_btn = ctk.CTkButton(
            shot_row, text="📸  Ekran Görüntüsü", command=self.take_screenshot,
            height=38, corner_radius=10, font=self.f_btn,
            fg_color=UI["warning"], hover_color=UI["warning_hover"],
            text_color="#1a1a1a", state="disabled"
        )
        self.screenshot_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.timer_entry = ctk.CTkEntry(
            shot_row, width=52, height=38, corner_radius=10,
            placeholder_text="0 sn", font=self.f_small,
            fg_color=UI["accent_soft"], border_color=UI["card_border"]
        )
        self.timer_entry.grid(row=0, column=1)

        self.record_btn = ctk.CTkButton(
            ctl_box, text="⏺   Kayıt Başlat", command=self.toggle_recording,
            height=38, corner_radius=10, font=self.f_btn,
            fg_color=UI["accent_soft"], hover_color=UI["accent_hover"],
            border_width=1, border_color=UI["card_border"], state="disabled"
        )
        self.record_btn.pack(fill="x", pady=(0, 8))

        self.fullscreen_btn = ctk.CTkButton(
            ctl_box, text="⛶   Tam Ekran", command=self.toggle_fullscreen,
            height=38, corner_radius=10, font=self.f_btn,
            fg_color=UI["accent"], hover_color=UI["accent_hover"], state="disabled"
        )
        self.fullscreen_btn.pack(fill="x")

        ctk.CTkLabel(
            ctl_box, text="İpucu: Görüntüye çift tıklayarak tam ekrana geçin",
            font=self.f_small, text_color=UI["muted"], wraplength=250, justify="left"
        ).pack(fill="x", pady=(8, 0))

        # ── Hareket algılama kartı ──
        motion_box = self._card("HAREKET ALGILAMA", "🏃")

        self.motion_btn = ctk.CTkButton(
            motion_box, text="Hareket: Kapalı", command=self.toggle_motion,
            height=34, corner_radius=10, font=self.f_btn,
            fg_color=UI["accent_soft"], hover_color=UI["accent_hover"],
            border_width=1, border_color=UI["card_border"], state="disabled"
        )
        self.motion_btn.pack(fill="x", pady=(0, 8))

        sens_row = ctk.CTkFrame(motion_box, fg_color="transparent")
        sens_row.pack(fill="x")
        ctk.CTkLabel(sens_row, text="Hassasiyet", font=self.f_small,
                     text_color=UI["muted"]).pack(side="left")
        self.sensitivity_slider = ctk.CTkSlider(
            sens_row, from_=10, to=100, number_of_steps=9,
            command=self.on_sensitivity_change,
            button_color=UI["accent"], button_hover_color=UI["accent_hover"],
            progress_color=UI["accent"], fg_color=UI["accent_soft"]
        )
        self.sensitivity_slider.set(25)
        self.sensitivity_slider.pack(side="left", fill="x", expand=True, padx=(8, 0))

        # ── Zamanlı kayıt kartı ──
        sched_box = self._card("ZAMANLI KAYIT", "⏰")

        self.schedule_type_menu = self._dropdown(
            sched_box, ["Hareket ile", "Zamanlayıcı ile"], height=32
        )
        self.schedule_type_menu.pack(fill="x", pady=(0, 6))

        dur_row = ctk.CTkFrame(sched_box, fg_color="transparent")
        dur_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(dur_row, text="Süre", font=self.f_small,
                     text_color=UI["muted"]).pack(side="left")
        self.duration_entry = ctk.CTkEntry(
            dur_row, width=52, height=30, corner_radius=8, placeholder_text="10",
            font=self.f_small, fg_color=UI["accent_soft"], border_color=UI["card_border"]
        )
        self.duration_entry.pack(side="left", padx=(6, 12))
        ctk.CTkLabel(dur_row, text="Aralık", font=self.f_small,
                     text_color=UI["muted"]).pack(side="left")
        self.interval_entry = ctk.CTkEntry(
            dur_row, width=52, height=30, corner_radius=8, placeholder_text="30",
            font=self.f_small, fg_color=UI["accent_soft"], border_color=UI["card_border"]
        )
        self.interval_entry.pack(side="left", padx=(6, 0))

        self.schedule_btn = ctk.CTkButton(
            sched_box, text="Zamanlamayı Başlat", command=self.toggle_schedule,
            height=34, corner_radius=10, font=self.f_btn,
            fg_color=UI["accent_soft"], hover_color=UI["accent_hover"],
            border_width=1, border_color=UI["card_border"], state="disabled"
        )
        self.schedule_btn.pack(fill="x")

        # ── Sanal kamera kartı ──
        cast_box = self._card("SANAL KAMERA YAYINI", "📡")

        cast_row = ctk.CTkFrame(cast_box, fg_color="transparent")
        cast_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(cast_row, text="Çözünürlük", font=self.f_small,
                     text_color=UI["muted"]).pack(side="left")
        self.broadcast_res_menu = self._dropdown(
            cast_row, ["640x480", "800x600", "1280x720", "1920x1080"], height=30
        )
        self.broadcast_res_menu.set("640x480")
        self.broadcast_res_menu.pack(side="left", fill="x", expand=True, padx=(8, 0))

        self.broadcast_btn = ctk.CTkButton(
            cast_box, text="📡  Yayını Başlat", command=self.toggle_broadcast,
            height=36, corner_radius=10, font=self.f_btn,
            fg_color=UI["info"], hover_color=UI["info_hover"], text_color="#0b1220",
            state="normal" if self.broadcast_manager.virtual_cam.available else "disabled"
        )
        self.broadcast_btn.pack(fill="x")

        self.broadcast_stats_label = ctk.CTkLabel(
            cast_box, text="", font=self.f_small, text_color=UI["muted"]
        )
        self.broadcast_stats_label.pack(fill="x", pady=(4, 0))

        # ── Efekt & çerçeve kartı ──
        fx_box = self._card("EFEKT & ÇERÇEVE", "✨")

        ctk.CTkLabel(fx_box, text="Efekt", font=self.f_small,
                     text_color=UI["muted"], anchor="w").pack(fill="x")
        self.effect_menu = self._dropdown(
            fx_box, self.filter_manager.get_effect_names(), self.on_effect_select, height=32
        )
        self.effect_menu.pack(fill="x", pady=(2, 6))

        ctk.CTkLabel(fx_box, text="Çerçeve", font=self.f_small,
                     text_color=UI["muted"], anchor="w").pack(fill="x")
        self.frame_menu = self._dropdown(
            fx_box, self.filter_manager.get_frame_names(), self.on_frame_select, height=32
        )
        self.frame_menu.pack(fill="x", pady=(2, 6))

        load_row = ctk.CTkFrame(fx_box, fg_color="transparent")
        load_row.pack(fill="x")
        load_row.grid_columnconfigure((0, 1), weight=1)

        self.load_frame_btn = ctk.CTkButton(
            load_row, text="🖼️ PNG Çerçeve", command=self.load_custom_frame,
            height=32, corner_radius=10, font=self.f_small,
            fg_color="transparent", hover_color=UI["accent_soft"],
            border_width=1, border_color=UI["card_border"], text_color=UI["muted"]
        )
        self.load_frame_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.load_bg_btn = ctk.CTkButton(
            load_row, text="🏞️ Arka Plan", command=self.load_custom_background,
            height=32, corner_radius=10, font=self.f_small,
            fg_color="transparent", hover_color=UI["accent_soft"],
            border_width=1, border_color=UI["card_border"], text_color=UI["muted"]
        )
        self.load_bg_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # ── Çerçeve rengi kartı ──
        color_box = self._card("ÇERÇEVE RENGİ", "🎨")

        hex_row = ctk.CTkFrame(color_box, fg_color="transparent")
        hex_row.pack(fill="x", pady=(0, 8))

        self.color_menu = self._dropdown(
            hex_row, self.filter_manager.get_bg_colors(), self.on_color_select, height=30
        )
        self.color_menu.set("Yesil")
        self.color_menu.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.hex_entry = ctk.CTkEntry(
            hex_row, width=78, height=30, corner_radius=8, placeholder_text="#00C800",
            font=self.f_small, fg_color=UI["accent_soft"], border_color=UI["card_border"]
        )
        self.hex_entry.insert(0, "#00C800")
        self.hex_entry.pack(side="left", padx=(0, 6))

        self.hex_apply_btn = ctk.CTkButton(
            hex_row, text="✓", width=32, height=30, corner_radius=8,
            command=self.apply_hex_color, font=self.f_chip,
            fg_color=UI["accent"], hover_color=UI["accent_hover"]
        )
        self.hex_apply_btn.pack(side="left")

        # Renk paleti
        palette_row = ctk.CTkFrame(color_box, fg_color="transparent")
        palette_row.pack(fill="x")

        palette_colors = [
            ("#00C800", "Yesil"), ("#0064FF", "Mavi"), ("#C80000", "Kirmizi"),
            ("#D4DC00", "Sari"), ("#B400B4", "Mor"), ("#FF8C00", "Turuncu"),
            ("#FF64B4", "Pembe"), ("#FFFFFF", "Beyaz"), ("#000000", "Siyah")
        ]

        for i, (hex_code, name) in enumerate(palette_colors):
            btn = ctk.CTkButton(
                palette_row, text="", width=26, height=26, corner_radius=8,
                fg_color=hex_code, hover_color=hex_code,
                border_width=1, border_color=UI["card_border"],
                command=lambda h=hex_code, n=name: self.on_palette_click(h, n)
            )
            btn.grid(row=0, column=i, padx=2, pady=2)

    def setup_stage(self):
        """Main video stage with rounded dark canvas"""
        self.stage = ctk.CTkFrame(
            self, fg_color=UI["card"], corner_radius=18,
            border_width=1, border_color=UI["card_border"]
        )
        self.stage.grid(row=1, column=1, padx=(10, 14), pady=(12, 0), sticky="nsew")
        self.stage.grid_columnconfigure(0, weight=1)
        self.stage.grid_rowconfigure(0, weight=1)

        self.video_label = ctk.CTkLabel(
            self.stage,
            text="🎥\n\nKamera bağlantısı bekleniyor...\n\n"
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
        self.status_frame = ctk.CTkFrame(self, height=34, corner_radius=0, fg_color=UI["panel"])
        self.status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
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

            self.motion_btn.configure(state="normal")
            self.schedule_btn.configure(state="normal")

            # İlk kamerayı otomatik seç ve yayını başlat
            self.on_camera_select(camera_names[0])
        else:
            self.camera_menu.configure(values=["Kamera bulunamadı"])
            self.camera_menu.set("Kamera bulunamadı")
            self.status_label.configure(text="Kamera bulunamadı")

    def on_camera_select(self, selection):
        """Handle camera selection — open it and auto-start the preview"""
        for cam_id, cam_info in self.camera_manager.cameras.items():
            if cam_info["name"] == selection or selection in cam_info["name"]:
                if self.is_streaming:
                    self.stop_stream()

                res = self.RESOLUTION_OPTIONS.get(self.res_menu.get())
                self.status_label.configure(text=f"{selection} açılıyor...")
                self.update()

                if self.camera_manager.open_camera(cam_id, res):
                    w, h = cam_info["resolution"]
                    self._set_resolution_info(w, h)
                    self.auto_camera_selected = True
                    self.status_label.configure(text=f"{selection} seçildi")
                    # Görüntü alınabiliyorsa yayını otomatik başlat
                    self.start_stream()
                else:
                    self.status_label.configure(
                        text=f"{selection} açılamadı — başka bir uygulama kullanıyor olabilir")
                return

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

    def toggle_stream_btn(self):
        """Single button start/stop toggle"""
        if self.is_streaming:
            self.stop_stream()
        else:
            self.start_stream()

    def start_stream(self):
        """Start video stream"""
        cam_id = self.camera_manager.current_camera_id
        if cam_id is None:
            # Try to auto-select first camera
            if self.camera_manager.cameras:
                cam_id = list(self.camera_manager.cameras.keys())[0]
            else:
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
        self.frame_count = 0
        self._fail_count = 0
        self.stream_btn.configure(
            text="⏹   Yayını Durdur",
            fg_color=UI["danger"], hover_color=UI["danger_hover"]
        )
        self.screenshot_btn.configure(state="normal")
        self.record_btn.configure(state="normal")
        self.motion_btn.configure(state="normal")
        self.schedule_btn.configure(state="normal")
        self.fullscreen_btn.configure(state="normal")
        self.live_badge.configure(text="●  CANLI", text_color=UI["danger"])
        self.status_label.configure(text="Yayın başlatıldı")

        self.last_time = time.time()
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
            self.frame_count += 1

            # Apply filters
            frame = self.filter_manager.apply(frame)

            # Motion detection
            frame, motion_detected = self.motion_detector.detect_motion(frame)

            # Scheduled recording check
            self.scheduled_recorder.check_time_based_recording(frame)

            # Write to recording if active
            if self.recording_manager.is_recording:
                self.recording_manager.write_frame(frame)

            # Send to virtual camera / broadcast
            if self.broadcast_manager.is_broadcasting:
                self.broadcast_manager.send_frame(frame)

            # Update scheduled recording status
            if self.scheduled_recorder.is_scheduled:
                if self.scheduled_recorder.is_recording_active:
                    self.rec_chip.configure(text="● ZAMANLI", text_color=UI["warning"])
                elif self.recording_manager.is_recording:
                    self.rec_chip.configure(text="● KAYITTA", text_color=UI["danger"])

            # Update broadcast stats
            if self.broadcast_manager.is_broadcasting:
                self.broadcast_stats_label.configure(
                    text=self.broadcast_manager.get_stats(),
                    text_color=UI["success"]
                )

            # Convert and display — aspect-fit, kırpılmadan sığdır
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            pad = 4 if not self.is_fullscreen else 0
            box_w = self.video_label.winfo_width() - pad
            box_h = self.video_label.winfo_height() - pad
            img = self._fit_to_box(img, box_w, box_h)

            imgtk = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.video_label.configure(image=imgtk, text="")
            self.video_label.image = imgtk

            current_time = time.time()
            fps = 1 / (current_time - self.last_time) if (current_time - self.last_time) > 0 else 0
            self.last_time = current_time

            self.fps_chip.configure(text=f"FPS  {fps:.0f}")
            self.frame_chip.configure(text=f"Kare  {self.frame_count}")
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

        if self.recording_manager.is_recording:
            self.toggle_recording()

        if self.scheduled_recorder.is_scheduled:
            self.scheduled_recorder.stop_schedule()
            self.schedule_btn.configure(text="Zamanlamayı Başlat", fg_color=UI["accent_soft"])

        if self.broadcast_manager.is_broadcasting:
            self.broadcast_manager.stop_broadcast()
            self.broadcast_btn.configure(text="📡  Yayını Başlat", fg_color=UI["info"])
            self.broadcast_stats_label.configure(text="", text_color=UI["muted"])

        if self.is_fullscreen:
            self.exit_fullscreen()

        self.stream_btn.configure(
            text="▶   Yayını Başlat",
            fg_color=UI["success"], hover_color=UI["success_hover"]
        )
        self.screenshot_btn.configure(state="disabled")
        self.record_btn.configure(state="disabled")
        self.motion_btn.configure(state="disabled")
        self.schedule_btn.configure(state="disabled")
        self.fullscreen_btn.configure(state="disabled")
        self.live_badge.configure(text="○ BEKLEMEDE", text_color=UI["muted"])
        self.rec_chip.configure(text="● KAYIT YOK", text_color=UI["muted"])
        self.fps_chip.configure(text="FPS  --")
        self.status_label.configure(text="Yayın durduruldu")

        self.video_label.configure(
            image=None,
            text="🎥\n\nKamera bağlantısı kesildi\n\n"
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
                        padx=(10, 14), pady=(12, 0), sticky="nsew")
        self.stage.configure(corner_radius=18, border_width=1, fg_color=UI["card"])
        self.video_label.grid_configure(padx=10, pady=10)
        self.video_label.configure(corner_radius=14)
        self.fullscreen_btn.configure(text="⛶   Tam Ekran")
        self.status_label.configure(text="Normal mod")

    # ── Ekran görüntüsü ──────────────────────────────────────────────────

    def take_screenshot(self):
        """Take a screenshot with optional timer"""
        timer_str = self.timer_entry.get()
        try:
            timer_seconds = int(timer_str) if timer_str else 0
        except ValueError:
            timer_seconds = 0

        if timer_seconds > 0:
            self.status_label.configure(text=f"Ekran görüntüsü {timer_seconds} saniye sonra...")
            self.timer_manager.set_timer(timer_seconds)
            self.timer_manager.start_timer(self._do_screenshot)
        else:
            self._do_screenshot()

    def _do_screenshot(self):
        """Actually take the screenshot"""
        if self.current_frame is not None:
            filepath, message = self.screenshot_manager.save_screenshot(
                self.current_frame, self.camera_manager.current_camera_id
            )
            if filepath:
                self.status_label.configure(text=message)
                self.screenshot_btn.configure(text="✓  Kaydedildi!")
                self.after(1200, lambda: self.screenshot_btn.configure(
                    text="📸  Ekran Görüntüsü"))
        else:
            self.status_label.configure(text="Kaydedilecek kare yok")

    # ── Kayıt / hareket / zamanlama ──────────────────────────────────────

    def toggle_recording(self):
        """Toggle video recording"""
        if self.recording_manager.is_recording:
            self.recording_manager.stop_recording()
            self.record_btn.configure(text="⏺   Kayıt Başlat", fg_color=UI["accent_soft"])
            self.rec_chip.configure(text="● KAYIT YOK", text_color=UI["muted"])
            self.status_label.configure(text="Kayıt durduruldu")
        else:
            if self.current_frame is not None:
                success = self.recording_manager.start_recording(
                    self.current_frame, self.camera_manager.current_camera_id
                )
                if success:
                    self.record_btn.configure(text="⏹   Kayıt Durdur", fg_color=UI["danger"])
                    self.rec_chip.configure(text="● KAYITTA", text_color=UI["danger"])
                    self.status_label.configure(text="Kayıt başlatıldı")

    def toggle_motion(self):
        """Toggle motion detection"""
        is_enabled = self.motion_detector.toggle_detection()
        if is_enabled:
            self.motion_btn.configure(text="Hareket: Aktif", fg_color=UI["success"])
            self.status_label.configure(text="Hareket algılama açıldı")
        else:
            self.motion_btn.configure(text="Hareket: Kapalı", fg_color=UI["accent_soft"])
            self.status_label.configure(text="Hareket algılama kapatıldı")

    def on_sensitivity_change(self, value):
        """Handle sensitivity slider change"""
        self.motion_detector.set_sensitivity(int(value))

    def toggle_schedule(self):
        """Toggle scheduled recording"""
        if self.scheduled_recorder.is_scheduled:
            self.scheduled_recorder.stop_schedule()
            self.motion_detector.on_motion_callback = None
            self.schedule_btn.configure(text="Zamanlamayı Başlat", fg_color=UI["accent_soft"])
            self.status_label.configure(text="Zamanlama durduruldu")
            self.rec_chip.configure(text="● KAYIT YOK", text_color=UI["muted"])
        else:
            # Get settings
            schedule_type = "motion" if "Hareket" in self.schedule_type_menu.get() else "time"

            try:
                duration = int(self.duration_entry.get()) if self.duration_entry.get() else 10
            except ValueError:
                duration = 10

            try:
                interval = int(self.interval_entry.get()) if self.interval_entry.get() else 30
            except ValueError:
                interval = 30

            self.scheduled_recorder.set_duration(duration)
            self.scheduled_recorder.set_interval(interval)
            self.scheduled_recorder.start_schedule(
                self.camera_manager.current_camera_id, schedule_type
            )

            # Connect motion detector to scheduled recorder
            if schedule_type == "motion":
                self.motion_detector.on_motion_callback = self.scheduled_recorder.on_motion_detected

            self.schedule_btn.configure(text="Zamanlamayı Durdur", fg_color=UI["danger"])
            type_text = "Hareket" if schedule_type == "motion" else f"Her {interval}sn"
            self.status_label.configure(
                text=f"Zamanlama başlatıldı — {type_text}, {duration}sn kayıt"
            )

    def toggle_broadcast(self):
        """Toggle virtual camera broadcast"""
        if self.broadcast_manager.is_broadcasting:
            self.broadcast_manager.stop_broadcast()
            self.broadcast_btn.configure(text="📡  Yayını Başlat", fg_color=UI["info"])
            self.broadcast_stats_label.configure(text="", text_color=UI["muted"])
            self.status_label.configure(text="Yayın durduruldu")
        else:
            # Parse resolution
            res_text = self.broadcast_res_menu.get()
            width, height = map(int, res_text.split('x'))

            success, message = self.broadcast_manager.start_broadcast(width, height, 30)
            if success:
                self.broadcast_btn.configure(text="⏹  Yayını Durdur", fg_color=UI["danger"])
                self.status_label.configure(text=f"Yayın başlatıldı — {message}")
            else:
                self.status_label.configure(text=f"Yayın hatası: {message}")
                messagebox.showerror("Yayın Hatası", message)

    # ── Efekt / çerçeve / renk ───────────────────────────────────────────

    def on_effect_select(self, effect_name):
        """Handle effect selection"""
        self.filter_manager.set_effect(effect_name)
        self.status_label.configure(text=f"Efekt: {effect_name}")

    def on_frame_select(self, frame_name):
        """Handle frame selection"""
        self.filter_manager.set_frame(frame_name)
        self.status_label.configure(text=f"Çerçeve: {frame_name}")

    def load_custom_frame(self):
        """Load custom PNG frame and add to filters folder"""
        file_path = filedialog.askopenfilename(
            title="Çerçeve PNG Seç",
            filetypes=[("PNG dosyaları", "*.png"), ("Tüm dosyalar", "*.*")]
        )
        if file_path:
            import shutil
            filters_dir = os.path.join(os.path.dirname(__file__), "filters")
            os.makedirs(filters_dir, exist_ok=True)
            dest = os.path.join(filters_dir, os.path.basename(file_path))
            shutil.copy2(file_path, dest)

            # Reload PNG frames
            self.filter_manager.load_png_filters()
            self.frame_menu.configure(values=self.filter_manager.get_frame_names())

            # Select the new frame
            name = f"PNG: {os.path.splitext(os.path.basename(file_path))[0]}"
            self.frame_menu.set(name)
            self.filter_manager.set_frame(name)
            self.status_label.configure(text=f"PNG çerçeve eklendi: {os.path.basename(file_path)}")

    def load_custom_background(self):
        """Load custom background for greenscreen"""
        if not hasattr(self.filter_manager, "load_background"):
            messagebox.showinfo("Bilgi", "Arka plan özelliği bu sürümde desteklenmiyor.")
            return

        file_path = filedialog.askopenfilename(
            title="Arka Plan Resmi Seç",
            filetypes=[("Resim dosyaları", "*.png *.jpg *.jpeg *.bmp"), ("Tüm dosyalar", "*.*")]
        )
        if file_path:
            if self.filter_manager.load_background(file_path):
                self.status_label.configure(text=f"Arka plan yüklendi: {os.path.basename(file_path)}")
            else:
                messagebox.showerror("Hata", "Arka plan yüklenemedi!")

    def on_color_select(self, color_name):
        """Handle background color selection"""
        if self.filter_manager.set_bg_color(color_name):
            self.status_label.configure(text=f"Çerçeve rengi: {color_name}")

    def apply_hex_color(self):
        """Apply hex color from entry"""
        hex_code = self.hex_entry.get().strip()
        if not hex_code.startswith("#"):
            hex_code = "#" + hex_code
        try:
            hex_code = hex_code.lstrip("#")
            if len(hex_code) == 6:
                r = int(hex_code[0:2], 16)
                g = int(hex_code[2:4], 16)
                b = int(hex_code[4:6], 16)
                self.filter_manager.bg_color = (b, g, r)  # BGR for OpenCV
                self.filter_manager.bg_color_name = f"#{hex_code}"
                self.status_label.configure(text=f"Renk uygulandı: #{hex_code}")
            else:
                messagebox.showerror("Hata", "Geçersiz hex kodu! 6 karakter olmalı.")
        except ValueError:
            messagebox.showerror("Hata", "Geçersiz hex kodu!")

    def on_palette_click(self, hex_code, color_name):
        """Handle palette color click"""
        self.hex_entry.delete(0, "end")
        self.hex_entry.insert(0, hex_code)
        self.on_color_select(color_name)

    def on_closing(self):
        """Handle application closing"""
        self.is_streaming = False
        if self.recording_manager.is_recording:
            self.recording_manager.stop_recording()
        if self.scheduled_recorder.is_scheduled:
            self.scheduled_recorder.stop_schedule()
        if self.broadcast_manager.is_broadcasting:
            self.broadcast_manager.stop_broadcast()
        self.camera_manager.release_all()
        self.destroy()


def main():
    app = EnhancedWebcamApp()
    app.mainloop()


if __name__ == "__main__":
    main()
