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

def preprocess_for_game_ocr(image: Image.Image, scale: float = 2.0) -> tuple[Image.Image, float]:
    """Предобработка для игр с тёмным UI, мелким или стилизованным шрифтом:
    масштабирование Bicubic + автоконтраст + усиление резкости."""
    from PIL import ImageOps, ImageFilter
    w, h = max(1, int(image.width * scale)), max(1, int(image.height * scale))
    up = image.resize((w, h), Image.Resampling.BICUBIC)
    gray = up.convert("L")
    contrast = ImageOps.autocontrast(gray, cutoff=1)
    sharp = contrast.filter(ImageFilter.SHARPEN)
    return sharp, scale

def check_windows_ocr_language(lang_code: str) -> tuple[bool, str, list[str]]:
    """Проверяет доступность Windows OCR для указанного языка (код 'en', 'ja', 'zh'...).
    Возвращает (is_available, tag, available_list)."""
    lang_tag = OCR_LANG_TAGS.get(lang_code, ("en-US", "eng"))[0]
    avail = []
    try:
        try:
            from winrt.windows.media.ocr import OcrEngine as WinOcr
            from winrt.windows.globalization import Language
        except ImportError:
            import importlib
            WinOcr = importlib.import_module("winsdk.windows.media.ocr").OcrEngine
            Language = importlib.import_module("winsdk.windows.globalization").Language

        for lng in WinOcr.available_recognizer_languages:
            avail.append(lng.display_name)

        engine = None
        try:
            engine = WinOcr.try_create_from_language(Language(lang_tag))
        except Exception:
            pass
        if engine is None and "-" in lang_tag:
            try:
                engine = WinOcr.try_create_from_language(Language(lang_tag.split("-")[0]))
            except Exception:
                pass
        return (engine is not None, lang_tag, avail)
    except Exception:
        return (False, lang_tag, avail)


def get_ocr_missing_instructions(lang_tag: str, avail_names: list[str]) -> str:
    """Возвращает подробную двуязычную инструкцию по установке OCR для языка."""
    from .config import CONFIG
    is_en = CONFIG.get("ui_lang", "ru") == "en"
    avail_str = ", ".join(avail_names) if avail_names else ("none" if is_en else "нет")

    if is_en:
        return (
            f"Windows OCR for language «{lang_tag}» is not installed.\n\n"
            "How to install:\n"
            "1. Open Windows Settings → Time & language → Language & region → Add a language.\n"
            "2. Select your language (the OCR package is installed automatically by Windows; if not, check the 'Optical character recognition' box).\n"
            "3. 💡 Tip: After installation, you can remove the keyboard layout if you don't need it — the OCR engine will remain in Windows!\n\n"
            f"Currently available OCR languages in system: {avail_str}."
        )
    else:
        return (
            f"Windows OCR для языка «{lang_tag}» не установлен.\n\n"
            "Как установить:\n"
            "1. Откройте Параметры Windows → Время и язык → Язык и регион → Добавить язык.\n"
            "2. Выберите нужный язык (компонент OCR скачивается автоматически; если не скачался — проверьте наличие галочки «Распознавание текста»).\n"
            "3. 💡 Совет: После установки саму раскладку клавиатуры можно удалить — модуль OCR останется в системе!\n\n"
            f"Сейчас доступны в системе: {avail_str}."
        )


# ---------------------------------------------------------------- Windows OCR
class WindowsOcrEngine:
    name = "Рекомендуемый (Windows OCR)"

    def __init__(self, lang: str):
        self.lang_code = lang
        self.lang_tag = OCR_LANG_TAGS.get(lang, ("en-US", "eng"))[0]

    def recognize(self, image: Image.Image) -> list[OcrLine]:
        import asyncio
        # Обязательный Bicubic апскейл для CJK (2x для кропа <= 900*600, 1.5x для полноэкранного оверлея)
        is_cjk = (self.lang_tag.startswith(("ja", "zh", "ko")) or
                  self.lang_code in ("ja", "zh", "ko", "jpn", "chi_sim", "kor"))
        if is_cjk and image.width >= 16 and image.height >= 16:
            scale = 2.0 if (image.width * image.height <= 900 * 600) else 1.5
            w2 = max(1, int(image.width * scale))
            h2 = max(1, int(image.height * scale))
            scaled_img = image.resize((w2, h2), Image.Resampling.BICUBIC)
            raw_lines = asyncio.run(self._recognize_async(scaled_img))
            scaled_lines = []
            for l in raw_lines:
                words = [OcrWord(w.text, w.x / scale, w.y / scale, w.w / scale, w.h / scale)
                         for w in l.words]
                scaled_lines.append(OcrLine(
                    l.text, l.x / scale, l.y / scale, l.w / scale, l.h / scale, words
                ))
            return postprocess_cjk_lines(scaled_lines)

        lines = asyncio.run(self._recognize_async(image))
        total_words = sum(len(l.words) for l in lines)

        # Если найдено мало слов (характерно для тёмного UI игр, светящихся или мелких шрифтов),
        # автоматически запускаем второй улучшенный проход с масштабированием и контрастом
        if total_words < 3 and image.width >= 16 and image.height >= 16:
            try:
                enhanced, scale = preprocess_for_game_ocr(image, scale=2.0)
                enh_lines = asyncio.run(self._recognize_async(enhanced))
                enh_words = sum(len(l.words) for l in enh_lines)
                if enh_words > total_words:
                    scaled_lines = []
                    for l in enh_lines:
                        words = [OcrWord(w.text, w.x / scale, w.y / scale, w.w / scale, w.h / scale)
                                 for w in l.words]
                        scaled_lines.append(OcrLine(
                            l.text, l.x / scale, l.y / scale, l.w / scale, l.h / scale, words
                        ))
                    return postprocess_cjk_lines(scaled_lines)
            except Exception:
                pass
        return postprocess_cjk_lines(lines)

    async def _recognize_async(self, image: Image.Image) -> list[OcrLine]:
        try:  # новый pywinrt (Python 3.13/3.14+)
            from winrt.windows.media.ocr import OcrEngine as WinOcr
            from winrt.windows.globalization import Language
            from winrt.windows.graphics.imaging import (
                BitmapDecoder, BitmapPixelFormat, BitmapAlphaMode, SoftwareBitmap
            )
            from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
        except ImportError:  # устаревший winsdk (Python <= 3.12)
            import importlib
            WinOcr = importlib.import_module("winsdk.windows.media.ocr").OcrEngine
            Language = importlib.import_module("winsdk.windows.globalization").Language
            _img_mod = importlib.import_module("winsdk.windows.graphics.imaging")
            BitmapDecoder = _img_mod.BitmapDecoder
            BitmapPixelFormat = _img_mod.BitmapPixelFormat
            BitmapAlphaMode = _img_mod.BitmapAlphaMode
            SoftwareBitmap = _img_mod.SoftwareBitmap
            _streams_mod = importlib.import_module("winsdk.windows.storage.streams")
            InMemoryRandomAccessStream = _streams_mod.InMemoryRandomAccessStream
            DataWriter = _streams_mod.DataWriter

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
        if engine is None and "-" in self.lang_tag:
            try:
                engine = WinOcr.try_create_from_language(Language(self.lang_tag.split("-")[0]))
            except Exception:
                pass

        if engine is None:
            # Запрошенный язык не установлен. Сообщаем понятную инструкцию на языке пользователя.
            avail = []
            try:
                for lng in WinOcr.available_recognizer_languages:
                    avail.append(lng.display_name)
            except Exception:
                pass
            msg = get_ocr_missing_instructions(self.lang_tag, avail)
            raise RuntimeError(msg)

        try:
            result = await engine.recognize_async(bitmap)
        except Exception:
            # На Windows 10 старых ревизий API BitmapDecoder может требовать конвертации
            # SoftwareBitmap в формат Bgra8 / Premultiplied перед передачей в recognize_async
            bgra8 = getattr(BitmapPixelFormat, "BGRA8", getattr(BitmapPixelFormat, "Bgra8", None))
            premul = getattr(BitmapAlphaMode, "PREMULTIPLIED", getattr(BitmapAlphaMode, "Premultiplied", None))
            converted = None
            if bgra8 is not None and premul is not None:
                try:
                    converted = SoftwareBitmap.convert(bitmap, bgra8, premul)
                except Exception:
                    try:
                        converted = SoftwareBitmap.convert(bitmap, bgra8)
                    except Exception:
                        converted = None
            elif bgra8 is not None:
                try:
                    converted = SoftwareBitmap.convert(bitmap, bgra8)
                except Exception:
                    converted = None

            if converted is not None:
                result = await engine.recognize_async(converted)
            else:
                raise
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
        self.lang_code = lang
        self.lang = OCR_LANG_TAGS.get(lang, ("en-US", "eng"))[1]

    def _recognize_raw(self, image: Image.Image) -> list[OcrLine]:
        import pytesseract
        from .config import CONFIG
        custom_cmd = (CONFIG.get("tesseract_path") or "").strip()
        if custom_cmd:
            pytesseract.pytesseract.tesseract_cmd = custom_cmd

        data = pytesseract.image_to_data(image, lang=self.lang,
                                         output_type=pytesseract.Output.DICT)
        lines_map: dict[tuple, list[OcrWord]] = {}
        n = len(data["text"])
        for i in range(n):
            txt = data["text"][i].strip()
            if not txt:
                continue
            try:
                if int(data["conf"][i]) < 15:
                    continue
            except (ValueError, TypeError):
                pass
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

    def recognize(self, image: Image.Image) -> list[OcrLine]:
        # Обязательный Bicubic апскейл для CJK (2x для кропа <= 900*600, 1.5x для полноэкранного оверлея)
        is_cjk = (self.lang in ("jpn", "chi_sim", "kor") or
                  self.lang_code in ("ja", "zh", "ko", "jpn", "chi_sim", "kor"))
        if is_cjk and image.width >= 16 and image.height >= 16:
            scale = 2.0 if (image.width * image.height <= 900 * 600) else 1.5
            w2 = max(1, int(image.width * scale))
            h2 = max(1, int(image.height * scale))
            scaled_img = image.resize((w2, h2), Image.Resampling.BICUBIC)
            raw_lines = self._recognize_raw(scaled_img)
            scaled_lines = []
            for l in raw_lines:
                words = [OcrWord(w.text, w.x / scale, w.y / scale, w.w / scale, w.h / scale)
                         for w in l.words]
                scaled_lines.append(OcrLine(
                    l.text, l.x / scale, l.y / scale, l.w / scale, l.h / scale, words
                ))
            return postprocess_cjk_lines(scaled_lines)

        lines = self._recognize_raw(image)
        total_words = sum(len(l.words) for l in lines)
        if total_words < 3 and image.width >= 16 and image.height >= 16:
            try:
                enhanced, scale = preprocess_for_game_ocr(image, scale=2.0)
                enh_lines = self._recognize_raw(enhanced)
                enh_words = sum(len(l.words) for l in enh_lines)
                if enh_words > total_words:
                    scaled_lines = []
                    for l in enh_lines:
                        words = [OcrWord(w.text, w.x / scale, w.y / scale, w.w / scale, w.h / scale)
                                 for w in l.words]
                        scaled_lines.append(OcrLine(
                            l.text, l.x / scale, l.y / scale, l.w / scale, l.h / scale, words
                        ))
                    return postprocess_cjk_lines(scaled_lines)
            except Exception:
                pass
        return postprocess_cjk_lines(lines)

def is_cjk_char(ch: str) -> bool:
    """Проверяет, относится ли символ к китайским, японским или корейским иероглифам/слогам."""
    if not ch:
        return False
    cp = ord(ch)
    return (
        # Hiragana & Katakana
        (0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF) or
        # CJK Unified Ideographs & extensions (Kanji / Hanzi)
        (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or
        # CJK Compatibility Ideographs
        (0xF900 <= cp <= 0xFAFF) or
        # Hangul Syllables & Jamo
        (0xAC00 <= cp <= 0xD7AF) or (0x1100 <= cp <= 0x11FF) or (0x3130 <= cp <= 0x318F)
    )

def is_japanese_char(ch: str) -> bool:
    if not ch: return False
    cp = ord(ch)
    return ((0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF) or
            (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF))

def is_hiragana(ch: str) -> bool:
    return bool(ch and 0x3040 <= ord(ch) <= 0x309F)

def is_katakana(ch: str) -> bool:
    return bool(ch and 0x30A0 <= ord(ch) <= 0x30FF)

def is_kanji(ch: str) -> bool:
    return bool(ch and ((0x4E00 <= ord(ch) <= 0x9FFF) or (0x3400 <= ord(ch) <= 0x4DBF)))

def is_hangul(ch: str) -> bool:
    if not ch: return False
    cp = ord(ch)
    return ((0xAC00 <= cp <= 0xD7AF) or (0x1100 <= cp <= 0x11FF) or (0x3130 <= cp <= 0x318F))

def has_cjk(text: str) -> bool:
    return any(is_cjk_char(c) for c in text)

JA_PARTICLES = {
    "は", "が", "を", "に", "へ", "と", "の", "も", "や", "か", "ね", "よ",
    "わ", "ぞ", "ぜ", "から", "まで", "より", "だけ", "ばかり", "ほど", "くらい", "ぐらい", "など"
}

def postprocess_cjk_lines(lines: list[OcrLine]) -> list[OcrLine]:
    """Умная группировка OCR-боксов для CJK-языков (японский, китайский, корейский).
    - Для корейского: склеивает слоги хангыля, стоящие вплотную друг к другу (без пробела).
    - Для японского/китайского: склеивает цепочки кандзи (составные слова), кандзи + окуригану (глаголы/прилагательные)
      и цепочки катаканы (заимствованные слова)."""
    processed_lines = []
    for line in lines:
        if not line.words or not any(has_cjk(w.text) for w in line.words):
            processed_lines.append(line)
            continue

        words = sorted(line.words, key=lambda w: w.x)
        merged: list[OcrWord] = []
        i = 0
        n = len(words)

        while i < n:
            curr = words[i]
            # Пытаемся поглотить следующие боксы
            while i + 1 < n:
                nxt = words[i + 1]
                # Расстояние по горизонтали между текущим и следующим боксом
                gap = nxt.x - (curr.x + curr.w)
                avg_char_w = max(curr.w / max(1, len(curr.text)), nxt.w / max(1, len(nxt.text)))

                # Если между ними большой пробел или разрыв строк — не склеиваем
                if gap > avg_char_w * 0.7 or gap < -avg_char_w * 0.8:
                    break

                curr_txt = curr.text.strip()
                nxt_txt = nxt.text.strip()
                if not curr_txt or not nxt_txt:
                    break

                should_merge = False

                # 1. Корейский (Hangul): слоги хангыля вплотную друг к другу
                if all(is_hangul(c) for c in curr_txt) and all(is_hangul(c) for c in nxt_txt):
                    if gap <= avg_char_w * 0.55:
                        should_merge = True

                # 2. Японский: Катакана + Катакана
                elif all(is_katakana(c) for c in curr_txt) and all(is_katakana(c) for c in nxt_txt):
                    if gap <= avg_char_w * 0.6:
                        should_merge = True

                # 3. Японский / Китайский: Кандзи + Кандзи (составное слово из 2-4 иероглифов)
                elif all(is_kanji(c) for c in curr_txt) and all(is_kanji(c) for c in nxt_txt):
                    if len(curr_txt) + len(nxt_txt) <= 6 and gap <= avg_char_w * 0.5:
                        should_merge = True

                # 4. Японский: Кандзи + Хирагана (окуригана / глагольные окончания, напр. 願 + い, 食 + べる, お願い + します)
                elif any(is_kanji(c) for c in curr_txt) and all(is_hiragana(c) for c in nxt_txt):
                    trailing_hira = 0
                    for ch in reversed(curr_txt):
                        if is_hiragana(ch):
                            trailing_hira += 1
                        else:
                            break

                    ends_with_kanji = bool(curr_txt and is_kanji(curr_txt[-1]))
                    is_particle = nxt_txt in JA_PARTICLES or any(nxt_txt.startswith(p) for p in JA_PARTICLES)

                    # Если слово заканчивается на кандзи (существительное) и следующий бокс — частица (напр. 水 + を), не склеиваем
                    if ends_with_kanji and is_particle:
                        should_merge = False
                    elif (trailing_hira + len(nxt_txt) <= 6) and gap <= avg_char_w * 0.65:
                        # Также не приклеиваем падежные частицы (を, が, は) к уже сформированному слову
                        if not (trailing_hira > 0 and nxt_txt in ("を", "が", "は")):
                            should_merge = True

                # 5. Японский: Префикс вежливости (お / ご) + Кандзи (напр. お + 願 + い)
                elif curr_txt in ("お", "ご", "御") and any(is_kanji(c) for c in nxt_txt):
                    if gap <= avg_char_w * 0.6:
                        should_merge = True

                if should_merge:
                    mx = min(curr.x, nxt.x)
                    my = min(curr.y, nxt.y)
                    mr = max(curr.x + curr.w, nxt.x + nxt.w)
                    mb = max(curr.y + curr.h, nxt.y + nxt.h)
                    curr = OcrWord(curr.text + nxt.text, mx, my, mr - mx, mb - my)
                    i += 1
                else:
                    break

            merged.append(curr)
            i += 1

        x0 = min(w.x for w in merged) if merged else line.x
        y0 = min(w.y for w in merged) if merged else line.y
        x1 = max(w.x + w.w for w in merged) if merged else line.x + line.w
        y1 = max(w.y + w.h for w in merged) if merged else line.y + line.h
        processed_lines.append(OcrLine(line.text, x0, y0, x1 - x0, y1 - y0, merged))

    return processed_lines

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
            import importlib
            importlib.import_module("winsdk")
            return WindowsOcrEngine(lang)
        except Exception:
            pass
    return TesseractEngine(lang)

# ------------------------------------------------------- работа с результатом
_WORD_RX = re.compile(r"[\w'’\-]+", re.UNICODE)
CJK_PUNCT = " [](){}<>\"'«».,:;!?*~`_「」『』【】〔〕〈〉《》・…！？：；、。"

def clean_word(text: str) -> str:
    cleaned = text.strip(CJK_PUNCT)
    m = _WORD_RX.search(cleaned)
    return m.group(0) if m else cleaned

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
    if best is not None and best_d < 260 ** 2:
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
        b_txt = b.text.lstrip()
        if any(b_txt.startswith(m) for m in ("•", "・", "-", "*", "(")):
            return False
        gap = b.y - (a.y + a.h)
        return -a.h * 0.6 <= gap <= a.h * 0.45

    # непрерывный вертикальный блок строк вокруг целевой
    block = [target_line]
    i = idx - 1
    while i >= 0 and adjacent(col[i], block[0]):
        block.insert(0, col[i]); i -= 1
    j = idx + 1
    while j < len(col) and adjacent(block[-1], col[j]):
        block.append(col[j]); j += 1

    chunk = "\n".join(l.text for l in block)
    parts = re.split(r"(?<=[.!?…。！？])\s+|\n+", chunk)
    w_clean = clean_word(target_word.text)
    for p in parts:
        p_clean = p.strip()
        if target_word.text in p_clean or (w_clean and w_clean in p_clean):
            return p_clean
    return target_line.text.strip()
