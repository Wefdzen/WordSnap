"""ИИ-источники для перевода и словаря. Поддерживаются два провайдера:
  • Groq  — самый быстрый (<1 сек), без региональных блокировок: https://console.groq.com/keys
  • Gemini — Google AI Studio: https://aistudio.google.com/apikey
Переводчик — контекстный перевод экранного текста.
Looktionary — ИИ-словарь: значение слова в контексте, уровень, транскрипция и т.д."""
import copy
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
    """Парсит JSON из ответа модели с автовосстановлением обрывов и очисткой markdown."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Поиск первого { или [ до последнего } или ]
    first_brace = min([p for p in (cleaned.find('{'), cleaned.find('[')) if p != -1], default=-1)
    last_brace = max(cleaned.rfind('}'), cleaned.rfind(']'))
    if first_brace != -1 and last_brace > first_brace:
        sub = cleaned[first_brace:last_brace + 1]
        try:
            return json.loads(sub)
        except Exception:
            pass

    # Если JSON был оборван лимитом токенов (например нет закрывающей скобки):
    if first_brace != -1:
        truncated = cleaned[first_brace:].strip()
        for ending in (']}', '}', '"]}', '"}', '"]'):
            try:
                return json.loads(truncated + ending)
            except Exception:
                pass

    # Резервный поиск массива строк "lines": [...]
    lines_match = re.search(r'"lines"\s*:\s*\[(.*)', cleaned, re.S)
    if lines_match:
        items = re.findall(r'"((?:\\.|[^"\\])*)"', lines_match.group(1))
        if items:
            return {"lines": items}

    raise GeminiError(f"Не удалось распарсить JSON из ответа: {text[:200]}")

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
        if not lines:
            return []
        prompt = (
            "Ты — Переводчик: профессиональный ИИ-переводчик экранного текста из игр и приложений.\n"
            f"Источник — экран приложения «{app_context or 'неизвестно'}».\n"
            "Исправляй мелкие OCR-ошибки по смыслу, сохраняй стиль и контекст.\n"
            f"Переведи каждую строку массива на язык [{target_lang}]. Переводи сразу, без рассуждений и пояснений.\n"
            'Верни строго JSON со схемой: {"lines": ["строка 1", "строка 2", ...]} — массив строк той же длины и порядка.\n'
            f"Строки: {json.dumps(lines, ensure_ascii=False)}"
        )
        out = self._generate(prompt)
        res_lines = None
        if isinstance(out, list):
            res_lines = out
        elif isinstance(out, dict):
            if "lines" in out and isinstance(out["lines"], list):
                res_lines = out["lines"]
            elif "translations" in out and isinstance(out["translations"], list):
                res_lines = out["translations"]
            else:
                for v in out.values():
                    if isinstance(v, list):
                        res_lines = v
                        break
                    elif isinstance(v, dict):
                        for sub_v in v.values():
                            if isinstance(sub_v, list):
                                res_lines = sub_v
                                break
                        if res_lines:
                            break
        if not isinstance(res_lines, list):
            raise GeminiError("Неверный формат ответа переводчика.")
        while len(res_lines) < len(lines):
            res_lines.append("")
        return [str(x) for x in res_lines[:len(lines)]]

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
_GROQ_MODELS_CACHE = {"timestamp": 0.0, "models": []}
_GROQ_CACHE_TTL = 3600.0  # 1 час

def fetch_active_groq_models(api_key: str, force_refresh: bool = False) -> list[str]:
    """Запрашивает список активных текстовых моделей из API Groq, отсортированных по качеству и новизне."""
    now = time.monotonic()
    if not force_refresh and _GROQ_MODELS_CACHE["models"] and (now - _GROQ_MODELS_CACHE["timestamp"] < _GROQ_CACHE_TTL):
        return _GROQ_MODELS_CACHE["models"]
    if not api_key:
        return ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
    try:
        r = requests.get("https://api.groq.com/openai/v1/models",
                         headers={"Authorization": f"Bearer {api_key}"},
                         timeout=5)
        if r.status_code == 200:
            data = r.json().get("data", [])
            candidates = []
            for m in data:
                mid = m.get("id", "")
                if not m.get("active", True):
                    continue
                # Исключаем whisper, prompt-guard, safeguard, audio, vision
                if any(bad in mid.lower() for bad in ("whisper", "guard", "audio", "orpheus", "vision", "embed")):
                    continue
                if m.get("context_window", 0) < 4096:
                    continue
                features = m.get("supported_features", [])
                if "json_mode" not in features:
                    continue

                # Приоритет: быстрые мультиязычные модели без reasoning-накладных расходов (Qwen, Llama) > флагманы
                score = m.get("created", 0)
                mid_l = mid.lower()
                if "qwen" in mid_l:
                    score += 2_000_000_000
                elif "llama" in mid_l:
                    score += 1_800_000_000
                elif "120b" in mid_l:
                    score += 1_000_000_000
                elif "70b" in mid_l:
                    score += 800_000_000
                elif "27b" in mid_l:
                    score += 700_000_000
                elif "20b" in mid_l:
                    score += 500_000_000
                candidates.append((score, mid))

            candidates.sort(reverse=True)
            models = [c[1] for c in candidates]
            if models:
                _GROQ_MODELS_CACHE["models"] = models
                _GROQ_MODELS_CACHE["timestamp"] = now
                return models
    except Exception as e:
        print("fetch_active_groq_models error:", e)

    fallback = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    return _GROQ_MODELS_CACHE["models"] or fallback


class Groq(_AIBase):
    """OpenAI-совместимый API Groq — самый быстрый, без региональных блокировок."""
    name = "Groq"

    def __init__(self, api_key: str, model: str = "auto"):
        super().__init__(api_key, model)

    def _resolve_model(self) -> str:
        """Определяет рабочую модель. Если 'auto' — берёт самую свежую и быструю из доступных."""
        if self.model and self.model != "auto":
            return self.model
        models = fetch_active_groq_models(self.api_key)
        return models[0] if models else "qwen/qwen3.8-27b"

    def check_key(self) -> str:
        """Быстрая проверка ключа через список моделей без траты токенов и без ожидания очереди генерации."""
        if not self.api_key:
            raise GeminiError("API-ключ Groq не указан.")
        try:
            r = requests.get(GROQ_MODELS_URL if 'GROQ_MODELS_URL' in globals() else "https://api.groq.com/openai/v1/models",
                             headers={"Authorization": f"Bearer {self.api_key}"},
                             timeout=5)
            if r.status_code == 200:
                return "OK"
            try:
                msg = r.json().get("error", {}).get("message", r.text[:200])
            except Exception:
                msg = r.text[:200]
            raise GeminiError(f"Groq API {r.status_code}: {msg}")
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            raise GeminiError("Таймаут подключения к Groq (проверьте интернет)")

    def _generate(self, prompt: str, json_mode: bool = True, timeout: int = 40):
        if not self.api_key:
            raise GeminiError("Не задан API-ключ Groq (Настройки → ИИ).")

        effective_model = self._resolve_model()
        body = {
            "model": effective_model,
            "messages": [
                {"role": "system", "content": "You are a professional on-screen translator. Always respond strictly in valid JSON without preamble or reasoning."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}

        for attempt in range(MAX_RETRIES + 2):
            self._throttle()
            r = requests.post(GROQ_URL, json=body, headers=headers, timeout=timeout)
            if r.status_code == 200:
                break
            try:
                msg = r.json()["error"]["message"]
            except Exception:
                msg = r.text[:300]

            # Если Groq вернул 400 из-за жесткой валидации JSON (json_validate_failed или лимит токенов):
            if r.status_code == 400 and ("json" in msg.lower() or "validate" in msg.lower() or "format" in msg.lower() or "token" in msg.lower()):
                if "response_format" in body:
                    print("Groq 400 (json_validate_failed): повторяем запрос без строгого response_format...")
                    body.pop("response_format", None)
                    continue
                available = fetch_active_groq_models(self.api_key)
                alt_models = [m for m in available if m != effective_model]
                if alt_models:
                    alt_model = alt_models[0]
                    print(f"Groq 400 на {effective_model}: переключаем на альтернативную модель {alt_model}...")
                    effective_model = alt_model
                    body["model"] = effective_model
                    continue

            # Если модель удалена/не существует (404) или недоступна:
            # автоматически обновляем список моделей из Groq API и переключаемся на актуальную
            if r.status_code == 404 or "does not exist" in msg.lower() or "not have access" in msg.lower():
                available = fetch_active_groq_models(self.api_key, force_refresh=True)
                next_models = [m for m in available if m != effective_model]
                if next_models:
                    new_model = next_models[0]
                    print(f"Groq: модель {effective_model} устарела/недоступна. Автоматически переключаем на {new_model}.")
                    effective_model = new_model
                    self.model = new_model
                    try:
                        from .config import CONFIG
                        CONFIG.set("groq_model", "auto", save=True)
                    except Exception:
                        pass
                    body["model"] = new_model
                    r = requests.post(GROQ_URL, json=body, headers=headers, timeout=timeout)
                    if r.status_code == 200:
                        break
                    try:
                        msg = r.json()["error"]["message"]
                    except Exception:
                        msg = r.text[:300]

            if r.status_code == 429 and attempt < MAX_RETRIES + 1:
                # Если исчерпан лимит токенов текущей модели в минуту (OTPM), переключаемся на другую модель с отдельной квотой
                available = fetch_active_groq_models(self.api_key)
                alt_models = [m for m in available if m != effective_model]
                if alt_models:
                    alt_model = alt_models[attempt % len(alt_models)]
                    print(f"Groq 429 на {effective_model}: переключаемся на квоту модели {alt_model}...")
                    effective_model = alt_model
                    body["model"] = effective_model
                    continue

                wait = float(r.headers.get("retry-after", 0) or 0)
                if 0 < wait <= MAX_RETRY_WAIT:
                    time.sleep(wait)
                    continue
            raise GeminiError(f"Groq API {r.status_code}: {msg}")

        text = r.json()["choices"][0]["message"]["content"]
        return _parse_json(text) if json_mode else text

_GEMINI_MODELS_CACHE = {"timestamp": 0.0, "models": []}

def fetch_active_gemini_models(api_key: str, force_refresh: bool = False) -> list[str]:
    """Запрашивает актуальный список доступных моделей Gemini из Google API."""
    if not api_key:
        return ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

    now = time.time()
    if not force_refresh and _GEMINI_MODELS_CACHE["models"] and (now - _GEMINI_MODELS_CACHE["timestamp"] < 3600):
        return _GEMINI_MODELS_CACHE["models"]

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json().get("models", [])
            candidates = []
            for m in data:
                name = m.get("name", "")
                mid = name.replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" not in methods:
                    continue
                if not mid.startswith("gemini"):
                    continue
                # Исключаем аудио/TTS, генерацию картинок, embedding и прочие специализированные модели
                if any(bad in mid.lower() for bad in (
                    "embedding", "aqa", "imagen", "robotics", "computer",
                    "tts", "image", "audio", "vision", "preview-tts", "lite-tts", "customtools"
                )):
                    continue

                # Приоритет: самые свежие рабочие Flash-модели для текста
                score = 0
                if "flash" in mid:
                    score += 1000
                if "3.8" in mid:
                    score += 500
                elif "3.7" in mid:
                    score += 450
                elif "3." in mid:
                    score += 400
                elif "2.5" in mid:
                    score += 300
                elif "2.0" in mid:
                    score += 200
                elif "1.5" in mid:
                    score += 100

                if "lite" in mid:
                    score -= 50
                candidates.append((score, mid))

            candidates.sort(reverse=True)
            models = [c[1] for c in candidates]
            if models:
                _GEMINI_MODELS_CACHE["models"] = models
                _GEMINI_MODELS_CACHE["timestamp"] = now
                return models
    except Exception as e:
        print("fetch_active_gemini_models error:", e)

    fallback = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    return _GEMINI_MODELS_CACHE["models"] or fallback


# ================================================================== Gemini
class Gemini(_AIBase):
    """Google Gemini (REST API)."""
    name = "Gemini"

    def __init__(self, api_key: str, model: str = "auto"):
        super().__init__(api_key, model)

    def _resolve_model(self) -> str:
        """Определяет модель. Если 'auto' — выбирает новейшую доступную Flash-модель."""
        if self.model and self.model != "auto":
            return self.model
        models = fetch_active_gemini_models(self.api_key)
        return models[0] if models else "gemini-3.8-flash"

    def check_key(self) -> str:
        """Быстрая проверка ключа через список моделей без траты токенов и зависаний."""
        if not self.api_key:
            raise GeminiError("API-ключ Gemini не указан.")
        try:
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}",
                             timeout=6)
            if r.status_code == 200:
                return "OK"
            try:
                msg = r.json().get("error", {}).get("message", r.text[:200])
            except Exception:
                msg = r.text[:200]
            raise GeminiError(f"Gemini API {r.status_code}: {msg}")
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            raise GeminiError("Таймаут подключения к Google Gemini (в РФ может требоваться VPN)")

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

        effective_model = self._resolve_model()
        url = GEMINI_URL.format(model=effective_model, key=self.api_key)

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

            # Если модель удалена/устарела (404), заблокирована или "no longer available":
            # Например: "This model models/gemini-2.5-flash is no longer available to new users.
            # Please update your code to use models/gemini-3.8-flash"
            if r.status_code == 404 or "not found" in msg.lower() or "no longer available" in msg.lower() or "deprecated" in msg.lower():
                all_models = re.findall(r"models/(gemini-[\w\.\-]+)", msg)
                rec_models = [m for m in all_models if m != effective_model]
                if rec_models:
                    new_model = rec_models[-1]
                else:
                    available = fetch_active_gemini_models(self.api_key, force_refresh=True)
                    next_models = [m for m in available if m != effective_model]
                    new_model = next_models[0] if next_models else "gemini-3.8-flash"

                if new_model and new_model != effective_model:
                    print(f"Gemini: модель {effective_model} недоступна. Автоматически переключаем на {new_model}.")
                    effective_model = new_model
                    self.model = new_model
                    try:
                        from .config import CONFIG
                        CONFIG.set("gemini_model", "auto", save=True)
                    except Exception:
                        pass
                    url = GEMINI_URL.format(model=new_model, key=self.api_key)
                    r = requests.post(url, json=body, timeout=timeout)
                    if r.status_code == 200:
                        break
                    try:
                        err = r.json()["error"]
                        msg = err["message"]
                    except Exception:
                        err, msg = {}, r.text[:300]

            # Если модель не поддерживает response_mime_type: application/json
            if r.status_code == 400 and ("json mode is not enabled" in msg.lower() or "not supported" in msg.lower()):
                body_no_json = copy.deepcopy(body)
                if "generationConfig" in body_no_json:
                    body_no_json["generationConfig"].pop("response_mime_type", None)
                r = requests.post(url, json=body_no_json, timeout=timeout)
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
        return Gemini(cfg.get("gemini_api_key", ""), cfg.get("gemini_model", "auto"))
    return Groq(cfg.get("groq_api_key", ""), cfg.get("groq_model", "auto"))
