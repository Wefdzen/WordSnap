"""Конфигурация приложения. Все настройки хранятся в data/settings.json рядом с программой."""
import json
import os
import sys
import copy

def app_dir() -> str:
    """Папка приложения: рядом с .exe (frozen) или корень проекта."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def is_dir_writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, f".test_write_{os.getpid()}")
        with open(test_file, "w") as f:
            f.write("1")
        if os.path.exists(test_file):
            os.remove(test_file)
        return True
    except Exception:
        return False

_DATA_DIR = None

def data_dir() -> str:
    global _DATA_DIR
    if _DATA_DIR and os.path.exists(_DATA_DIR):
        return _DATA_DIR

    local_data = os.path.join(app_dir(), "data")
    portable_marker = os.path.join(app_dir(), "portable.flag")
    if os.path.exists(portable_marker) or is_dir_writable(local_data):
        _DATA_DIR = local_data
    else:
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        _DATA_DIR = os.path.join(appdata, "WordSnap", "data")

    os.makedirs(_DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(_DATA_DIR, "screenshots"), exist_ok=True)
    return _DATA_DIR

SETTINGS_PATH = lambda: os.path.join(data_dir(), "settings.json")

def detect_system_lang() -> str:
    if sys.platform == "win32":
        try:
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFF
            if lang_id in (0x19, 0x22, 0x23):
                return "ru"
            return "en"
        except Exception:
            pass
    try:
        import locale
        loc = (locale.getlocale()[0] or "").lower()
        if loc.startswith(("ru", "uk", "be")):
            return "ru"
    except Exception:
        pass
    return "en"

DEFAULTS = {
    # --- Внешний вид ---
    "ui_theme": "dark",              # "dark" | "light" | "system"
    "ui_lang": detect_system_lang(), # "en" | "ru" — язык интерфейса по умолчанию
    # --- Общие ---
    "mode": "dictionary",            # "translator" | "dictionary"
    "autostart": False,
    # --- Горячие клавиши ---
    "hotkey": "alt+q",
    "mouse_hotkey_enabled": True,
    "mouse_hotkey_button": "middle",  # "middle" | "x1" | "x2" | "none"
    "mouse_hotkey_modifier": "none",  # "none" | "alt" | "ctrl" | "shift"
    # --- OCR ---
    "ocr_engine": "auto",            # "auto" -> WindowsOCR на Windows, иначе tesseract
    "ocr_lang": "en",                # язык текста на экране
    # --- Взаимодействие с играми ---
    "overlay_active_window": False,
    "freeze_screen": False,
    "autopause_window": "",
    "fullscreenize_window": "",
    # --- Слова ---
    "auto_save_words": False,
    "auto_crop_screenshots": False,
    "show_duplicate_badge": True,    # значок-метка у слов, которые встречаются не раз
    # --- Переводчик и словари ---
    "sources_order": ["translator_pro", "looktionary_pro"],
    "sources_enabled": {"translator_pro": True, "looktionary_pro": True},
    "translator_pro": {"target_lang": "ru", "hide_in_dict_mode": False},
    "looktionary_pro": {"def_lang": "ru", "word_trans_lang": "ru", "hide_word_translation": False},
    # --- ИИ-провайдер ---
    "ai_provider": "groq",          # "groq" (быстрый) | "gemini"
    "groq_api_key": "",             # https://console.groq.com/keys
    "groq_model": "auto",
    "gemini_api_key": "",
    "gemini_model": "auto",
    # --- Первый запуск ---
    "first_setup_done": False,
    # --- Anki (AnkiConnect) ---
    "anki_enabled": True,
    "anki_server": "http://127.0.0.1:8765",
    "anki_tags": "wordsnap",
    "anki_deck": "",
    "anki_model": "",
    "anki_fields": {},
    "anki_duplicate_scope": "deck",
}

LANGS = [("ru", "Русский", "🇷🇺"), ("en", "English", "🇺🇸"), ("de", "Deutsch", "🇩🇪"),
         ("fr", "Français", "🇫🇷"), ("es", "Español", "🇪🇸"), ("ja", "日本語", "🇯🇵"),
         ("zh", "中文", "🇨🇳"), ("ko", "한국어", "🇰🇷"), ("uk", "Українська", "🇺🇦")]

def flag_for(lang: str) -> str:
    for code, _, fl in LANGS:
        if code == lang:
            return fl
    return "🌐"

def lang_name(lang: str) -> str:
    for code, name, _ in LANGS:
        if code == lang:
            return name
    return lang

class Config:
    def __init__(self):
        self._d = copy.deepcopy(DEFAULTS)
        self.is_first_run = not os.path.exists(SETTINGS_PATH())
        self.load()

    def load(self):
        try:
            with open(SETTINGS_PATH(), "r", encoding="utf-8") as f:
                stored = json.load(f)
            for k, v in stored.items():
                if isinstance(v, dict) and isinstance(self._d.get(k), dict):
                    self._d[k].update(v)
                else:
                    self._d[k] = v
            if "first_setup_done" not in stored:
                self._d["first_setup_done"] = True
        except FileNotFoundError:
            self._d["first_setup_done"] = False
        except Exception as e:
            print("config load error:", e)

    def save(self):
        try:
            with open(SETTINGS_PATH(), "w", encoding="utf-8") as f:
                json.dump(self._d, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("config save error:", e)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value, save=True):
        self._d[key] = value
        if save:
            self.save()

    def __getitem__(self, k):
        return self._d[k]

CONFIG = Config()
