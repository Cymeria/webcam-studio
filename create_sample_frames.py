"""
Example: Create sample PNG frames with KEY COLOR method

KEY COLOR: Magenta (#FF00FF) = Camera shows through
Other colors = Frame decoration
Green = Outside frame (greenscreen)
"""

import cv2
import numpy as np
import os

# Key color (magenta) - camera window
MAGENTA = (255, 0, 255)  # RGB
MAGENTA_BGR = (255, 0, 255)  # BGR

def create_circle_frame():
    """Circle frame: Magenta center = camera, blue border = frame, green outside"""
    h, w = 480, 640
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # 1. Green background (outside frame - greenscreen)
    img[:] = (0, 200, 0)

    # 2. Blue frame border (circular)
    center = (w // 2, h // 2)
    outer_radius = min(w, h) // 2 - 20
    inner_radius = outer_radius - 30

    # Draw filled blue circle (frame)
    cv2.circle(img, center, outer_radius, (200, 100, 0), -1)

    # 3. Magenta center (camera window)
    cv2.circle(img, center, inner_radius, MAGENTA_BGR, -1)

    # Add white ring decoration
    cv2.circle(img, center, outer_radius, (255, 255, 255), 3)
    cv2.circle(img, center, inner_radius, (255, 255, 255), 3)

    return img

def create_ornate_frame():
    """Ornate frame: Magenta center = camera, gold border = frame, green outside"""
    h, w = 480, 640
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # 1. Green background
    img[:] = (0, 200, 0)

    # 2. Gold frame (outer rectangle)
    img[10:470, 10:630] = (0, 180, 220)  # Gold color

    # 3. Magenta center (camera window)
    img[50:430, 50:590] = MAGENTA_BGR

    # Decorations (opaque, not magenta)
    cv2.rectangle(img, (5, 5), (635, 475), (255, 255, 255), 3)
    cv2.rectangle(img, (45, 45), (595, 435), (200, 200, 200), 2)

    # Corner decorations
    for x, y in [(25, 25), (615, 25), (25, 455), (615, 455)]:
        cv2.circle(img, (x, y), 12, (0, 150, 200), -1)
        cv2.circle(img, (x, y), 6, (255, 255, 255), -1)

    return img

def create_heart_frame():
    """Heart frame: Magenta heart = camera, pink border = frame"""
    h, w = 480, 640
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # 1. Green background
    img[:] = (0, 200, 0)

    center = (w // 2, h // 2)

    # Create heart shape
    t = np.linspace(0, 2 * np.pi, 1000)
    x = 16 * np.sin(t) ** 3
    y = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))

    scale = min(w, h) / 42
    x = (x * scale + w // 2).astype(int)
    y = (y * scale + h // 2).astype(int)
    points = np.column_stack((x, y))

    # 2. Pink frame (outer heart)
    cv2.fillPoly(img, [points], (180, 100, 255))

    # 3. Magenta center (smaller heart - camera window)
    scale_inner = min(w, h) / 48
    x_inner = (16 * np.sin(t) ** 3 * scale_inner + w // 2).astype(int)
    y_inner = (-(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)) * scale_inner + h // 2).astype(int)
    points_inner = np.column_stack((x_inner, y_inner))
    cv2.fillPoly(img, [points_inner], MAGENTA_BGR)

    # White border
    cv2.polylines(img, [points], True, (255, 255, 255), 3)
    cv2.polylines(img, [points_inner], True, (255, 255, 255), 2)

    return img

def create_modern_frame():
    """Modern minimal frame with gradient-like border"""
    h, w = 480, 640
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # 1. Green background
    img[:] = (0, 200, 0)

    # 2. Dark frame border
    img[0:15, :] = (80, 60, 40)     # Top
    img[465:480, :] = (80, 60, 40)  # Bottom
    img[:, 0:15] = (80, 60, 40)     # Left
    img[:, 625:640] = (80, 60, 40)  # Right

    # 3. Accent lines
    img[15:18, :] = (0, 200, 255)   # Cyan line top
    img[462:465, :] = (0, 200, 255) # Cyan line bottom

    # 4. Magenta center (camera window)
    img[18:462, 15:625] = MAGENTA_BGR

    return img

# Create and save samples
if __name__ == "__main__":
    filters_dir = os.path.join(os.path.dirname(__file__), "filters")
    os.makedirs(filters_dir, exist_ok=True)

    frames = {
        "daire_cerceve.png": create_circle_frame(),
        "sulu_cerceve.png": create_ornate_frame(),
        "kalp_cerceve.png": create_heart_frame(),
        "modern_cerceve.png": create_modern_frame(),
    }

    for name, img in frames.items():
        path = os.path.join(filters_dir, name)
        cv2.imwrite(path, img)
        print(f"Olusturuldu: {path}")

    print("\nMantik:")
    print("  YESIL = Dis alan (greenscreen)")
    print("  MAGENTA (#FF00FF) = Kamera goruntusu burada")
    print("  DIGER RENKLER = Cerceve dekorasyonu")
