"""Скрипт сборки WordSnap:
1. Компиляция exe через PyInstaller (onedir mode, исключение неиспользуемых 200MB+ модулей)
2. Копирование ресурсов assets/ и преднастроенной базы словарей data/
3. Создание Portable ZIP-архива (WordSnap-1.0.0-Portable.zip)
4. Компиляция инсталлятора через Inno Setup (WordSnap-1.0.0-Setup.exe)
"""
import os
import sys
import shutil
import subprocess
import zipfile
import json

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

APP_NAME = "WordSnap"
VERSION = "1.3.1"
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(ROOT_DIR, "dist", APP_NAME)
RELEASE_DIR = os.path.join(ROOT_DIR, "release")

ISCC_PATHS = [
    r"C:\Users\wefdr\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]

def find_iscc() -> str | None:
    for p in ISCC_PATHS:
        if os.path.exists(p):
            return p
    try:
        res = subprocess.run(["where", "ISCC.exe"], capture_output=True, text=True)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            if lines:
                return lines[0].strip()
    except Exception:
        pass
    return None

def make_clean_settings() -> dict:
    return {
        "ui_theme": "dark",
        "ui_lang": "en",
        "mode": "dictionary",
        "autostart": False,
        "hotkey": "alt+q",
        "mouse_hotkey_enabled": True,
        "mouse_hotkey_button": "middle",
        "mouse_hotkey_modifier": "ctrl",
        "ocr_engine": "auto",
        "ocr_lang": "en",
        "overlay_active_window": False,
        "freeze_screen": False,
        "autopause_window": "",
        "fullscreenize_window": "",
        "auto_save_words": False,
        "auto_crop_screenshots": False,
        "show_duplicate_badge": True,
        "sources_order": [
            "translator_pro",
            "looktionary_pro",
            "dict:wty-en-ru"
        ],
        "sources_enabled": {
            "translator_pro": True,
            "looktionary_pro": True,
            "dict:wty-en-ru": True
        },
        "translator_pro": {
            "target_lang": "ru",
            "hide_in_dict_mode": False
        },
        "looktionary_pro": {
            "def_lang": "ru",
            "word_trans_lang": "ru",
            "hide_word_translation": False
        },
        "ai_provider": "groq",
        "groq_api_key": "",
        "groq_model": "auto",
        "gemini_api_key": "",
        "gemini_model": "auto",
        "first_setup_done": False,
        "anki_enabled": False,
        "anki_server": "http://127.0.0.1:8765",
        "anki_tags": "wordsnap",
        "anki_deck": "",
        "anki_model": "",
        "anki_fields": {},
        "anki_duplicate_scope": "deck"
    }

def step1_pyinstaller():
    print("=" * 60)
    print("1. Запуск PyInstaller для сборки WordSnap.exe...")
    print("=" * 60)

    # Убеждаемся, что icon.ico есть
    ico_path = os.path.join(ROOT_DIR, "assets", "icon.ico")
    if not os.path.exists(ico_path):
        from PIL import Image
        img = Image.open(os.path.join(ROOT_DIR, "assets", "icon.png"))
        img.save(ico_path, format="ICO", sizes=[(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)])

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--name", APP_NAME,
        "--icon", ico_path,
        # Зависимости Windows OCR и хуков
        "--collect-all", "winrt",
        "--hidden-import", "winrt.windows.media.ocr",
        "--hidden-import", "winrt.windows.globalization",
        "--hidden-import", "winrt.windows.graphics.imaging",
        "--hidden-import", "winrt.windows.storage.streams",
        "--hidden-import", "pynput.keyboard._win32",
        "--hidden-import", "pynput.mouse._win32",
        "--hidden-import", "pyttsx3.drivers",
        "--hidden-import", "pyttsx3.drivers.sapi5",
        "--hidden-import", "sqlite3",
        # Исключаем гигантские неиспользуемые модули PySide6 (WebEngineCore = 195MB, Qml, 3D, Multimedia)
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.QtWebEngineQuick",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.QtQuickWidgets",
        "--exclude-module", "PySide6.QtQuick3D",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.Qt3DRender",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "PySide6.QtMultimediaWidgets",
        "--exclude-module", "PySide6.QtDesigner",
        "--exclude-module", "PySide6.QtPdf",
        "--exclude-module", "PySide6.QtPdfWidgets",
        "--exclude-module", "PySide6.QtPositioning",
        "--exclude-module", "PySide6.QtBluetooth",
        "--exclude-module", "PySide6.QtNfc",
        "--exclude-module", "PySide6.QtSensors",
        "--exclude-module", "PySide6.QtSql",
        "--exclude-module", "PySide6.QtTest",
        "--exclude-module", "PySide6.QtSpatialAudio",
        "--exclude-module", "PySide6.QtVirtualKeyboard",
        "--exclude-module", "tkinter",
        "--exclude-module", "unittest",
        "--exclude-module", "test",
        "main.py"
    ]

    res = subprocess.run(cmd, cwd=ROOT_DIR)
    if res.returncode != 0:
        raise RuntimeError("PyInstaller завершился с ошибкой!")

def step2_copy_resources():
    print("=" * 60)
    print("2. Копирование ресурсов и подготовка структуры...")
    print("=" * 60)

    # 1. Assets
    dest_assets = os.path.join(DIST_DIR, "assets")
    if os.path.exists(dest_assets):
        shutil.rmtree(dest_assets)
    shutil.copytree(os.path.join(ROOT_DIR, "assets"), dest_assets)

    # 2. Data
    dest_data = os.path.join(DIST_DIR, "data")
    os.makedirs(dest_data, exist_ok=True)
    os.makedirs(os.path.join(dest_data, "screenshots"), exist_ok=True)

    # Копируем базу словарей dictionaries.db
    src_dicts = os.path.join(ROOT_DIR, "data", "dictionaries")
    dest_dicts = os.path.join(dest_data, "dictionaries")
    if os.path.exists(src_dicts):
        if os.path.exists(dest_dicts):
            shutil.rmtree(dest_dicts)
        shutil.copytree(src_dicts, dest_dicts)

    # Чистый settings.json
    with open(os.path.join(dest_data, "settings.json"), "w", encoding="utf-8") as f:
        json.dump(make_clean_settings(), f, ensure_ascii=False, indent=2)

    # Пустой words.json
    with open(os.path.join(dest_data, "words.json"), "w", encoding="utf-8") as f:
        json.dump([], f)

    # Флаг портативности
    with open(os.path.join(DIST_DIR, "portable.flag"), "w", encoding="utf-8") as f:
        f.write("portable=1\n")

    # Чистка лишних тяжелых переводов Qt (кроме en/ru)
    qt_translations = os.path.join(DIST_DIR, "PySide6", "translations")
    if os.path.exists(qt_translations):
        for fn in os.listdir(qt_translations):
            if not fn.startswith(("qt_ru", "qt_en", "qtbase_ru", "qtbase_en")):
                try:
                    os.remove(os.path.join(qt_translations, fn))
                except Exception:
                    pass

def get_dir_size(path: str) -> int:
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total

def step3_make_portable_zip():
    print("=" * 60)
    print("3. Создание Portable ZIP-архива...")
    print("=" * 60)
    os.makedirs(RELEASE_DIR, exist_ok=True)
    zip_name = f"{APP_NAME}-{VERSION}-Portable.zip"
    zip_path = os.path.join(RELEASE_DIR, zip_name)
    if os.path.exists(zip_path):
        os.remove(zip_path)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(DIST_DIR):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, os.path.dirname(DIST_DIR))
                z.write(full_path, rel_path)

    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"Готово! Portable ZIP создан: {zip_path} ({zip_size_mb:.1f} MB)")
    return zip_path

def step4_make_installer():
    print("=" * 60)
    print("4. Компиляция инсталлятора через Inno Setup...")
    print("=" * 60)
    iscc = find_iscc()
    if not iscc:
        print("[ВНИМАНИЕ] Inno Setup (ISCC.exe) не найден! Инсталлятор пропущен.")
        return None

    ico_path = os.path.join(ROOT_DIR, "assets", "icon.ico")
    iss_content = """
; Скрипт сборки инсталлятора WordSnap
#define MyAppName "__APP_NAME__"
#define MyAppVersion "__VERSION__"
#define MyAppPublisher "WordSnap Team"
#define MyAppExeName "__APP_NAME__.exe"
#define MyAppSourceDir "__DIST_DIR__"
#define MyOutputDir "__RELEASE_DIR__"

[Setup]
AppId={{A8C3B14E-7F89-4D6B-952C-5A24D3E83C90}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir={#MyOutputDir}
OutputBaseFilename=WordSnap-__VERSION__-Setup
SetupIconFile=__ICON_PATH__
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableDirPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Запускать WordSnap при входе в Windows / Run WordSnap at startup"; GroupDescription: "Windows:"; Flags: unchecked

[Files]
Source: "{#MyAppSourceDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"
Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """"{app}\\{#MyAppExeName}""""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
"""
    iss_content = iss_content.replace("__APP_NAME__", APP_NAME)
    iss_content = iss_content.replace("__VERSION__", VERSION)
    iss_content = iss_content.replace("__DIST_DIR__", DIST_DIR)
    iss_content = iss_content.replace("__RELEASE_DIR__", RELEASE_DIR)
    iss_content = iss_content.replace("__ICON_PATH__", ico_path)
    iss_file = os.path.join(ROOT_DIR, "installer.iss")
    with open(iss_file, "w", encoding="utf-8") as f:
        f.write(iss_content.strip())

    res = subprocess.run([iscc, iss_file], cwd=ROOT_DIR)
    if res.returncode != 0:
        raise RuntimeError("Компиляция Inno Setup завершилась с ошибкой!")

    installer_path = os.path.join(RELEASE_DIR, f"{APP_NAME}-{VERSION}-Setup.exe")
    if os.path.exists(installer_path):
        inst_size_mb = os.path.getsize(installer_path) / (1024 * 1024)
        print(f"Готово! Инсталлятор создан: {installer_path} ({inst_size_mb:.1f} MB)")
        return installer_path
    return None

if __name__ == "__main__":
    print(f"Начало сборки {APP_NAME} v{VERSION}...")
    step1_pyinstaller()
    step2_copy_resources()
    dist_size = get_dir_size(DIST_DIR) / (1024 * 1024)
    print(f"Размер распакованной папки {APP_NAME}: {dist_size:.1f} MB")
    zip_res = step3_make_portable_zip()
    inst_res = step4_make_installer()

    print("\n" + "=" * 60)
    print("ИТОГИ СБОРКИ:")
    print("=" * 60)
    print(f"1. Папка программы:     {DIST_DIR} ({dist_size:.1f} MB)")
    if zip_res:
        print(f"2. Portable ZIP:        {zip_res} ({os.path.getsize(zip_res)/(1024*1024):.1f} MB)")
    if inst_res:
        print(f"3. Инсталлятор Windows: {inst_res} ({os.path.getsize(inst_res)/(1024*1024):.1f} MB)")
    print("=" * 60)
