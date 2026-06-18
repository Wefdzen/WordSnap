"""ИИ-источники для перевода и словаря. Поддерживаются два провайдера:
  • Groq  — самый быстрый (<1 сек), без региональных блокировок: https://console.groq.com/keys
  • Gemini — Google AI Studio: https://aistudio.google.com/apikey
Переводчик — контекстный перевод экранного текста.
Looktionary — ИИ-словарь: значение слова в контексте, уровень, транскрипция и т.д."""
import json
import re
import threading
import time

import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

MIN_INTERVAL = 0.0   # сек: минимальная пауза между запросами (0 = без throttle, максимум скорости)
MAX_RETRIES = 2      # повторов при 429 (rate limit)
MAX_RETRY_WAIT = 8   # сек: дольше этого ждать повтор не будем (чтобы не подвисать)

class GeminiError(Exception):
    """Историческое имя ошибки ИИ-провайдера (используется по всему коду)."""
    pass

AIError = GeminiError  # понятный псевдоним

def _parse_json(text: str):
    """Убирает ```json-обёртку и парсит JSON из ответа модели."""
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)

# ============================================================ базовый клиент
class _AIBase:
    """Общая логика: промпты Переводчика и Looktionary. Подклассы реализуют _generate()."""
    name = "ИИ"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self._lock = threading.Lock()
        self._last_call = 0.0

    @property
    def ready(self) -> bool:
        return bool(self.api_key)

    def _throttle(self):
        """Пауза не меньше MIN_INTERVAL между запросами (потокобезопасно)."""
        if MIN_INTERVAL <= 0:
            return
        with self._lock:
            wait = MIN_INTERVAL - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    # --- реализуется в подклассе ---
    def _generate(self, prompt: str, json_mode: bool = True, timeout: int = 40):
        raise NotImplementedError

    def check_key(self) -> str:
        self._generate('Ответь строго JSON: {"ok": true}')
        return "OK"

    # ------------------------------------------------------- Переводчик
    def translate_sentence(self, sentence: str, target_lang: str, word: str = "",
                           app_context: str = "") -> str:
        prompt = (
            "Ты — Переводчик, профессиональный ИИ-переводчик экранного текста из игр, "
            "приложений и видео.\n"
            f"Текст распознан OCR с экрана приложения «{app_context or 'неизвестно'}» и может содержать "
            "ошибки распознавания: перепутанные буквы, склейки слов, смешение алфавитов "
            "(например, кириллица, прочитанная латиницей). Сначала мысленно восстанови, что было "
            "написано на самом деле, с учётом игрового лора и терминологии.\n"
            f"Затем переведи восстановленный текст на язык [{target_lang}] — естественно, грамотно "
            "и литературно. Переводи СМЫСЛ, не транслитерируй и не копируй исходные буквы.\n"
            f"В ответе дай ТОЛЬКО перевод на язык [{target_lang}], без пояснений и без исходного текста.\n"
            + (f"Слово «{word}» в переводе оберни тегами <u></u> (его точное соответствие).\n" if word else "")
            + f'Распознанный текст: """{sentence}"""\n'
            'Ответ строго JSON: {"translation": "..."}'
        )
        return self._generate(prompt)["translation"]

    def translate_lines(self, lines: list[str], target_lang: str, app_context: str = "") -> list[str]:
        prompt = (
            "Ты — Переводчик: ИИ-переводчик экранного текста. "
            f"Источник — экран приложения «{app_context or 'неизвестно'}». "
            "Исправляй мелкие OCR-ошибки по смыслу, сохраняй стиль.\n"
            f"Переведи каждую строку массива на язык [{target_lang}]. "
            'Верни строго JSON вида {"lines": [...]} — массив строк той же длины и порядка.\n'
            f"Строки: {json.dumps(lines, ensure_ascii=False)}"
        )
        out = self._generate(prompt)
        if isinstance(out, dict):
            out = next(iter(out.values()))
        if not isinstance(out, list):
            raise GeminiError("Неверный формат ответа переводчика.")
        while len(out) < len(lines):
            out.append("")
        return [str(x) for x in out[:len(lines)]]

    # ------------------------------------------------------ Looktionary
    def lookup_word(self, word: str, sentence: str, def_lang: str, trans_lang: str,
                    app_context: str = "") -> dict:
        prompt = (
            "Ты — Looktionary: ИИ-словарь для изучающих языки. "
            "Дай точное значение слова именно в данном контексте.\n"
            f"Слово в тексте: «{word}»\n"
            f'Контекст (с экрана приложения «{app_context or "неизвестно"}», возможны OCR-ошибки): """{sentence}"""\n'
            "Верни строго JSON со схемой:\n"
            "{\n"
            f'  "dict_form": "начальная (словарная) форма слова",\n'
            f'  "src_lang": "ISO-код языка слова (en/ru/de/...)",\n'
            f'  "level": "уровень CEFR: A1|A2|B1|B2|C1|C2",\n'
            f'  "transcription": "транскрипция IPA в /слешах/",\n'
            f'  "pos_tags": ["часть речи и грамматические пометы на языке [{def_lang}], напр. Существительное, Множественное число, тематика"],\n'
            f'  "definition": "определение значения слова В ДАННОМ КОНТЕКСТЕ на языке [{def_lang}], 1-2 предложения",\n'
            f'  "word_translation": "перевод слова на язык [{trans_lang}] (именно контекстное значение)",\n'
            f'  "synonyms": ["2-4 синонима на языке слова"],\n'
            f'  "context_translation": "перевод всего контекста на язык [{trans_lang}], слово оберни <u></u>"\n'
            "}"
        )
        res = self._generate(prompt)
        res.setdefault("dict_form", word)
        res.setdefault("pos_tags", [])
        res.setdefault("synonyms", [])
        return res

# ==================================================================== Groq
class Groq(_AIBase):
    """OpenAI-совместимый API Groq — самый быстрый, без региональных блокировок."""
    name = "Groq"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        super().__init__(api_key, model)

    def _generate(self, prompt: str, json_mode: bool = True, timeout: int = 40):
        if not self.api_key:
            raise GeminiError("Не задан API-ключ Groq (Настройки → ИИ).")
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}

        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            r = requests.post(GROQ_URL, json=body, headers=headers, timeout=timeout)
            if r.status_code == 200:
                break
            try:
                msg = r.json()["error"]["message"]
            except Exception:
                msg = r.text[:300]
            if r.status_code == 429 and attempt < MAX_RETRIES:
                wait = float(r.headers.get("retry-after", 0) or 0)
                if 0 < wait <= MAX_RETRY_WAIT:
                    time.sleep(wait)
                    continue
            raise GeminiError(f"Groq API {r.status_code}: {msg}")

        text = r.json()["choices"][0]["message"]["content"]
        return _parse_json(text) if json_mode else text

# ================================================================== Gemini
class Gemini(_AIBase):
    """Google Gemini (REST API)."""
    name = "Gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        super().__init__(api_key, model)

    @staticmethod
    def _retry_delay(err: dict):
        """Достаёт рекомендованную паузу (сек) из RetryInfo в ответе 429, иначе None."""
        for d in err.get("details", []):
            if d.get("@type", "").endswith("RetryInfo"):
                m = re.match(r"([\d.]+)s", str(d.get("retryDelay", "")))
                if m:
                    return float(m.group(1)) + 0.5  # небольшой запас
        return None

    def _generate(self, prompt: str, json_mode: bool = True, timeout: int = 40):
        if not self.api_key:
            raise GeminiError("Не задан API-ключ Gemini (Настройки → ИИ).")
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                # отключаем «размышление» — для перевода/словаря оно не нужно, а тормозит ответ
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        if json_mode:
            body["generationConfig"]["response_mime_type"] = "application/json"
        url = GEMINI_URL.format(model=self.model, key=self.api_key)

        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            r = requests.post(url, json=body, timeout=timeout)
            if r.status_code == 200:
                break
            try:
                err = r.json()["error"]
                msg = err["message"]
            except Exception:
                err, msg = {}, r.text[:300]
            if r.status_code == 429 and attempt < MAX_RETRIES:
                wait = self._retry_delay(err)
                if wait is not None and wait <= MAX_RETRY_WAIT:
                    time.sleep(wait)
                    continue
            raise GeminiError(f"Gemini API {r.status_code}: {msg}")

        data = r.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise GeminiError("Пустой ответ Gemini (возможно, сработал фильтр).")
        return _parse_json(text) if json_mode else text

# =============================================================== фабрика
def get_ai(cfg) -> _AIBase:
    """Создаёт ИИ-клиента по настройкам (провайдер + ключ + модель)."""
    provider = cfg.get("ai_provider", "groq")
    if provider == "gemini":
        return Gemini(cfg.get("gemini_api_key", ""), cfg.get("gemini_model", "gemini-2.5-flash"))
    return Groq(cfg.get("groq_api_key", ""), cfg.get("groq_model", "llama-3.3-70b-versatile"))
