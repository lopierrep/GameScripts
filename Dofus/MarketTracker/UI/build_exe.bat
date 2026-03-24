@echo off
:: ============================================================
:: MarketTracker - Compilar .exe con PyInstaller
:: ============================================================

cd /d "%~dp0"
set ROOT=%~dp0..
set DIST=%~dp0dist\MarketTracker

echo [1/4] Instalando dependencias...
python -m pip install pyinstaller --quiet

echo [2/4] Compilando...
python -m PyInstaller ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "MarketTracker" ^
  --paths "%ROOT%" ^
  --hidden-import update_profession_recipes ^
  --hidden-import update_single_recipe ^
  --hidden-import Helpers.SearchAndSave.search_item_prices ^
  --hidden-import Helpers.SearchAndSave.save_recipe_selling_prices ^
  --hidden-import Helpers.SearchAndSave.save_recipe_crafting_prices ^
  --hidden-import Helpers.SearchAndSave.save_resource_buy_prices ^
  --hidden-import Helpers.SearchAndSave.common ^
  --hidden-import Helpers.Exporting.export_to_sheets ^
  --hidden-import gspread ^
  --hidden-import google.auth ^
  --hidden-import google.auth.transport.requests ^
  --hidden-import PIL ^
  --hidden-import pytesseract ^
  --hidden-import keyboard ^
  --hidden-import pyautogui ^
  app.py

if errorlevel 1 (
    echo [ERROR] Fallo la compilacion.
    pause
    exit /b 1
)

echo [3/4] Copiando datos junto al ejecutable...

if not exist "%DIST%" mkdir "%DIST%"

move /Y "%~dp0dist\MarketTracker.exe" "%DIST%\MarketTracker.exe"
if errorlevel 1 echo [AVISO] No se pudo mover el exe

robocopy "%ROOT%\Recipes" "%DIST%\Recipes" /E /NFL /NDL /NJH /NJS /NP > nul
robocopy "%ROOT%\Markets" "%DIST%\Markets" /E /NFL /NDL /NJH /NJS /NP > nul
robocopy "%ROOT%\Helpers" "%DIST%\Helpers" /E /NFL /NDL /NJH /NJS /NP /XF calibration.json /XF credentials.json > nul

echo [4/4] Listo!
echo.
echo Distribucion lista en:
echo   %DIST%\
echo.
echo IMPORTANTE: Tesseract OCR debe estar instalado en:
echo   C:\Program Files\Tesseract-OCR\tesseract.exe
pause
