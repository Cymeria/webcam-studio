@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo    Webcam Studio Pro - EXE Derleme
echo ========================================
echo.

echo PyInstaller yukleniyor...
pip install pyinstaller

echo.
echo Derleme basliyor...
echo Bu islem birkaç dakika surebilir.
echo.

pyinstaller --name "WebcamStudioPro" --windowed --onefile --noconsole --clean webcam_studio_pro.py

if %errorlevel% neq 0 (
    echo.
    echo Derleme hatasi! Asagidaki komutu deneyin:
    echo pyinstaller --name "WebcamStudioPro" --windowed --onefile webcam_studio_pro.py
    pause
    exit /b 1
)

echo.
echo ========================================
echo    Derleme tamamlandi!
echo ========================================
echo.
echo EXE dosyasi: dist\WebcamStudioPro.exe
echo.
echo dist klasorunu kontrol edin.
echo.

if exist "dist\WebcamStudioPro.exe" (
    echo EXE dosyasi bulundu. Test icin calistirmak ister misiniz?
    set /p choice="E/H: "
    if /i "%choice%"=="E" (
        start "" "dist\WebcamStudioPro.exe"
    )
)

pause
