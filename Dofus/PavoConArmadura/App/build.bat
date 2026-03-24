@echo off
cd /d "%~dp0"

echo Instalando PyInstaller si no esta instalado...
pip install pyinstaller --quiet

echo.
echo Generando .exe...
pyinstaller --onefile --windowed --name "PavoConArmadura" PavoConArmaduraApp.py

echo.
echo Listo! El .exe esta en: dist\PavoConArmadura.exe
pause
