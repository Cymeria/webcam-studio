"""
Ekran goruntusu alma scripti - Webcam App ve Webcam App Pro icin
Uygulamalari baslatir, arayuzun gorunmesini bekler, screenshot alir.
"""
import subprocess
import time
import sys
import os
import signal

def take_screenshots():
    import pyautogui
    import pygetwindow as gw
    
    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    
    # Webcam App
    print("[1/4] Webcam App baslatiliyor...")
    proc1 = subprocess.Popen(
        [sys.executable, "webcam_app.py"],
        cwd=os.path.dirname(__file__),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    time.sleep(4)
    
    print("[2/4] Webcam App ekran goruntusu aliniyor...")
    try:
        windows = gw.getWindowsWithTitle("Webcam Studio")
        if windows:
            win = windows[0]
            win.activate()
            time.sleep(0.5)
            # Pencerenin gorunur alani screenshot
            screenshot = pyautogui.screenshot(region=(win.left, win.top, win.width, win.height))
            screenshot.save(os.path.join(screenshots_dir, "webcam_app_main.png"))
            print("  -> Kaydedildi: webcam_app_main.png")
        else:
            # Pencere bulunamadiysa tam ekran screenshot al
            screenshot = pyautogui.screenshot()
            screenshot.save(os.path.join(screenshots_dir, "webcam_app_main.png"))
            print("  -> Tam ekran screenshot alindi: webcam_app_main.png")
    except Exception as e:
        print(f"  -> Hata: {e}")
        screenshot = pyautogui.screenshot()
        screenshot.save(os.path.join(screenshots_dir, "webcam_app_main.png"))
    
    # Kapat
    print("[3/4] Webcam App kapatiliyor...")
    try:
        proc1.terminate()
        proc1.wait(timeout=5)
    except:
        try:
            proc1.kill()
        except:
            pass
    time.sleep(2)
    
    # Webcam App Pro
    print("[4/4] Webcam App Pro baslatiliyor...")
    proc2 = subprocess.Popen(
        [sys.executable, "webcam_studio_pro.py"],
        cwd=os.path.dirname(__file__),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    time.sleep(4)
    
    print("[5/5] Webcam App Pro ekran goruntusu aliniyor...")
    try:
        windows = gw.getWindowsWithTitle("Webcam Studio Pro")
        if windows:
            win = windows[0]
            win.activate()
            time.sleep(0.5)
            screenshot = pyautogui.screenshot(region=(win.left, win.top, win.width, win.height))
            screenshot.save(os.path.join(screenshots_dir, "webcam_app_pro_main.png"))
            print("  -> Kaydedildi: webcam_app_pro_main.png")
        else:
            screenshot = pyautogui.screenshot()
            screenshot.save(os.path.join(screenshots_dir, "webcam_app_pro_main.png"))
            print("  -> Tam ekran screenshot alindi: webcam_app_pro_main.png")
    except Exception as e:
        print(f"  -> Hata: {e}")
        screenshot = pyautogui.screenshot()
        screenshot.save(os.path.join(screenshots_dir, "webcam_app_pro_main.png"))
    
    # Kapat
    print("  Pro kapatiliyor...")
    try:
        proc2.terminate()
        proc2.wait(timeout=5)
    except:
        try:
            proc2.kill()
        except:
            pass
    
    print("\nTamamlandi! Ekran goruntuleri screenshots/ klasorune kaydedildi.")

if __name__ == "__main__":
    take_screenshots()
