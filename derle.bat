@echo off
chcp 65001 >nul
echo ═══════════════════════════════════════════════════════════
echo              ORBIT DOWNLOADER - BUILD SCRIPT
echo ═══════════════════════════════════════════════════════════
echo.

echo [1/4] Build ve dist klasorleri temizleniyor...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
echo       Temizlik tamamlandi.

echo.
echo [2/4] PyInstaller ile derleniyor...
pyinstaller Orbit.spec --noconfirm
if %errorlevel% neq 0 (
    echo HATA: PyInstaller basarisiz oldu!
    pause
    exit /b 1
)

echo.
echo [3/4] Gereksiz ceviri dosyalari temizleniyor...
powershell -Command "Get-ChildItem 'dist\Orbit\_internal\PySide6\translations\*' -Exclude '*_tr.qm' | Remove-Item -Force"

echo.
echo [4/4] Build boyutu hesaplaniyor...
powershell -Command "$size = (Get-ChildItem -Recurse 'dist\Orbit' | Measure-Object -Property Length -Sum).Sum / 1MB; Write-Host ('Dist boyutu: ' + [math]::Round($size,2) + ' MB')"

echo.
echo ═══════════════════════════════════════════════════════════
echo              BUILD TAMAMLANDI!
echo ═══════════════════════════════════════════════════════════
echo.
echo Simdi Inno Setup ile setup_script.iss dosyasini derleyebilirsiniz.
echo.
pause
