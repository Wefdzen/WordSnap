"""Хранилище слов: data/words.json + скриншоты в data/screenshots/ (без БД)."""
import json
import os
import time
import uuid
import csv

from .config import data_dir

WORDS_PATH = lambda: os.path.join(data_dir(), "words.json")
SHOTS_DIR = lambda: os.path.join(data_dir(), "screenshots")

# Структура записи слова:
# {
#   "id": str, "created": float,
#   "src_lang": "en", "dst_lang": "ru",
#   "dict_form": "long", "word_in_text": "longer",
#   "level": "A1", "transcription": "/lɒŋ/",
#   "pos_tags": ["Прилагательное"],
#   "definition": "...", "word_translation": "длинный",
#   "synonyms": ["lengthy", ...],
#   "context": "...", "context_translation": "...",
#   "source_app": "...", "source_title": "...",
#   "screenshot": "имя_файла.png" | "",
#   "complete": bool  # все ли данные ИИ получены
# }

class WordsStore:
    def __init__(self):
        self.items: list[dict] = []
        self.load()

    def load(self):
        try:
            with open(WORDS_PATH(), "r", encoding="utf-8") as f:
                self.items = json.load(f)
        except FileNotFoundError:
            self.items = []
        except Exception as e:
            print("words load error:", e)
            self.items = []

    def save(self):
        with open(WORDS_PATH(), "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)

    def add(self, entry: dict) -> dict:
        entry.setdefault("id", uuid.uuid4().hex)
        entry.setdefault("created", time.time())
        entry.setdefault("complete", False)
        entry.setdefault("favorite", False)
        entry.setdefault("tags", [])
        self.items.insert(0, entry)
        self.save()
        return entry

    def toggle_favorite(self, entry_id: str) -> bool:
        for it in self.items:
            if it["id"] == entry_id:
                it["favorite"] = not it.get("favorite", False)
                self.save()
                return it["favorite"]
        return False

    def update(self, entry_id: str, **fields):
        for it in self.items:
            if it["id"] == entry_id:
                it.update(fields)
                break
        self.save()

    def get(self, entry_id: str):
        for it in self.items:
            if it["id"] == entry_id:
                return it
        return None

    def delete(self, ids: list[str]):
        keep = []
        for it in self.items:
            if it["id"] in ids:
                shot = it.get("screenshot")
                if shot:
                    try:
                        os.remove(os.path.join(SHOTS_DIR(), shot))
                    except OSError:
                        pass
            else:
                keep.append(it)
        self.items = keep
        self.save()

    def incomplete(self) -> list[dict]:
        return [it for it in self.items if not it.get("complete")]

    # ---------- скриншоты ----------
    def save_screenshot(self, pil_image, max_w: int = 1280) -> str:
        """Сохраняет уменьшенный JPEG — лёгкий по весу и аккуратный в превью."""
        img = pil_image
        if img.width > max_w:  # ужимаем большие (полноэкранные) скрины
            h = round(img.height * max_w / img.width)
            img = img.resize((max_w, h))
        name = f"{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}.jpg"
        img.convert("RGB").save(os.path.join(SHOTS_DIR(), name), "JPEG", quality=72)
        return name

    def screenshot_path(self, name: str) -> str:
        return os.path.join(SHOTS_DIR(), name)

    # ---------- экспорт ----------
    def export(self, path: str, ids: list[str] | None = None):
        items = [it for it in self.items if ids is None or it["id"] in ids]
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":
            with open(path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        elif ext == ".csv":
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Слово", "Перевод", "Уровень", "Транскрипция",
                            "Определение", "Контекст", "Перевод контекста", "Синонимы"])
                for it in items:
                    w.writerow([it.get("dict_form", ""), it.get("word_translation", ""),
                                it.get("level", ""), it.get("transcription", ""),
                                it.get("definition", ""), it.get("context", ""),
                                it.get("context_translation", ""),
                                ", ".join(it.get("synonyms", []))])
        else:  # .txt / Anki TSV
            import shutil
            # картинки кладём в папку рядом с файлом — её содержимое нужно скопировать
            # в collection.media профиля Anki, тогда <img> в карточках заработают
            media_dir = os.path.splitext(path)[0] + "_media"
            if any(it.get("screenshot") for it in items):
                os.makedirs(media_dir, exist_ok=True)

            def clean(s: str) -> str:
                return (s or "").replace("\t", " ").replace("\r", "").replace("\n", "<br>")

            with open(path, "w", encoding="utf-8", newline="") as f:
                # заголовки Anki: разделитель — таб, поля парсятся как HTML (для <img>)
                f.write("#separator:tab\n#html:true\n")
                f.write("#columns:Word\tTranslation\tDefinition\tContext\tImage\n")
                for it in items:
                    img = ""
                    shot = it.get("screenshot", "")
                    if shot:
                        src = os.path.join(SHOTS_DIR(), shot)
                        if os.path.exists(src):
                            try:
                                shutil.copy(src, os.path.join(media_dir, shot))
                                img = f'<img src="{shot}">'
                            except OSError:
                                pass
                    row = [it.get("dict_form", ""), it.get("word_translation", ""),
                           it.get("definition", ""), it.get("context", ""), img]
                    f.write("\t".join(clean(c) for c in row) + "\n")

WORDS = WordsStore()
