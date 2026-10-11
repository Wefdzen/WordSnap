"""Интеграция с Anki через плагин AnkiConnect (по аналогии с Yomitan).

Предоставляет:
- Проверку связи с AnkiConnect
- Получение списка колод (decks) и моделей/типов заметок (models)
- Получение полей модели (fields)
- Подстановку маркеров шаблона ({expression}, {glossary}, {sentence}, {audio}, {screenshot} и т.д.)
- Экспорт медиафайлов (аудио-озвучка через pyttsx3, скриншоты) в коллекцию Anki
- Создание карточки через addNote с защитой от дубликатов
"""
import base64
import datetime
import html
import os
import re
import tempfile
import threading
import requests

from .config import CONFIG, data_dir

ANKI_MARKERS = [
    "{expression}",
    "{reading}",
    "{phonetic-transcriptions}",
    "{glossary}",
    "{glossary-offline}",
    "{glossary-ai}",
    "{dictionary}",
    "{glossary-brief}",
    "{glossary-first}",
    "{definition}",
    "{word-translation}",
    "{sentence}",
    "{sentence-plain}",
    "{sentence-translation}",
    "{audio}",
    "{screenshot}",
    "{part-of-speech}",
    "{frequencies}",
    "{synonyms}",
    "{document-title}",
    "{source-app}",
    "{clipboard-text}",
    "{tags}",
    "{date}",
    "(пусто)",
]

class AnkiError(Exception):
    pass


class AnkiClient:
    def __init__(self, server_url: str | None = None):
        self._server_url = server_url

    @property
    def server_url(self) -> str:
        return self._server_url or CONFIG.get("anki_server", "http://127.0.0.1:8765").rstrip("/")

    def invoke(self, action: str, **params) -> any:
        payload = {"action": action, "version": 6}
        if params:
            payload["params"] = params
        try:
            resp = requests.post(self.server_url, json=payload, timeout=3.5)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            raise AnkiError(f"Не удалось подключиться к AnkiConnect по адресу {self.server_url}. Проверьте, запущен ли Anki.")
        except requests.exceptions.Timeout:
            raise AnkiError(f"Превышено время ожидания ответа от AnkiConnect ({self.server_url}).")
        except Exception as e:
            raise AnkiError(f"Ошибка AnkiConnect: {e}")

        if not isinstance(data, dict):
            raise AnkiError("Некорректный ответ от AnkiConnect.")
        if data.get("error"):
            raise AnkiError(str(data["error"]))
        return data.get("result")

    def check_connection(self, timeout: float = 2.5) -> tuple[bool, str]:
        """Возвращает (успех, сообщение/версия). Быстрая проверка связи с таймаутом."""
        try:
            payload = {"action": "version", "version": 6}
            resp = requests.post(self.server_url, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and not data.get("error"):
                return True, f"v{data.get('result')}"
            return False, str(data.get("error", "Некорректный ответ"))
        except Exception as e:
            return False, str(e)

    def get_decks(self) -> list[str]:
        try:
            res = self.invoke("deckNames")
            return sorted(res or [])
        except Exception:
            return []

    def get_models(self) -> list[str]:
        try:
            res = self.invoke("modelNames")
            return sorted(res or [])
        except Exception:
            return []

    def get_model_fields(self, model_name: str) -> list[str]:
        if not model_name:
            return []
        try:
            res = self.invoke("modelFieldNames", modelName=model_name)
            return list(res or [])
        except Exception:
            return []

    def store_media_file(self, filename: str, data_bytes: bytes) -> str:
        b64 = base64.b64encode(data_bytes).decode("ascii")
        self.invoke("storeMediaFile", filename=filename, data=b64)
        return filename

    def store_media_from_path(self, file_path: str, target_filename: str | None = None) -> str:
        if not os.path.exists(file_path):
            return ""
        name = target_filename or os.path.basename(file_path)
        with open(file_path, "rb") as f:
            data = f.read()
        return self.store_media_file(name, data)

    def check_note_exists(self, deck: str, expression: str) -> bool:
        if not expression or not deck:
            return False
        try:
            q = f'deck:"{deck}" "{expression}"'
            res = self.invoke("findNotes", query=q)
            return bool(res)
        except Exception:
            return False

    def generate_and_store_audio(self, text: str, lang: str = "en") -> str:
        """Синтезирует аудио слова через pyttsx3 и сохраняет в медиа-коллекцию Anki."""
        if not text:
            return ""
        clean_name = re.sub(r"[^\w\-]", "_", text.strip().lower())
        ts = int(datetime.datetime.now().timestamp() * 1000)
        filename = f"wordsnap_{clean_name}_{ts}.wav"

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            import pyttsx3
            engine = pyttsx3.init()
            target = {"ru": "russian", "en": "english", "de": "german",
                      "fr": "french", "es": "spanish"}.get(lang, "")
            if target:
                for v in engine.getProperty("voices"):
                    if target in (v.name or "").lower() or target in (v.id or "").lower():
                        engine.setProperty("voice", v.id)
                        break
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            engine.stop()

            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()
            if audio_bytes:
                self.store_media_file(filename, audio_bytes)
                return filename
        except Exception as e:
            print("audio generation error:", e)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        return ""

    def store_screenshot(self, shot_filename: str) -> str:
        """Копирует скриншот из data/screenshots/ в коллекцию Anki."""
        if not shot_filename:
            return ""
        full_path = os.path.join(data_dir(), "screenshots", shot_filename)
        if not os.path.exists(full_path):
            return ""
        ts = int(datetime.datetime.now().timestamp() * 1000)
        anki_filename = f"wordsnap_shot_{ts}_{shot_filename}"
        try:
            return self.store_media_from_path(full_path, anki_filename)
        except Exception as e:
            print("screenshot store error:", e)
            return ""

    def evaluate_field_template(self, template: str, entry: dict,
                                media_cache: dict) -> str:
        """Вычисляет значение поля по шаблону с маркерами {expression}, {glossary} и т.д."""
        if not template or template.strip() in ("(пусто)", "(none)", ""):
            return ""

        val = template
        expr = entry.get("dict_form") or entry.get("word_in_text") or ""
        word_in_text = entry.get("word_in_text") or expr
        reading = entry.get("transcription") or ""
        defn = entry.get("definition") or ""
        word_tr = entry.get("word_translation") or ""
        ctx = entry.get("context") or ""
        ctx_tr = entry.get("context_translation") or entry.get("translation") or ""
        level = entry.get("level") or ""
        pos = ", ".join(entry.get("pos_tags") or [])
        syns = ", ".join(entry.get("synonyms") or [])
        doc_title = entry.get("source_title") or ""
        src_app = entry.get("source_app") or ""
        date_str = datetime.date.today().strftime("%Y-%m-%d")

        # Получаем данные офлайн-словарей
        from .dictionaries import DICTIONARIES
        offline_entries = entry.get("offline_entries")
        if offline_entries is None and expr:
            try:
                offline_entries = DICTIONARIES.lookup(expr)
            except Exception:
                offline_entries = []

        offline_html = DICTIONARIES.format_glossary_html(offline_entries or [])
        offline_brief = DICTIONARIES.format_glossary_brief(offline_entries or [])

        # Если для слова есть чтение/транскрипция в офлайн-словаре, а в AI нет:
        if not reading and offline_entries:
            for oe in offline_entries:
                if oe.get("reading"):
                    reading = oe["reading"]
                    break

        # Если для слова есть POS в офлайн-словаре:
        if not pos and offline_entries:
            poses = [oe["pos"] for oe in offline_entries if oe.get("pos")]
            if poses:
                pos = ", ".join(dict.fromkeys(poses))

        # Формирование rich glossary
        ai_parts = []
        if word_tr:
            ai_parts.append(f"<div style='font-size:1.1em; font-weight:600; margin-bottom:4px;'>{html.escape(word_tr)}</div>")
        if defn:
            ai_parts.append(f"<div style='color:#a0a0a0;'>{html.escape(defn)}</div>")
        if syns:
            ai_parts.append(f"<div style='font-size:0.9em; color:#888; margin-top:4px;'><i>Синонимы:</i> {html.escape(syns)}</div>")
        ai_glossary = "".join(ai_parts) or html.escape(word_tr or defn)

        # Главный {glossary}: если есть словарные статьи из Yomitan — используем их
        # (в точности как в скриншоте пользователя Image 3), иначе fallback на ИИ
        glossary = offline_html if offline_html else ai_glossary

        # Контекст с выделенным словом
        sentence_html = html.escape(ctx)
        if word_in_text and word_in_text in ctx:
            pattern = re.compile(re.escape(word_in_text), re.IGNORECASE)
            sentence_html = pattern.sub(lambda m: f"<b>{m.group(0)}</b>", html.escape(ctx))

        # Обработка {single-glossary-<dict_id>}
        for m in re.findall(r"\{single-glossary-([a-zA-Z0-9_\-]+)\}", val):
            s_html = DICTIONARIES.format_glossary_html(offline_entries or [], target_dict_id=m)
            val = val.replace(f"{{single-glossary-{m}}}", s_html)

        # Обработка аудио {audio}
        if "{audio}" in val:
            if "audio" not in media_cache:
                media_cache["audio"] = self.generate_and_store_audio(expr, entry.get("src_lang", "en"))
            audio_file = media_cache["audio"]
            audio_tag = f"[sound:{audio_file}]" if audio_file else ""
            val = val.replace("{audio}", audio_tag)

        # Обработка скриншота {screenshot}
        if "{screenshot}" in val:
            if "screenshot" not in media_cache:
                media_cache["screenshot"] = self.store_screenshot(entry.get("screenshot", ""))
            shot_file = media_cache["screenshot"]
            shot_tag = f'<img src="{shot_file}">' if shot_file else ""
            val = val.replace("{screenshot}", shot_tag)

        # Прочие маркеры
        replacements = {
            "{expression}": html.escape(expr),
            "{word-in-text}": html.escape(word_in_text),
            "{reading}": html.escape(reading),
            "{phonetic-transcriptions}": html.escape(reading),
            "{glossary}": glossary,
            "{glossary-offline}": offline_html,
            "{glossary-ai}": ai_glossary,
            "{dictionary}": offline_html or ai_glossary,
            "{glossary-brief}": offline_brief or html.escape(word_tr),
            "{glossary-first}": offline_brief or html.escape(word_tr or defn),
            "{definition}": html.escape(defn),
            "{word-translation}": html.escape(word_tr),
            "{sentence}": sentence_html,
            "{sentence-plain}": html.escape(ctx),
            "{sentence-translation}": html.escape(ctx_tr),
            "{part-of-speech}": html.escape(pos),
            "{frequencies}": html.escape(level),
            "{synonyms}": html.escape(syns),
            "{document-title}": html.escape(doc_title),
            "{source-app}": html.escape(src_app),
            "{tags}": html.escape(CONFIG.get("anki_tags", "wordsnap")),
            "{date}": date_str,
            "{clipboard-text}": "",
        }

        for marker, sub in replacements.items():
            val = val.replace(marker, sub)

        return val.strip()

    def add_word_note(self, entry: dict, deck: str | None = None,
                      model: str | None = None,
                      field_mappings: dict[str, str] | None = None,
                      tags: list[str] | None = None) -> int:
        """Создает и добавляет карточку слова в Anki."""
        deck = deck or CONFIG.get("anki_deck")
        model = model or CONFIG.get("anki_model")
        if not deck:
            decks = self.get_decks()
            deck = decks[0] if decks else "Default"
            CONFIG.set("anki_deck", deck)

        if not model:
            models = self.get_models()
            model = models[0] if models else "Basic"
            CONFIG.set("anki_model", model)

        model_fields = self.get_model_fields(model)
        if not model_fields:
            raise AnkiError(f"Не удалось получить поля модели '{model}' из Anki.")

        if not field_mappings:
            saved_fields = CONFIG.get("anki_fields", {})
            field_mappings = saved_fields.get(model, {})

        # Если для модели нет настроенных полей, генерируем умные дефолты
        if not field_mappings:
            field_mappings = {}
            for f in model_fields:
                fl = f.lower()
                if "front" in fl or "word" in fl or "выражение" in fl or "термин" in fl:
                    field_mappings[f] = "{expression}"
                elif "back" in fl or "glossary" in fl or "перевод" in fl or "значение" in fl:
                    field_mappings[f] = "{glossary}"
                elif "reading" in fl or "transcription" in fl or "чтение" in fl:
                    field_mappings[f] = "{reading}"
                elif "sentence" in fl or "context" in fl or "пример" in fl:
                    field_mappings[f] = "{sentence}"
                elif "image" in fl or "picture" in fl or "screenshot" in fl or "картинка" in fl:
                    field_mappings[f] = "{screenshot}"
                elif "audio" in fl or "sound" in fl or "звук" in fl:
                    field_mappings[f] = "{audio}"
                else:
                    field_mappings[f] = ""

        # Вычисляем значения полей
        resolved_fields = {}
        media_cache = {}
        for f in model_fields:
            template = field_mappings.get(f, "")
            resolved_fields[f] = self.evaluate_field_template(template, entry, media_cache)

        # Теги
        if tags is None:
            tag_cfg = CONFIG.get("anki_tags", "wordsnap")
            tags = [t.strip() for t in re.split(r"[,\s]+", tag_cfg) if t.strip()]

        dup_scope = CONFIG.get("anki_duplicate_scope", "deck")

        note_data = {
            "deckName": deck,
            "modelName": model,
            "fields": resolved_fields,
            "options": {
                "allowDuplicate": False,
                "duplicateScope": dup_scope,
            },
            "tags": tags,
        }

        note_id = self.invoke("addNote", note=note_data)
        return note_id


_CLIENT: AnkiClient | None = None

def get_anki_client(*args, **kwargs) -> AnkiClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = AnkiClient()
    return _CLIENT
