"""
Camera Filters Module - Key Color Based PNG Frames
Magenta (#FF00FF) = Camera shows through
Other colors = Frame decoration
Green/background = Outside frame (greenscreen)
"""

import cv2
import numpy as np
import os


# KEY COLOR: Magenta (255, 0, 255) in RGB = Camera window
KEY_COLOR_RGB = (255, 0, 255)
KEY_COLOR_BGR = (255, 0, 255)
KEY_THRESHOLD = 60  # Color matching tolerance


class CameraFilters:
    """Camera filters with key-color based PNG frame system"""

    def __init__(self):
        # Filter system (effects applied to the whole image)
        self.current_filter = "Yok"

        # Frame system (shape/background applied after filter)
        self.current_frame = "Yok"
        self.frame_image = None
        self.frame_path = None

        # Background color settings (BGR format)
        self.bg_color = (0, 200, 0)  # Default green
        self.bg_color_name = "Yesil"

        # Filter definitions (effects)
        self.effects = {
            "Yok": self.no_effect,
            "Eski TV": self.old_tv,
            "VHS Kayit": self.vhs_effect,
            "Sinyal Kaybi": self.signal_lost,
            "Scanlines": self.scanlines,
            "Retro": self.retro,
            "Sinema": self.cinema,
            "Gece Gorushu": self.night_vision,
            "Termal": self.thermal,
            "Pop Art": self.pop_art,
            "Komik Ayna": self.funny_mirror,
        }

        # Built-in frame shapes
        self.frames = {
            "Yok": self.no_frame,
            "Yuvarlak": self.circle_frame,
            "Oval": self.oval_frame,
            "Kare": self.square_frame,
            "Kalp": self.heart_shape,
            "Yildiz": self.star_shape,
        }

        # PNG frames loaded from filters folder
        self.png_frames = {}
        self.load_png_filters()

    def get_effect_names(self):
        return list(self.effects.keys())

    def get_frame_names(self):
        return list(self.frames.keys()) + list(self.png_frames.keys())

    def set_effect(self, effect_name):
        if effect_name in self.effects:
            self.current_filter = effect_name
            return True
        return False

    def set_frame(self, frame_name):
        if frame_name in self.frames or frame_name in self.png_frames:
            self.current_frame = frame_name
            return True
        return False

    def apply(self, frame):
        """Apply filter first, then frame on top"""
        result = frame.copy()

        # Step 1: Apply effect/filter
        if self.current_filter in self.effects:
            result = self.effects[self.current_filter](result)

        # Step 2: Apply frame shape (on top of filtered image)
        if self.current_frame in self.frames:
            result = self.frames[self.current_frame](result)
        elif self.current_frame in self.png_frames:
            result = self.apply_png_frame(result, self.current_frame)

        return result

    # ==================== EFFECTS ====================

    def no_effect(self, frame):
        return frame

    def old_tv(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        noise = np.random.normal(0, 25, gray.shape).astype(np.uint8)
        noisy = cv2.add(gray, noise)
        for i in range(0, frame.shape[0], 2):
            noisy[i] = np.clip(noisy[i] - 30, 0, 255)
        result = cv2.cvtColor(noisy, cv2.COLOR_GRAY2BGR)
        result[:, :, 0] = np.clip(result[:, :, 0] + 10, 0, 255)
        result = self._add_vignette(result)
        return result

    def vhs_effect(self, frame):
        result = frame.copy()
        result[:, :, 0] = cv2.GaussianBlur(result[:, :, 0], (3, 3), 0)
        num_lines = np.random.randint(3, 8)
        for _ in range(num_lines):
            y = np.random.randint(0, frame.shape[0])
            thickness = np.random.randint(1, 4)
            result[y:y + thickness] = np.clip(result[y:y + thickness] + 50, 0, 255)
        cv2.putText(result, "REC", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        noise = np.random.normal(0, 10, result.shape).astype(np.uint8)
        return cv2.add(result, noise)

    def signal_lost(self, frame):
        h, w = frame.shape[:2]
        static = np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)
        cv2.putText(static, "SINYAL YOK", (w // 4, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
        return static

    def scanlines(self, frame):
        result = frame.copy()
        for i in range(0, frame.shape[0], 2):
            result[i] = np.clip(result[i] * 0.7, 0, 255).astype(np.uint8)
        return result

    def retro(self, frame):
        result = frame.copy()
        result[:, :, 0] = np.clip(result[:, :, 0] * 0.8, 0, 255).astype(np.uint8)
        result[:, :, 2] = np.clip(result[:, :, 2] * 1.2, 0, 255).astype(np.uint8)
        noise = np.random.normal(0, 15, result.shape).astype(np.uint8)
        result = cv2.add(result, noise)
        return self._add_vignette(result)

    def cinema(self, frame):
        result = frame.copy()
        h = result.shape[0]
        result[:, :, 0] = np.clip(result[:, :, 0] * 0.9, 0, 255).astype(np.uint8)
        result[:, :, 2] = np.clip(result[:, :, 2] * 1.1, 0, 255).astype(np.uint8)
        bar_height = h // 6
        result[:bar_height] = 0
        result[h - bar_height:] = 0
        return result

    def night_vision(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        result = np.zeros_like(frame)
        result[:, :, 1] = gray
        noise = np.random.normal(0, 20, gray.shape).astype(np.uint8)
        result[:, :, 1] = np.clip(result[:, :, 1] + noise, 0, 255)
        result = self._add_vignette(result)
        h, w = gray.shape
        center = (w // 2, h // 2)
        cv2.circle(result, center, 50, (0, 255, 0), 1)
        cv2.line(result, (center[0] - 70, center[1]), (center[0] + 70, center[1]), (0, 255, 0), 1)
        cv2.line(result, (center[0], center[1] - 70), (center[0], center[1] + 70), (0, 255, 0), 1)
        return result

    def thermal(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.applyColorMap(gray, cv2.COLORMAP_JET)

    def pop_art(self, frame):
        result = frame.copy()
        for i in range(3):
            result[:, :, i] = (result[:, :, i] // 64) * 64
        hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.5, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    def funny_mirror(self, frame):
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        map_x = np.zeros((h, w), dtype=np.float32)
        map_y = np.zeros((h, w), dtype=np.float32)
        for i in range(h):
            for j in range(w):
                dx = (j - cx) / cx
                dy = (i - cy) / cy
                r = np.sqrt(dx ** 2 + dy ** 2)
                if r < 1:
                    new_r = r ** 1.5
                    theta = np.arctan2(dy, dx)
                    map_x[i, j] = cx + new_r * np.cos(theta) * cx
                    map_y[i, j] = cy + new_r * np.sin(theta) * cy
                else:
                    map_x[i, j] = j
                    map_y[i, j] = i
        return cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR)

    def _add_vignette(self, frame, strength=0.5):
        rows, cols = frame.shape[:2]
        X = cv2.GaussianBlur(
            (np.eye(rows, cols) * 2 - 1) ** 2,
            (min(rows, cols) | 1, min(rows, cols) | 1), 0
        )
        X = X / X.max()
        X = 1 - strength * (1 - X)
        return (frame * X[:, :, np.newaxis]).astype(np.uint8)

    # ==================== FRAMES ====================

    def no_frame(self, frame):
        return frame

    def _apply_frame_mask(self, frame, mask_type="circle"):
        """Apply shaped frame mask with background color"""
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        center = (w // 2, h // 2)

        if mask_type == "circle":
            radius = min(w, h) // 2 - 20
            cv2.circle(mask, center, radius, 255, -1)
        elif mask_type == "oval":
            axes = (w // 2 - 20, h // 2 - 20)
            cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
        elif mask_type == "square":
            size = min(w, h) // 2 - 20
            cv2.rectangle(mask, (center[0] - size, center[1] - size),
                         (center[0] + size, center[1] + size), 255, -1)
        elif mask_type == "heart":
            mask = self._create_heart_mask(h, w)
        elif mask_type == "star":
            mask = self._create_star_mask(h, w)

        # Background color where mask is 0
        result = np.full_like(frame, self.bg_color, dtype=np.uint8)
        # Camera frame where mask is 255
        result[mask > 0] = frame[mask > 0]

        # White border
        border_size = 3
        if mask_type == "circle":
            cv2.circle(result, center, min(w, h) // 2 - 20, (255, 255, 255), border_size)
        elif mask_type == "oval":
            cv2.ellipse(result, center, (w // 2 - 20, h // 2 - 20), 0, 0, 360, (255, 255, 255), border_size)
        elif mask_type == "square":
            size = min(w, h) // 2 - 20
            cv2.rectangle(result, (center[0] - size, center[1] - size),
                         (center[0] + size, center[1] + size), (255, 255, 255), border_size)

        return result

    def _create_heart_mask(self, h, w):
        mask = np.zeros((h, w), dtype=np.uint8)
        t = np.linspace(0, 2 * np.pi, 1000)
        x = 16 * np.sin(t) ** 3
        y = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
        scale = min(w, h) / 40
        x = (x * scale + w // 2).astype(int)
        y = (y * scale + h // 2).astype(int)
        points = np.column_stack((x, y))
        cv2.fillPoly(mask, [points], 255)
        return mask

    def _create_star_mask(self, h, w):
        mask = np.zeros((h, w), dtype=np.uint8)
        center = (w // 2, h // 2)
        outer_r = min(w, h) // 2 - 20
        inner_r = outer_r * 0.4
        points = []
        for i in range(10):
            angle = i * np.pi / 5 - np.pi / 2
            r = outer_r if i % 2 == 0 else inner_r
            x = int(center[0] + r * np.cos(angle))
            y = int(center[1] + r * np.sin(angle))
            points.append([x, y])
        points = np.array(points)
        cv2.fillPoly(mask, [points], 255)
        return mask

    def circle_frame(self, frame):
        return self._apply_frame_mask(frame, "circle")

    def oval_frame(self, frame):
        return self._apply_frame_mask(frame, "oval")

    def square_frame(self, frame):
        return self._apply_frame_mask(frame, "square")

    def heart_shape(self, frame):
        return self._apply_frame_mask(frame, "heart")

    def star_shape(self, frame):
        return self._apply_frame_mask(frame, "star")

    # ==================== PNG FRAMES (KEY COLOR METHOD) ====================

    def load_png_filters(self):
        """Load PNG files from filters folder"""
        filters_dir = os.path.join(os.path.dirname(__file__), "filters")
        if not os.path.exists(filters_dir):
            os.makedirs(filters_dir)
            self._create_readme(filters_dir)
            return

        for filename in os.listdir(filters_dir):
            if filename.lower().endswith(".png"):
                name = os.path.splitext(filename)[0]
                filepath = os.path.join(filters_dir, filename)
                try:
                    img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
                    if img is not None:
                        display_name = f"PNG: {name}"
                        self.png_frames[display_name] = img
                except Exception:
                    pass

    def _create_readme(self, directory):
        """Create README explaining PNG frame format"""
        readme_text = """PNG CERCEVE FORMATI
==================

METHOT: ANAHTAR RENK (KEY COLOR)

Cerceve PNG'nizde 3 farkli alan olmali:

1. MAGENTA (#FF00FF) - KAMERA GÖRÜNTÜSÜ
   - RGB: (255, 0, 255) 
   - Bu alanda kameradan gelen görüntü görünür
   - PNG'de magenta ile boyanmis alan = kamera penceresi

2. DIGER RENKLER - CERCEVE DEKORASYONU  
   - Mavi, kirmizi, altin, vb. 
   - Bunlar cercevenin kendisini olusturur
   - Kamera goruntusu BU ALANDA GÖRÜNMEZ

3. YESIL (veya arka plan rengi) - DIS ALAN
   - Greenscreen icin kullanilir
   - OBS'de bu alan kaldirilabilir

ORNEK PNG OLUSTURMA (Python):
-----------------------------
import cv2, numpy as np

img = np.zeros((480, 640, 3), dtype=np.uint8)

# Dis alan: Yesil (greenscreen)
img[:] = (0, 200, 0)

# Cerceve: Mavi dikdortgen  
img[20:60, 20:620] = (200, 100, 0)   # Ust
img[420:460, 20:620] = (200, 100, 0) # Alt
img[20:460, 20:60] = (200, 100, 0)   # Sol
img[20:460, 580:620] = (200, 100, 0) # Sag

# Kamera alani: Magenta (#FF00FF)
img[60:420, 60:580] = (255, 0, 255)

cv2.imwrite("cercevem.png", img)

NOT: PNG 3 kanalli (RGB) veya 4 kanalli (RGBA) olabilir.
Magenta rengi tam olarak (255, 0, 255) olmali veya
yaklasik olarak bu degerlerde olmali (esik: 60 birim).
"""
        with open(os.path.join(directory, "README.txt"), "w", encoding="utf-8") as f:
            f.write(readme_text)

    def apply_png_frame(self, frame, frame_name):
        """
        Apply PNG frame using key-color method.
        
        Magenta areas (#FF00FF) = Camera shows through
        Other areas = PNG image shown (frame decoration)
        Green areas = Background color (greenscreen)
        """
        if frame_name not in self.png_frames:
            return frame

        frame_img = self.png_frames[frame_name]
        h, w = frame.shape[:2]

        # Resize frame image to match video
        frame_resized = cv2.resize(frame_img, (w, h))

        # If has alpha channel, use it for transparency
        if frame_resized.shape[2] == 4:
            bgr = frame_resized[:, :, :3]
            alpha = frame_resized[:, :, 3] / 255.0
        else:
            bgr = frame_resized
            alpha = np.ones((h, w), dtype=np.float32)

        # Create mask for magenta (key color)
        magenta_mask = self._create_key_color_mask(bgr, KEY_COLOR_BGR, KEY_THRESHOLD)

        # Create result image
        result = np.zeros_like(frame)

        # Where magenta mask is 1: show camera frame
        for c in range(3):
            result[:, :, c] = np.where(
                magenta_mask > 0,
                frame[:, :, c],  # Camera
                bgr[:, :, c]     # PNG frame
            )

        # Apply alpha: where alpha=0, show background color
        bg = np.full_like(frame, self.bg_color, dtype=np.uint8)
        alpha_3channel = np.stack([alpha] * 3, axis=-1)
        result = (result * alpha_3channel + bg * (1 - alpha_3channel)).astype(np.uint8)

        return result

    def _create_key_color_mask(self, bgr_image, key_color_bgr, threshold):
        """Create mask where key color is detected"""
        # Calculate distance from key color
        diff = bgr_image.astype(np.float32) - np.array(key_color_bgr, dtype=np.float32)
        distance = np.sqrt(np.sum(diff ** 2, axis=2))
        
        # Create mask: 1 where distance < threshold, 0 otherwise
        mask = np.where(distance < threshold, 255, 0).astype(np.uint8)
        
        # Clean up mask
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        return mask

    # ==================== COLOR SETTINGS ====================

    def set_bg_color(self, color_name):
        """Set background color for frames"""
        colors = {
            "Yesil": (0, 200, 0), "Mavi": (200, 100, 0),
            "Kirmizi": (0, 0, 200), "Sari": (0, 220, 220),
            "Mor": (180, 0, 180), "Turuncu": (0, 140, 255),
            "Pembe": (180, 100, 255), "Beyaz": (255, 255, 255),
            "Siyah": (0, 0, 0),
        }
        if color_name in colors:
            self.bg_color = colors[color_name]
            self.bg_color_name = color_name
            return True
        return False

    def get_bg_colors(self):
        return ["Yesil", "Mavi", "Kirmizi", "Sari", "Mor", "Turuncu", "Pembe", "Beyaz", "Siyah"]
