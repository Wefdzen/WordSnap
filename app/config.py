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

def data_dir() -> str:
    d = os.path.join(app_dir(), "data")
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(d, "screenshots"), exist_ok=True)
    return d

SETTINGS_PATH = lambda: os.path.join(data_dir(), "settings.json")

DEFAULTS = {
    # --- Внешний вид ---
    "ui_theme": "dark",              # "dark" | "light" | "system"
    "ui_lang": "ru",                 # "ru" | "en" — язык интерфейса
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
    "auto_save_words": True,
    "auto_crop_screenshots": False,
    "show_duplicate_badge": True,    # значок-метка у слов, которые встречаются не раз
    # --- Переводчик и словари ---
    "sources_order": ["translator_pro", "looktionary_pro", "oxford"],
    "sources_enabled": {"translator_pro": True, "looktionary_pro": True, "oxford": True},
    "translator_pro": {"target_lang": "ru", "hide_in_dict_mode": False},
    "looktionary_pro": {"def_lang": "ru", "word_trans_lang": "ru", "hide_word_translation": False},
    # --- ИИ-провайдер ---
    "ai_provider": "groq",          # "groq" (быстрый) | "gemini"
    "groq_api_key": "",             # https://console.groq.com/keys
    "groq_model": "llama-3.3-70b-versatile",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
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
        except FileNotFoundError:
            pass
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
