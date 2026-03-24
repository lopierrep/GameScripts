# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=['E:\\2_Games\\Scripts\\Dofus\\MarketTracker\\App\\..'],
    binaries=[],
    datas=[],
    hiddenimports=['update_profession_recipes', 'update_single_recipe', 'Helpers.SearchAndSave.search_item_prices', 'Helpers.SearchAndSave.save_recipe_selling_prices', 'Helpers.SearchAndSave.save_recipe_crafting_prices', 'Helpers.SearchAndSave.save_resource_buy_prices', 'Helpers.SearchAndSave.common', 'Helpers.Exporting.export_to_sheets', 'gspread', 'google.auth', 'google.auth.transport.requests', 'PIL', 'pytesseract', 'keyboard', 'pyautogui'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MarketTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
