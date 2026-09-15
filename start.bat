@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo    Webcam Studio - Baslatici
echo ========================================
echo.
echo  1. Basit Versiyon (webcam_app.py)
echo  2. Pro Versiyon (webcam_studio_pro.py)
echo.
set /p choice="Seciminizi yapin (1 veya 2): "

if "%choice%"=="1" (
    echo.
    echo Basit versiyon baslatiliyor...
    python webcam_app.py
) else if "%choice%"=="2" (
    echo.
    echo Pro versiyon baslatiliyor...
    python webcam_studio_pro.py
) else (
    echo.
    echo Gecersiz secim. Pro versiyon baslatiliyor...
    python webcam_studio_pro.py
)

pause
