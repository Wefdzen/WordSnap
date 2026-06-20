"""OCR-движки: Windows OCR (winrt) — рекомендуемый, Tesseract — запасной.
Архитектура как в Translumo: единый интерфейс, разные движки."""
import io
import re
import sys
from dataclasses import dataclass

from PIL import Image

@dataclass
class OcrWord:
    text: str
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self): return self.x + self.w / 2
    @property
    def cy(self): return self.y + self.h / 2

@dataclass
class OcrLine:
    text: str
    x: float
    y: float
    w: float
    h: float
    words: list

OCR_LANG_TAGS = {  # код языка -> BCP-47 для Windows OCR / код tesseract
    "ru": ("ru-RU", "rus"), "en": ("en-US", "eng"), "de": ("de-DE", "deu"),
    "fr": ("fr-FR", "fra"), "es": ("es-ES", "spa"), "ja": ("ja-JP", "jpn"),
    "zh": ("zh-CN", "chi_sim"), "ko": ("ko-KR", "kor"), "uk": ("uk-UA", "ukr"),
}

# ---------------------------------------------------------------- Windows OCR
class WindowsOcrEngine:
    name = "Рекомендуемый (Windows OCR)"

    def __init__(self, lang: str):
        self.lang_tag = OCR_LANG_TAGS.get(lang, ("en-US", "eng"))[0]

    def recognize(self, image: Image.Image) -> list[OcrLine]:
        import asyncio
        return asyncio.run(self._recognize_async(image))

    async def _recognize_async(self, image: Image.Image) -> list[OcrLine]:
        try:  # новый pywinrt (Python 3.13/3.14+)
            from winrt.windows.media.ocr import OcrEngine as WinOcr
            from winrt.windows.globalization import Language
            from winrt.windows.graphics.imaging import BitmapDecoder
            from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
        except ImportError:  # устаревший winsdk (Python <= 3.12)
            from winsdk.windows.media.ocr import OcrEngine as WinOcr
            from winsdk.windows.globalization import Language
            from winsdk.windows.graphics.imaging import BitmapDecoder
            from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream.get_output_stream_at(0))
        writer.write_bytes(buf.getvalue())
        await writer.store_async()
        await writer.flush_async()
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()

        engine = None
        try:
            engine = WinOcr.try_create_from_language(Language(self.lang_tag))
        except Exception:
            pass
        if engine is None:
            # Запрошенный язык не установлен. Раньше тут была тихая подмена на
            # системный язык — но он распознаёт чужой текст (например японский)
            # как мусор. Поэтому честно сообщаем, как доустановить пакет.
            avail = []
            try:
                for lng in WinOcr.available_recognizer_languages:
                    avail.append(lng.display_name)
            except Exception:
                pass
            msg = (f"Windows OCR для языка «{self.lang_tag}» не установлен.\n"
                   "Поставьте его: Параметры Windows → Время и язык → Язык и регион → "
                   "добавьте язык, затем в его «Параметрах языка» включите распознавание текста.")
            if avail:
                msg += "\nСейчас доступны: " + ", ".join(avail) + "."
            raise RuntimeError(msg)

        result = await engine.recognize_async(bitmap)
        lines: list[OcrLine] = []
        for line in result.lines:
            words = []
            for w in line.words:
                r = w.bounding_rect
                words.append(OcrWord(w.text, r.x, r.y, r.width, r.height))
            if not words:
                continue
            x0 = min(w.x for w in words); y0 = min(w.y for w in words)
            x1 = max(w.x + w.w for w in words); y1 = max(w.y + w.h for w in words)
            lines.append(OcrLine(line.text, x0, y0, x1 - x0, y1 - y0, words))
        return lines

# ----------------------------------------------------------------- Tesseract
class TesseractEngine:
    name = "Tesseract"

    def __init__(self, lang: str):
        self.lang = OCR_LANG_TAGS.get(lang, ("en-US", "eng"))[1]

    def recognize(self, image: Image.Image) -> list[OcrLine]:
        import pytesseract
        data = pytesseract.image_to_data(image, lang=self.lang,
                                         output_type=pytesseract.Output.DICT)
        lines_map: dict[tuple, list[OcrWord]] = {}
        n = len(data["text"])
        for i in range(n):
            txt = data["text"][i].strip()
            if not txt:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines_map.setdefault(key, []).append(
                OcrWord(txt, data["left"][i], data["top"][i], data["width"][i], data["height"][i]))
        lines = []
        for words in lines_map.values():
            words.sort(key=lambda w: w.x)
            x0 = min(w.x for w in words); y0 = min(w.y for w in words)
            x1 = max(w.x + w.w for w in words); y1 = max(w.y + w.h for w in words)
            lines.append(OcrLine(" ".join(w.text for w in words), x0, y0, x1 - x0, y1 - y0, words))
        lines.sort(key=lambda l: (l.y, l.x))
        return lines

def get_engine(cfg) -> "WindowsOcrEngine | TesseractEngine":
    choice = cfg.get("ocr_engine", "auto")
    lang = cfg.get("ocr_lang", "en")
    if choice == "tesseract":
        return TesseractEngine(lang)
    if choice == "windows" or (choice == "auto" and sys.platform == "win32"):
        try:
            import winrt.windows.media.ocr  # noqa: F401
            return WindowsOcrEngine(lang)
        except ImportError:
            pass
        try:
            import winsdk  # noqa: F401
            return WindowsOcrEngine(lang)
        except ImportError:
            pass
    return TesseractEngine(lang)

# ------------------------------------------------------- работа с результатом
_WORD_RX = re.compile(r"[\w'’\-]+", re.UNICODE)

def clean_word(text: str) -> str:
    m = _WORD_RX.search(text)
    return m.group(0) if m else text.strip()

def word_at_point(lines: list[OcrLine], px: float, py: float):
    """Слово под точкой (курсором) или ближайшее к ней. Возвращает (line, word) | (None, None)."""
    best, best_line, best_d = None, None, 1e18
    for line in lines:
        for w in line.words:
            if w.x <= px <= w.x + w.w and w.y <= py <= w.y + w.h:
                return line, w
            d = (w.cx - px) ** 2 + (w.cy - py) ** 2
            if d < best_d:
                best_d, best, best_line = d, w, line
    if best is not None and best_d < 200 ** 2:
        return best_line, best
    return None, None

def sentence_around(lines: list[OcrLine], target_line: OcrLine, target_word: OcrWord) -> str:
    """Предложение вокруг слова — только из той же колонки текста (без чужих блоков,
    меню и боковых столбцов), и только из строк, идущих подряд по вертикали."""
    # строки той же колонки: их горизонтальный диапазон пересекается с целевой строкой
    def x_overlap(l):
        return min(l.x + l.w, target_line.x + target_line.w) - max(l.x, target_line.x)
    col = sorted([l for l in lines if x_overlap(l) > 0.3 * min(l.w, target_line.w)],
                 key=lambda l: l.y)
    try:
        idx = col.index(target_line)
    except ValueError:
        return target_line.text.strip()

    def adjacent(a, b):  # b идёт сразу под a (один абзац, без большого разрыва)
        gap = b.y - (a.y + a.h)
        return -a.h * 0.6 <= gap <= a.h * 1.2

    # непрерывный вертикальный блок строк вокруг целевой
    block = [target_line]
    i = idx - 1
    while i >= 0 and adjacent(col[i], block[0]):
        block.insert(0, col[i]); i -= 1
    j = idx + 1
    while j < len(col) and adjacent(block[-1], col[j]):
        block.append(col[j]); j += 1

    chunk = " ".join(l.text for l in block)
    parts = re.split(r"(?<=[.!?…])\s+", chunk)
    for p in parts:
        if target_word.text in p:
            return p.strip()
    return target_line.text.strip()
