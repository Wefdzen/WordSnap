"""Lookupper-клон: экранный переводчик и ИИ-словарь для изучения языков.

Запуск:  python main.py
Горячая клавиша по умолчанию: Alt+Q (или средняя кнопка мыши).
"""
import sys
import threading
import traceback

from PySide6.QtCore import QObject, Signal, Qt, QRect
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from app.config import CONFIG
from app.storage import WORDS
from app import capture, ocr
from app.gemini import get_ai, GeminiError
from app.translator import oxford_slot_lookup
from app.hotkeys import HotkeyManager
from app.ui.main_window import MainWindow, make_app_icon
from app.ui.popup import DictionaryPopup
from app.ui.overlay import TranslationOverlay, WordHighlight
from app.ui.i18n import t

# Сообщение ИИ-источников, когда не задан API-ключ провайдера.
NO_KEY_MSG = "Добавьте API-ключ в Настройках → ИИ-источники."

def active_window_title() -> tuple[str, str]:
    """(имя процесса, заголовок активного окна) — для контекста ИИ и «Детали источника»."""
    if sys.platform != "win32":
        return "", ""
    try:
        import ctypes
        import ctypes.wintypes as wt
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        pid = wt.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
        name = ""
        if h:
            nbuf = ctypes.create_unicode_buffer(260)
            size = wt.DWORD(260)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, nbuf, ctypes.byref(size)):
                name = nbuf.value.split("\\")[-1]
            ctypes.windll.kernel32.CloseHandle(h)
        return name, title
    except Exception:
        return "", ""

class Bridge(QObject):
    """Проброс результатов фоновых потоков в GUI-поток."""
    translator_ready = Signal(str)
    looktionary_ready = Signal(dict)
    oxford_ready = Signal(object)
    source_failed = Signal(str, str)
    overlay_ready = Signal(dict, list, object)
    highlight_ready = Signal(int, int, int, int)
    words_changed = Signal()
    error = Signal(str)

class Controller(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.window = MainWindow()
        self.popup = DictionaryPopup()
        self.overlay: TranslationOverlay | None = None
        self.word_highlight: WordHighlight | None = None
        self.bridge = Bridge()
        self.hotkeys = HotkeyManager(CONFIG)
        self._pending_entry: dict | None = None
        self._busy = False

        self.hotkeys.triggered.connect(self.on_hotkey)
        self.hotkeys.escaped.connect(self.on_escape)
        self.window.settings_page.hotkeys_changed.connect(self.hotkeys.restart)
        self.window.words_page.fetch_missing.connect(self.fetch_missing)
        self.popup.bookmark_clicked.connect(self.save_pending_entry)
        self.popup.closed.connect(self.close_highlight)

        self.bridge.translator_ready.connect(self.popup.fill_translator)
        self.bridge.looktionary_ready.connect(self._on_looktionary)
        self.bridge.oxford_ready.connect(self.popup.fill_oxford)
        self.bridge.source_failed.connect(self.popup.fail_source)
        self.bridge.overlay_ready.connect(self.show_overlay)
        self.bridge.highlight_ready.connect(self.show_highlight)
        self.bridge.words_changed.connect(self.window.words_page.reload)

        self._tray()
        self.hotkeys.start()
        self.window.show()

    # ------------------------------------------------------------- трей
    def _tray(self):
        # tray и menu держим на self, иначе сборщик мусора их убьёт и меню «умрёт»
        self.tray = QSystemTrayIcon(make_app_icon(), self)
        self.tray_menu = QMenu()
        hk = CONFIG.get("hotkey", "alt+q").upper()
        self.tray_menu.addAction(f"{t('Распознать текст')}\t{hk}").triggered.connect(self._tray_recognize)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(t("Слова")).triggered.connect(lambda: self._open_page(0))
        self.tray_menu.addAction(t("Переводчик и словари")).triggered.connect(lambda: self._open_page(1))
        self.tray_menu.addAction(t("Настройки")).triggered.connect(lambda: self._open_page(2))
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(t("Выход")).triggered.connect(self.app.quit)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.setToolTip(t("Lookupper — экранный переводчик"))
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._open_page(0)

    def _open_page(self, idx: int):
        self.window.show()
        self.window.setWindowState(self.window.windowState() & ~Qt.WindowMinimized)
        self.window.raise_()
        self.window.activateWindow()
        self.window.set_page(idx)

    def _tray_recognize(self):
        from PySide6.QtGui import QCursor
        pos = QCursor.pos()
        self.on_hotkey(pos.x(), pos.y())

    # --------------------------------------------------------- горячая клавиша
    def on_hotkey(self, x: int, y: int):
        if self.overlay and self.overlay.isVisible():
            self.overlay.close()
            self.overlay = None
            return
        if self._busy:
            return
        if CONFIG.get("mode") == "translator":
            self.run_translator_mode(x, y)
        else:
            self.run_dictionary_mode(x, y)

    def on_escape(self):
        """Глобальный Esc: закрывает попап/оверлей даже если фокус не на них."""
        if self.popup.isVisible():
            self.popup.close_animated()      # окно сжимается и гаснет (не мгновенно)
        if self.overlay and self.overlay.isVisible():
            self.overlay.close()
            self.overlay = None
        self.close_highlight()

    # ============================ РЕЖИМ СЛОВАРЯ ============================
    def run_dictionary_mode(self, x: int, y: int):
        self.close_highlight()
        app_name, win_title = active_window_title()
        # 1) скриншот области вокруг курсора (экран «замораживается» в момент нажатия)
        try:
            img, left, top = capture.region_around(x, y)
        except Exception as e:
            self.bridge.error.emit(str(e))
            return

        # чистый скриншот всего экрана СЕЙЧАС — до появления попапа,
        # иначе в кадр попадёт полупрозрачное окно перевода
        full_shot = None
        if not CONFIG.get("auto_crop_screenshots"):
            try:
                full_shot, _ = capture.grab_monitor_at(x, y)
            except Exception:
                full_shot = None

        order = [k for k in CONFIG.get("sources_order")
                 if CONFIG.get("sources_enabled").get(k)]
        # яркость фона под курсором → светлая/тёмная тема попапа
        try:
            light_bg = img.convert("L").resize((1, 1)).getpixel((0, 0)) > 140
        except Exception:
            light_bg = False
        self.popup.open_at(x, y, order, light=light_bg)

        def worker():
            self._busy = True
            try:
                engine = ocr.get_engine(CONFIG)
                lines = engine.recognize(img)
                line, word = ocr.word_at_point(lines, x - left, y - top)
                if word is None:
                    for k in order:
                        self.bridge.source_failed.emit(k, "Под курсором не найден текст.")
                    return
                # подсветка найденного слова прямо на экране (экранные координаты)
                self.bridge.highlight_ready.emit(
                    int(left + word.x), int(top + word.y),
                    int(word.w), int(word.h))
                w_clean = ocr.clean_word(word.text)
                sentence = ocr.sentence_around(lines, line, word)

                # скриншот для карточки слова
                if CONFIG.get("auto_crop_screenshots"):
                    pad = 120
                    box = (max(0, int(word.x) - pad), max(0, int(word.y) - pad),
                           min(img.width, int(word.x + word.w) + pad),
                           min(img.height, int(word.y + word.h) + pad))
                    shot_img = img.crop(box)
                else:
                    # чистый полноэкранный кадр, снятый ДО показа попапа
                    shot_img = full_shot if full_shot is not None else img
                shot_name = WORDS.save_screenshot(shot_img)

                self._pending_entry = {
                    "src_lang": CONFIG.get("ocr_lang"),
                    "dst_lang": CONFIG.get("looktionary_pro")["word_trans_lang"],
                    "dict_form": w_clean, "word_in_text": w_clean,
                    "context": sentence, "screenshot": shot_name,
                    "source_app": app_name, "source_title": win_title,
                    "complete": False,
                }
                if CONFIG.get("auto_save_words"):
                    self._pending_entry = WORDS.add(self._pending_entry)
                    self.bridge.words_changed.emit()

                gem = get_ai(CONFIG)

                # --- Переводчик ---
                def do_translator():
                    try:
                        if not gem.ready:
                            self.bridge.source_failed.emit("translator_pro", t(NO_KEY_MSG))
                            return
                        tgt = CONFIG.get("translator_pro")["target_lang"]
                        tr = gem.translate_sentence(sentence, tgt, w_clean, app_name)
                        self.bridge.translator_ready.emit(tr)
                    except Exception as e:
                        self.bridge.source_failed.emit("translator_pro", f"Ошибка: {e}")

                # --- Looktionary ---
                def do_looktionary():
                    try:
                        if not gem.ready:
                            self.bridge.source_failed.emit("looktionary_pro", t(NO_KEY_MSG))
                            return
                        lk = CONFIG.get("looktionary_pro")
                        data = gem.lookup_word(w_clean, sentence, lk["def_lang"],
                                               lk["word_trans_lang"], app_name)
                        self.bridge.looktionary_ready.emit(data)
                    except Exception as e:
                        self.bridge.source_failed.emit("looktionary_pro", f"Ошибка: {e}")

                # --- Oxford-слот ---
                def do_oxford():
                    try:
                        self.bridge.oxford_ready.emit(oxford_slot_lookup(w_clean))
                    except Exception as e:
                        self.bridge.source_failed.emit("oxford", f"Ошибка: {e}")

                # запускаем все источники ОДНОВРЕМЕННО — каждый присылает результат сам по себе
                jobs = {"translator_pro": do_translator,
                        "looktionary_pro": do_looktionary, "oxford": do_oxford}
                threads = [threading.Thread(target=jobs[k], daemon=True)
                           for k in order if k in jobs]
                for th in threads:
                    th.start()
                for th in threads:
                    th.join()
            except Exception as e:
                traceback.print_exc()
                for k in order:
                    self.bridge.source_failed.emit(k, f"OCR-ошибка: {e}")
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _on_looktionary(self, data: dict):
        self.popup.fill_looktionary(data)
        # дозаполняем сохранённую запись данными ИИ
        if self._pending_entry and self._pending_entry.get("id"):
            WORDS.update(self._pending_entry["id"],
                         dict_form=data.get("dict_form", self._pending_entry["dict_form"]),
                         src_lang=data.get("src_lang", self._pending_entry["src_lang"]),
                         level=data.get("level", ""),
                         transcription=data.get("transcription", ""),
                         pos_tags=data.get("pos_tags", []),
                         definition=data.get("definition", ""),
                         word_translation=data.get("word_translation", ""),
                         synonyms=data.get("synonyms", []),
                         context_translation=data.get("context_translation", ""),
                         complete=bool(data.get("definition")))
            self.bridge.words_changed.emit()
        elif self._pending_entry is not None:
            self._pending_entry.update(data)

    def save_pending_entry(self):
        """Клик по закладке в попапе, когда автосохранение выключено."""
        if self._pending_entry and not self._pending_entry.get("id"):
            self._pending_entry = WORDS.add(self._pending_entry)
            self.bridge.words_changed.emit()

    # ----------------------------------------------- подсветка слова на экране
    def show_highlight(self, x: int, y: int, w: int, h: int):
        self.close_highlight()
        self.word_highlight = WordHighlight(x, y, w, h)
        self.word_highlight.show()
        # сдвигаем окно перевода под/над слово, чтобы оно не накрывало само слово
        self.popup.place_near_word(x, y, w, h)

    def close_highlight(self):
        if self.word_highlight:
            self.word_highlight.close()
            self.word_highlight = None

    # ========================== РЕЖИМ ПЕРЕВОДЧИКА ==========================
    def run_translator_mode(self, x: int, y: int):
        app_name, _ = active_window_title()
        try:
            img, mon = capture.grab_monitor_at(x, y)
        except Exception as e:
            self.bridge.error.emit(str(e))
            return

        frozen = None
        if CONFIG.get("freeze_screen"):
            qimg = QImage(img.tobytes(), img.width, img.height,
                          img.width * 3, QImage.Format_RGB888)
            frozen = QPixmap.fromImage(qimg.copy())

        def worker():
            self._busy = True
            try:
                engine = ocr.get_engine(CONFIG)
                lines = engine.recognize(img)
                lines = [l for l in lines if len(l.text.strip()) > 1][:60]
                if not lines:
                    self._busy = False
                    return
                gem = get_ai(CONFIG)
                if not gem.ready:
                    self.bridge.error.emit(t(NO_KEY_MSG))
                    self._busy = False
                    return
                texts = [l.text for l in lines]
                tgt = CONFIG.get("translator_pro")["target_lang"]
                translated = gem.translate_lines(texts, tgt, app_name)
                items = [(QRect(int(l.x), int(l.y), int(l.w), int(l.h)), tr)
                         for l, tr in zip(lines, translated)]
                self.bridge.overlay_ready.emit(mon, items, frozen)
            except Exception:
                traceback.print_exc()
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()

    def show_overlay(self, mon: dict, items: list, frozen):
        if self.overlay:
            self.overlay.close()
        self.overlay = TranslationOverlay(
            mon, items, frozen, interactive=CONFIG.get("overlay_active_window"))
        self.overlay.show()
        if CONFIG.get("overlay_active_window"):
            self.overlay.activateWindow()

    # ================== «Получить недостающие данные» ==================
    def fetch_missing(self):
        gem = get_ai(CONFIG)
        if not gem.ready:
            self.bridge.error.emit("Укажите API-ключ Gemini в Настройках → ИИ-источники.")
            return
        items = WORDS.incomplete()
        lk = CONFIG.get("looktionary_pro")

        def worker():
            for e in items:
                try:
                    data = gem.lookup_word(e.get("word_in_text", e.get("dict_form", "")),
                                           e.get("context", ""), lk["def_lang"],
                                           lk["word_trans_lang"], e.get("source_app", ""))
                    WORDS.update(e["id"],
                                 dict_form=data.get("dict_form", e.get("dict_form")),
                                 src_lang=data.get("src_lang", e.get("src_lang")),
                                 level=data.get("level", ""),
                                 transcription=data.get("transcription", ""),
                                 pos_tags=data.get("pos_tags", []),
                                 definition=data.get("definition", ""),
                                 word_translation=data.get("word_translation", ""),
                                 synonyms=data.get("synonyms", []),
                                 context_translation=data.get("context_translation", ""),
                                 complete=True)
                    self.bridge.words_changed.emit()
                except Exception as ex:
                    print("fetch_missing:", ex)
            self.bridge.words_changed.emit()

        threading.Thread(target=worker, daemon=True).start()

def main():
    # Windows показывает в панели задач иконку python.exe, пока у процесса нет
    # своего AppUserModelID. Задаём его — тогда таскбар берёт иконку окна.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Lookupper.Desktop.App")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Lookupper")
    from app.ui.theme import apply_palette
    apply_palette(app)                  # палитра под выбранную тему (важно для светлой)
    app.setWindowIcon(make_app_icon())  # иконка приложения (панель задач)
    app.setQuitOnLastWindowClosed(False)
    ctl = Controller(app)
    ctl.bridge.error.connect(lambda m: ctl.tray.showMessage("Lookupper", m,
                                                            QSystemTrayIcon.Warning, 4000))
    sys.exit(app.exec())

if __name__ == "__main__":
    print("Starting Lookupper...")
    main()