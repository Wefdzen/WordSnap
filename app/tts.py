"""Озвучка слов и определений (pyttsx3 — офлайн, Windows SAPI)."""
import threading

_lock = threading.Lock()

def speak(text: str, lang: str = "en"):
    if not text:
        return
    def run():
        with _lock:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                # Подбираем голос под язык, если есть
                target = {"ru": "russian", "en": "english", "de": "german",
                          "fr": "french", "es": "spanish"}.get(lang, "")
                if target:
                    for v in engine.getProperty("voices"):
                        if target in (v.name or "").lower() or target in (v.id or "").lower():
                            engine.setProperty("voice", v.id)
                            break
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception as e:
                print("tts error:", e)
    threading.Thread(target=run, daemon=True).start()
