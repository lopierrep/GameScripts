@echo off
cd /d "%~dp0"

echo Instalando PyInstaller si no esta instalado...
python -m pip install pyinstaller keyboard --quiet

echo.
echo Generando .exe...
python -m PyInstaller --onefile --windowed --hidden-import=keyboard --name "PavoConArmadura" PavoConArmaduraApp.py

echo.
echo Listo! El .exe esta en: dist\PavoConArmadura.exe
pause
