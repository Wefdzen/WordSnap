"""Lookupper-клон: экранный переводчик и ИИ-словарь для изучения языков.

Запуск:  python main.py
Горячая клавиша по умолчанию: Alt+Q (или средняя кнопка мыши).
"""
import sys
import threading
import traceback
import atexit

from PySide6.QtCore import QObject, Signal, Qt, QRect, QPoint, QTimer
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from app.config import CONFIG
from app.storage import WORDS
from app import capture, ocr
from app.gemini import get_ai, GeminiError
from app.hotkeys import HotkeyManager, parse_hotkey
from app.ui.main_window import MainWindow, make_app_icon
from app.ui.popup import DictionaryPopup
from app.ui.overlay import TranslationOverlay, WordHighlight, FreezeFrameOverlay, force_foreground_and_release_cursor
from app.ui.i18n import t

# Сообщение ИИ-источников, когда не задан API-ключ провайдера.
NO_KEY_MSG = "Добавьте API-ключ в Настройках → ИИ-источники."

_GLOBAL_PAUSED_HANDLE = None

def _emergency_resume_process():
    """Гарантированное возобновление процесса при аварийном завершении приложения (atexit)."""
    global _GLOBAL_PAUSED_HANDLE
    if _GLOBAL_PAUSED_HANDLE and sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.ntdll.NtResumeProcess(_GLOBAL_PAUSED_HANDLE)
            ctypes.windll.kernel32.CloseHandle(_GLOBAL_PAUSED_HANDLE)
        except Exception:
            pass
        _GLOBAL_PAUSED_HANDLE = None

atexit.register(_emergency_resume_process)

def active_window_title() -> tuple[str, str, int, int]:
    """(имя процесса, заголовок активного окна, pid, hwnd) — для контекста ИИ, автопаузы и разворачивания."""
    if sys.platform != "win32":
        return "", "", 0, 0
    try:
        import ctypes
        import ctypes.wintypes as wt
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return "", "", 0, 0
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
        return name, title, int(pid.value), int(hwnd)
    except Exception:
        return "", "", 0, 0

class Bridge(QObject):
    """Проброс результатов фоновых потоков в GUI-поток."""
    translator_ready = Signal(str)
    looktionary_ready = Signal(dict)
    offline_dict_ready = Signal(str, object)
    source_failed = Signal(str, str)
    overlay_ready = Signal(dict, list, object)
    highlight_ready = Signal(int, int, int, int)
    words_changed = Signal()
    anki_status = Signal(str, str)
    anki_visible = Signal(bool)
    bookmark_saved = Signal(bool)
    error = Signal(str)
    outside_click = Signal(int, int)      # глобальный клик мимо попапа — закрыть его

class Controller(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.window: MainWindow | None = None
        self.tray: QSystemTrayIcon | None = None
        self.tray_menu: QMenu | None = None
        self.popup = DictionaryPopup()
        self.overlay: TranslationOverlay | None = None
        self.freeze_overlay: FreezeFrameOverlay | None = None
        self._freeze_full_shot = None
        self.word_highlight: WordHighlight | None = None
        self.bridge = Bridge()
        self.hotkeys = HotkeyManager(CONFIG)
        self._pending_entry: dict | None = None
        self._busy = False
        self._popup_open = False          # попап открыт → ловим клики мимо него
        self._anki_connected = False
        self._saved_game_hwnd: int | None = None
        self._saved_game_pid: int | None = None
        self._paused_process_handle = None

        self.hotkeys.triggered.connect(self.on_hotkey)
        self.hotkeys.escaped.connect(self.on_escape)
        self.hotkeys.wheel_scrolled.connect(self.popup.scroll_by_delta)
        self.hotkeys.is_escape_suppress_active = self._is_escape_suppress_active
        self.hotkeys.is_wheel_suppress_active = self._is_wheel_suppress_active
        self.popup.bookmark_clicked.connect(self.toggle_pending_bookmark)
        self.popup.anki_clicked.connect(self.add_current_to_anki)
        self.popup.closed.connect(self.close_highlight)
        self.popup.closed.connect(self._on_popup_closed)
        self.bridge.outside_click.connect(self._on_outside_click)

        self.bridge.translator_ready.connect(self.popup.fill_translator)
        self.bridge.looktionary_ready.connect(self._on_looktionary)
        self.bridge.offline_dict_ready.connect(self.popup.fill_offline_dict)
        self.bridge.source_failed.connect(self.popup.fail_source)
        self.bridge.overlay_ready.connect(self.show_overlay)
        self.bridge.highlight_ready.connect(self.show_highlight)
        self.bridge.anki_status.connect(self.popup.set_anki_state)
        self.bridge.anki_visible.connect(self.popup.set_anki_visible)
        self.bridge.bookmark_saved.connect(self.popup.set_bookmark_saved)

        self._tray()
        self.hotkeys.start()
        self._start_click_watch()
        self._check_anki_connection_async()

        if not CONFIG.get("first_setup_done"):
            # При первом запуске показываем ТОЛЬКО мастер настройки, главное окно не открываем
            from app.ui.onboarding_dialog import OnboardingWizard
            self.onboarding = OnboardingWizard(None)
            self.onboarding.finished.connect(self._on_onboarding_finished)
            self.onboarding.show()
        else:
            self._create_main_window(show=True)

    def _create_main_window(self, show: bool = True):
        """Создание главного окна приложения и привязка его обработчиков."""
        if self.window is not None:
            try:
                self.window.deleteLater()
            except Exception:
                pass
        self.window = MainWindow()
        self.window.settings_page.hotkeys_changed.connect(self.hotkeys.restart)
        self.window.settings_page.words_display_changed.connect(self.window.words_page.reload)
        self.window.settings_page.anki_settings_changed.connect(self._on_anki_settings_changed)
        self.window.words_page.fetch_missing.connect(self.fetch_missing)
        self.bridge.words_changed.connect(self.window.words_page.reload)
        if show:
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

    def _on_onboarding_finished(self):
        CONFIG.set("first_setup_done", True, save=True)
        theme = CONFIG.get("ui_theme", "dark")
        from app.ui.theme import P, resolve, apply_theme_live
        if P != resolve(theme):
            apply_theme_live(self.app, theme)

        # Создаём главное окно после успешного завершения первичной настройки
        self._create_main_window(show=True)
        self._tray()

    # ------------------------------------- закрытие попапа кликом мимо него
    def _start_click_watch(self):
        """Глобально следим за нажатиями мыши: пока попап открыт, клик вне его
        окна закрывает попап. Через pynput — иначе клики по другим окнам Qt не видит."""
        from pynput import mouse

        def on_click(x, y, button, pressed):
            if pressed and self._popup_open:
                self.bridge.outside_click.emit(int(x), int(y))

        self._click_listener = mouse.Listener(on_click=on_click)
        self._click_listener.daemon = True
        self._click_listener.start()

    def _on_outside_click(self, x: int, y: int):
        if not self.popup.isVisible():
            self._popup_open = False
            return
        import time
        # Защита: игнорируем клики в первые 450 мс после открытия (клик, который открыл попап)
        if time.time() - getattr(self, "_popup_open_time", 0) < 0.45:
            return
        # клик внутри окна попапа (кнопки, закладка) — не закрываем
        if self.popup.frameGeometry().contains(QPoint(x, y)):
            return
        self._popup_open = False
        self.popup.close_animated()
        self.close_highlight()
        self._resume_paused_process()

    def _discard_pending_screenshot(self):
        """Удаляет временный скриншот с диска, если слово не было сохранено в личную библиотеку."""
        if not self._pending_entry:
            return
        # Если слово сохранено в личную библиотеку — скриншот нужен для карточки
        if self._pending_entry.get("id"):
            return
        # Если прямо сейчас идёт отправка в Anki — удалим скриншот после завершения загрузки
        if self._pending_entry.get("anki_in_progress"):
            self._pending_entry["pending_delete_shot"] = True
            return

        shot = self._pending_entry.get("screenshot")
        if shot:
            WORDS.delete_screenshot(shot)
            self._pending_entry["screenshot"] = ""

    def _on_popup_closed(self):
        self._popup_open = False
        self._resume_paused_process()
        self._discard_pending_screenshot()
        if self._pending_entry and not self._pending_entry.get("id") and not self._pending_entry.get("anki_in_progress"):
            self._pending_entry = None

    def _is_escape_suppress_active(self) -> bool:
        """Перехватывать и блокировать ли системный Esc, чтобы он не долетал до игры."""
        if self.popup and self.popup.isVisible():
            return True
        if self.freeze_overlay and self.freeze_overlay.isVisible():
            return True
        if self.overlay and self.overlay.isVisible():
            return True
        return False

    def _is_wheel_suppress_active(self, x: int = 0, y: int = 0) -> bool:
        """Перехватывать и изолировать ли колесико мыши от фоновой игры."""
        if not self.popup or not self.popup.isVisible():
            return False
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QCursor
        if x == 0 and y == 0:
            pos = QCursor.pos()
            x, y = pos.x(), pos.y()
        # Если курсор находится над окном попапа (с запасом 6px для удобства)
        return self.popup.frameGeometry().adjusted(-6, -6, 6, 6).contains(QPoint(x, y))

    def _suspend_process(self, pid: int, app_name: str = ""):
        """Приостанавливает процесс игры через NtSuspendProcess (чтобы FPS-игра не центрировала мышь)."""
        if not pid or sys.platform != "win32":
            return
        import os
        if pid == os.getpid() or pid <= 4:
            return
        ignore_apps = ("explorer.exe", "dwm.exe", "taskmgr.exe", "python.exe", "wordsnap.exe", "shellexperiencehost.exe")
        if (app_name or "").lower() in ignore_apps:
            return
        if getattr(self, "_paused_process_handle", None):
            return
        try:
            import ctypes
            # PROCESS_SUSPEND_RESUME = 0x0800
            h = ctypes.windll.kernel32.OpenProcess(0x0800, False, pid)
            if h:
                ctypes.windll.ntdll.NtSuspendProcess(h)
                self._paused_process_handle = h
                global _GLOBAL_PAUSED_HANDLE
                _GLOBAL_PAUSED_HANDLE = h
                # Дублируем сброс захвата курсора сразу после приостановки
                ctypes.windll.user32.ClipCursor(None)
        except Exception as e:
            print("suspend process error:", e)

    def _check_autopause(self, app_name: str, win_title: str, pid: int):
        """Автоматическая пауза игры/приложения через NtSuspendProcess, если настроено."""
        target = (CONFIG.get("autopause_window") or "").strip().lower()
        if not target or not pid or sys.platform != "win32":
            return
        if target in (app_name or "").lower() or target in (win_title or "").lower():
            self._suspend_process(pid, app_name)

    def _resume_paused_process(self, force: bool = False):
        """Возобновление работы приостановленного процесса."""
        # Если оверлей заморозки всё ещё открыт, не возобновляем игру раньше времени (если не force)
        if not force and self.freeze_overlay and self.freeze_overlay.isVisible():
            return
        h = getattr(self, "_paused_process_handle", None)
        if h:
            try:
                import ctypes
                ctypes.windll.ntdll.NtResumeProcess(h)
                ctypes.windll.kernel32.CloseHandle(h)
            except Exception as e:
                print("autopause resume error:", e)
            finally:
                self._paused_process_handle = None
                global _GLOBAL_PAUSED_HANDLE
                _GLOBAL_PAUSED_HANDLE = None

    def _check_fullscreenize(self, app_name: str, win_title: str, hwnd: int):
        """Растягивание окна без рамок на весь экран, если совпадает с настройкой."""
        target = (CONFIG.get("fullscreenize_window") or "").strip().lower()
        if not target or not hwnd or sys.platform != "win32":
            return
        if target in (app_name or "").lower() or target in (win_title or "").lower():
            try:
                import ctypes
                GWL_STYLE = -16
                WS_CAPTION = 0x00C00000
                WS_THICKFRAME = 0x00040000
                WS_MINIMIZEBOX = 0x00020000
                WS_MAXIMIZEBOX = 0x00010000
                WS_SYSMENU = 0x00080000
                SWP_FRAMECHANGED = 0x0020
                SWP_SHOWWINDOW = 0x0040
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)
                w = ctypes.windll.user32.GetSystemMetrics(0)
                h = ctypes.windll.user32.GetSystemMetrics(1)
                ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, w, h, SWP_FRAMECHANGED | SWP_SHOWWINDOW)
            except Exception as e:
                print("fullscreenize error:", e)

    # ------------------------------------------------------------- трей
    def _tray(self):
        # tray и menu держим на self, иначе сборщик мусора их убьёт и меню «умрёт»
        if getattr(self, "tray", None) is None:
            self.tray = QSystemTrayIcon(make_app_icon(), self)
            self.tray.activated.connect(self._tray_activated)
        else:
            self.tray.setIcon(make_app_icon())

        self.tray_menu = QMenu()
        hk = CONFIG.get("hotkey", "alt+q").upper()
        self.tray_menu.addAction(f"{t('Распознать текст')}\t{hk}").triggered.connect(self._tray_recognize)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(t("Слова")).triggered.connect(lambda: self._open_page(0))
        self.tray_menu.addAction(t("Переводчик и словари")).triggered.connect(lambda: self._open_page(1))
        self.tray_menu.addAction(t("Настройки")).triggered.connect(lambda: self._open_page(2))
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(t("❤️ Поддержать")).triggered.connect(self._tray_donate)
        self.tray_menu.addAction(t("Выход")).triggered.connect(self.app.quit)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.setToolTip(t("WordSnap — экранный переводчик и словарь"))
        if not self.tray.isVisible():
            self.tray.show()

    def _tray_donate(self):
        from app.ui.thank_you_dialog import open_donation_support
        open_donation_support(self.window if (self.window and self.window.isVisible()) else None)

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._open_page(0)

    def _open_page(self, idx: int):
        if self.window is None:
            self._create_main_window(show=False)
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
        if self.freeze_overlay and self.freeze_overlay.isVisible():
            self._close_freeze_mode()
            return
        if self.overlay and self.overlay.isVisible():
            self.overlay.close()
            self.overlay = None
            self._resume_paused_process()
            return
        if self._busy:
            return

        mode = CONFIG.get("mode", "dictionary")
        # Если режим переводчика, но зажат Shift/Ctrl (или Alt, если он не входит в сам хоткей) — режим словаря
        is_alt = self.hotkeys.is_alt_down()
        is_shift = self.hotkeys.is_shift_down()
        is_ctrl = self.hotkeys.is_ctrl_down()
        req_mods, _ = parse_hotkey(CONFIG.get("hotkey", "alt+q"))
        extra_mod = ((is_alt and "alt" not in req_mods) or
                     (is_shift and "shift" not in req_mods) or
                     (is_ctrl and "ctrl" not in req_mods))
        if mode == "translator" and extra_mod:
            self._dispatch_dictionary_mode(x, y)
        elif mode == "translator":
            self.run_translator_mode(x, y)
        else:
            self._dispatch_dictionary_mode(x, y)

    def _dispatch_dictionary_mode(self, x: int, y: int):
        if CONFIG.get("freeze_screen"):
            self.run_freeze_dictionary_mode(x, y)
        else:
            self.run_dictionary_mode(x, y)

    def on_escape(self):
        """Глобальный Esc: закрывает попап/оверлей даже если фокус не на них."""
        self._popup_open = False
        if self.freeze_overlay and self.freeze_overlay.isVisible():
            self._close_freeze_mode()
            return
        if self.popup.isVisible():
            self.popup.close_animated()      # окно сжимается и гаснет (не мгновенно)
        if self.overlay and self.overlay.isVisible():
            self.overlay.close()
            self.overlay = None
            self._resume_paused_process()
        self.close_highlight()

    def _close_freeze_mode(self):
        """Корректный выход из режима заморозки (Resume & Restore)."""
        # 1. Сначала возобновляем процесс игры (NtResumeProcess и CloseHandle)
        self._resume_paused_process(force=True)

        # 2. Закрываем / скрываем оверлей
        overlay = self.freeze_overlay
        self.freeze_overlay = None
        if overlay:
            try:
                overlay.close()
            except Exception:
                pass

        if self.popup and self.popup.isVisible():
            self.popup.close_animated()

        # 3. Возвращаем фокус окну игры
        if getattr(self, "_saved_game_hwnd", None) and sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(self._saved_game_hwnd)
            except Exception:
                pass
            self._saved_game_hwnd = None

    # ============================ РЕЖИМ СЛОВАРЯ ============================
    def run_freeze_dictionary_mode(self, x: int, y: int):
        """Режим «Заморозка экрана + Свободный курсор» для игр без видимого курсора."""
        self.close_highlight()

        # Шаг 3.1: До показа оверлея сохраняем game_hwnd и game_pid
        app_name, win_title, game_pid, game_hwnd = active_window_title()
        if sys.platform == "win32" and not game_hwnd:
            try:
                import ctypes
                import ctypes.wintypes as wt
                game_hwnd = int(ctypes.windll.user32.GetForegroundWindow())
                pid_dw = wt.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(game_hwnd, ctypes.byref(pid_dw))
                game_pid = int(pid_dw.value)
            except Exception:
                pass
        self._saved_game_hwnd = game_hwnd
        self._saved_game_pid = game_pid

        self._check_fullscreenize(app_name, win_title, game_hwnd)

        # Шаг 3.2: Делаем скриншот экрана
        try:
            img, mon = capture.grab_monitor_at(x, y)
        except Exception as e:
            self.bridge.error.emit(str(e))
            self._resume_paused_process(force=True)
            return

        self._freeze_full_shot = img

        # Шаг 3.3: Создаём и показываем FreezeFrameOverlay
        self.freeze_overlay = FreezeFrameOverlay(
            img, mon,
            on_word_clicked=lambda w, s, sx, sy, ww, wh: self._on_freeze_word_clicked(w, s, sx, sy, ww, wh, app_name, win_title),
            on_close=self._on_freeze_closed
        )
        self.freeze_overlay.setGeometry(mon["left"], mon["top"], mon["width"], mon["height"])
        self.freeze_overlay.showFullScreen()
        self.freeze_overlay.raise_()
        self.freeze_overlay.activateWindow()

        # Шаг 3.4: Принудительный перехват фокуса и сброс захвата курсора,
        # пока игра ещё жива и успевает обработать потерю фокуса (WM_KILLFOCUS)
        force_foreground_and_release_cursor(self.freeze_overlay)

        # Шаг 3.5: Запуск OCR-потока
        self.freeze_overlay._start_ocr_thread()

        # Шаг 3.6: Если включена автопауза, вызываем заморозку процесса с задержкой 30 мс
        target = (CONFIG.get("autopause_window") or "").strip().lower()
        if target and game_pid and (target in (app_name or "").lower() or target in (win_title or "").lower()):
            def do_pause():
                if self.freeze_overlay and self.freeze_overlay.isVisible():
                    self._suspend_process(game_pid, app_name)
                    if sys.platform == "win32":
                        try:
                            import ctypes
                            ctypes.windll.user32.ClipCursor(None)
                        except Exception:
                            pass
            QTimer.singleShot(30, do_pause)

    def _on_freeze_closed(self):
        """Коллбэк при закрытии оверлея изнутри (Esc / Q / клик по крестику)."""
        # 1. Сначала возобновляем процесс игры
        self._resume_paused_process(force=True)

        # 2. Скрываем оверлей и попап
        self.freeze_overlay = None
        if self.popup and self.popup.isVisible():
            self.popup.close_animated()

        # 3. Возвращаем фокус окну игры
        if getattr(self, "_saved_game_hwnd", None) and sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(self._saved_game_hwnd)
            except Exception:
                pass
            self._saved_game_hwnd = None

    def _on_freeze_word_clicked(self, w_clean: str, sentence: str, sx: int, sy: int, w: int, h: int, app_name: str, win_title: str):
        if not w_clean:
            return

        shot_name = WORDS.save_screenshot(self._freeze_full_shot)
        self._pending_entry = {
            "src_lang": CONFIG.get("ocr_lang"),
            "dst_lang": CONFIG.get("looktionary_pro")["word_trans_lang"],
            "dict_form": w_clean, "word_in_text": w_clean,
            "context": sentence, "screenshot": shot_name,
            "source_app": app_name, "source_title": win_title,
            "complete": False,
        }
        existing_word = WORDS.find_by_word(w_clean)
        if existing_word:
            self._pending_entry["id"] = existing_word["id"]
            self.bridge.bookmark_saved.emit(True)
        elif CONFIG.get("auto_save_words", False):
            self._pending_entry = WORDS.add(self._pending_entry)
            self.bridge.words_changed.emit()
            self.bridge.bookmark_saved.emit(True)
        else:
            self.bridge.bookmark_saved.emit(False)

        anki_enabled = CONFIG.get("anki_enabled", False)
        self.popup.set_anki_visible(anki_enabled)
        if anki_enabled:
            self.popup.set_anki_state("idle" if self._anki_connected else "disconnected")
            self._check_anki_connection_async(word_to_check=w_clean)

        import time
        self._popup_open_time = time.time()

        order = [k for k in CONFIG.get("sources_order") if CONFIG.get("sources_enabled").get(k)]
        self.popup.open_at(sx + w // 2, sy + h, order, light=False)
        self.popup.raise_()
        if sys.platform == "win32":
            try:
                import ctypes
                HWND_TOPMOST = -1
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_SHOWWINDOW = 0x0040
                ctypes.windll.user32.SetWindowPos(int(self.popup.winId()), HWND_TOPMOST, 0, 0, 0, 0,
                                                 SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            except Exception:
                pass
        self.popup.activateWindow()
        self._popup_open = True

        self._start_lookup_jobs(w_clean, sentence, app_name, order)

    def run_dictionary_mode(self, x: int, y: int):
        self.close_highlight()
        app_name, win_title, pid, hwnd = active_window_title()
        self._check_autopause(app_name, win_title, pid)
        self._check_fullscreenize(app_name, win_title, hwnd)
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
        import time
        self._popup_open_time = time.time()
        self.popup.open_at(x, y, order, light=light_bg)
        self._popup_open = True

        def worker():
            self._busy = True
            try:
                engine = ocr.get_engine(CONFIG)
                lines = engine.recognize(img)
                line, word = ocr.word_at_point(lines, x - left, y - top)
                if word is None:
                    for k in order:
                        self.bridge.source_failed.emit(k, t("Под курсором не найден текст."))
                    if sys.platform == "win32":
                        self.tray.showMessage(
                            "WordSnap",
                            t("Под курсором нет текста. Для игр без курсора включите «Заморозка экрана» в Настройках."),
                            QSystemTrayIcon.Information, 2500
                        )
                    return
                # подсветка найденного слова прямо на экране (экранные координаты)
                self.bridge.highlight_ready.emit(
                    int(left + word.x), int(top + word.y),
                    int(word.w), int(word.h))
                w_clean = ocr.clean_word(word.text)
                sentence = ocr.sentence_around(lines, line, word)

                # Если предыдущее слово не сохраняли в библиотеку — удаляем старый скриншот
                self._discard_pending_screenshot()

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
                # Личный словарь: автосохранение или проверка наличия
                existing_word = WORDS.find_by_word(w_clean)
                if existing_word:
                    self._pending_entry["id"] = existing_word["id"]
                    self.bridge.bookmark_saved.emit(True)
                elif CONFIG.get("auto_save_words", False):
                    self._pending_entry = WORDS.add(self._pending_entry)
                    self.bridge.words_changed.emit()
                    self.bridge.bookmark_saved.emit(True)
                else:
                    self.bridge.bookmark_saved.emit(False)

                # Anki: если интеграция включена — кнопка видна в попапе
                anki_enabled = CONFIG.get("anki_enabled", False)
                self.popup.set_anki_visible(anki_enabled)
                if anki_enabled:
                    if self._anki_connected:
                        self.popup.set_anki_state("idle")
                    else:
                        self.popup.set_anki_state("disconnected", t("Проверка подключения к AnkiConnect..."))
                    self._check_anki_connection_async(word_to_check=w_clean)

                self._start_lookup_jobs(w_clean, sentence, app_name, order)
            except Exception as e:
                traceback.print_exc()
                for k in order:
                    self.bridge.source_failed.emit(k, f"{t('OCR-ошибка')}: {e}")
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _start_lookup_jobs(self, w_clean: str, sentence: str, app_name: str, order: list[str]):
        """Запуск асинхронных задач получения перевода и словарных статей."""
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
                self.bridge.source_failed.emit("translator_pro", f"{t('Ошибка')}: {e}")

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
                self.bridge.source_failed.emit("looktionary_pro", f"{t('Ошибка')}: {e}")

        # запускаем все источники ОДНОВРЕМЕННО — каждый присылает результат сам по себе
        jobs = {"translator_pro": do_translator,
                "looktionary_pro": do_looktionary}

        from app.dictionaries import DICTIONARIES, normalize_key
        for k in order:
            if k not in jobs:
                def make_offline_job(src_key):
                    def do_offline():
                        try:
                            d_id = normalize_key(src_key)
                            res = DICTIONARIES.lookup(w_clean, d_id, context=sentence)
                            self.bridge.offline_dict_ready.emit(src_key, res)
                            if res and self._pending_entry is not None:
                                if "offline_entries" not in self._pending_entry:
                                    self._pending_entry["offline_entries"] = []
                                self._pending_entry["offline_entries"].extend(res)
                        except Exception as e:
                            self.bridge.source_failed.emit(src_key, f"{t('Ошибка')}: {e}")
                    return do_offline
                jobs[k] = make_offline_job(k)

        threads = [threading.Thread(target=jobs[k], daemon=True)
                   for k in order if k in jobs]
        for th in threads:
            th.start()

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
                         complete=bool(data.get("definition") or data.get("word_translation")))
            self.bridge.words_changed.emit()
        elif self._pending_entry is not None:
            self._pending_entry.update(data)
            if data.get("definition") or data.get("word_translation"):
                self._pending_entry["complete"] = True

    def toggle_pending_bookmark(self):
        """Клик по кнопке закладки (🔖 / ✅) в попапе."""
        if not self._pending_entry:
            return
        entry_id = self._pending_entry.get("id")
        if entry_id:
            WORDS.delete([entry_id])
            self._pending_entry.pop("id", None)
            self.popup.set_bookmark_saved(False)
            self.bridge.words_changed.emit()
        else:
            if self._pending_entry.get("definition") or self._pending_entry.get("word_translation"):
                self._pending_entry["complete"] = True
            self._pending_entry = WORDS.add(self._pending_entry)
            self.popup.set_bookmark_saved(True)
            self.bridge.words_changed.emit()

    def save_pending_entry(self):
        """Сохранение текущего слова (обратная совместимость)."""
        self.toggle_pending_bookmark()

    def _check_anki_connection_async(self, word_to_check: str = ""):
        """Фоновая проверка связи с AnkiConnect. Если включено — кнопка в попапе всегда отображается."""
        def task():
            enabled = CONFIG.get("anki_enabled", False)
            self.bridge.anki_visible.emit(enabled)
            if not enabled:
                self._anki_connected = False
                return

            try:
                from app.anki import get_anki_client
                client = get_anki_client()
                ok, msg = client.check_connection(timeout=2.5)
                self._anki_connected = ok
                try:
                    if ok:
                        deck = CONFIG.get("anki_deck")
                        if word_to_check and deck and client.check_note_exists(deck, word_to_check):
                            self.bridge.anki_status.emit("exists", t("Слово уже есть в Anki"))
                        else:
                            self.bridge.anki_status.emit("idle", "")
                    else:
                        self.bridge.anki_status.emit("disconnected", msg)
                except (RuntimeError, Exception):
                    pass
            except Exception as e:
                self._anki_connected = False
                try:
                    self.bridge.anki_status.emit("disconnected", str(e))
                except (RuntimeError, Exception):
                    pass

        threading.Thread(target=task, daemon=True).start()

    def add_current_to_anki(self):
        """Добавление текущего слова из попапа в Anki через AnkiConnect."""
        if not self._pending_entry:
            self.popup.set_anki_state("error", t("Нет данных слова"))
            return

        entry = self._pending_entry
        entry["anki_in_progress"] = True

        def worker():
            try:
                import time
                for _ in range(15):
                    if (entry.get("complete")
                            or entry.get("definition")
                            or entry.get("offline_entries")):
                        break
                    time.sleep(0.1)

                from app.anki import get_anki_client
                client = get_anki_client()
                note_id = client.add_word_note(entry)
                self.bridge.anki_status.emit("added", f"{t('Добавлено в Anki')} (ID: {note_id})")
                if entry.get("id"):
                    WORDS.update(entry["id"], in_anki=True, anki_id=note_id)
                    self.bridge.words_changed.emit()
            except Exception as e:
                msg = str(e)
                if "подключиться" in msg.lower() or "connection" in msg.lower():
                    self._anki_connected = False
                    self.bridge.anki_status.emit("disconnected", msg)
                elif "duplicate" in msg.lower() or "дубликат" in msg.lower():
                    self.bridge.anki_status.emit("exists", t("Слово уже есть в Anki"))
                else:
                    self.bridge.anki_status.emit("error", msg)
            finally:
                entry["anki_in_progress"] = False
                # Если слово не сохранено в библиотеку и окно закрыто — удаляем локальный скриншот (Anki уже сохранил себе)
                if not entry.get("id") and (entry.get("pending_delete_shot") or not self._popup_open):
                    shot = entry.get("screenshot")
                    if shot:
                        WORDS.delete_screenshot(shot)
                        entry["screenshot"] = ""

        threading.Thread(target=worker, daemon=True).start()

    def _on_anki_settings_changed(self):
        self._check_anki_connection_async()

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
        app_name, win_title, pid, hwnd = active_window_title()
        self._check_autopause(app_name, win_title, pid)
        self._check_fullscreenize(app_name, win_title, hwnd)

        try:
            img, mon = capture.grab_monitor_at(x, y)
        except Exception as e:
            self.bridge.error.emit(str(e))
            self._resume_paused_process()
            return

        frozen = None
        if CONFIG.get("freeze_screen"):
            try:
                img_rgba = img.convert("RGBA")
                raw_bytes = img_rgba.tobytes()
                qimg = QImage(raw_bytes, img.width, img.height,
                              img.width * 4, QImage.Format_RGBA8888)
                frozen = QPixmap.fromImage(qimg.copy())
            except Exception:
                frozen = None

        # Уведомление в трей о начале распознавания и перевода
        self.tray.showMessage("WordSnap", t("Распознавание и перевод текста на экране..."),
                              QSystemTrayIcon.Information, 1500)

        def worker():
            self._busy = True
            try:
                engine = ocr.get_engine(CONFIG)
                lines = engine.recognize(img)
                lines = [l for l in lines if len(l.text.strip()) > 1][:60]
                if not lines:
                    self.bridge.error.emit(t("Текст на экране не обнаружен."))
                    self._resume_paused_process()
                    return
                gem = get_ai(CONFIG)
                if not gem.ready:
                    self.bridge.error.emit(t(NO_KEY_MSG))
                    self._resume_paused_process()
                    return
                texts = [l.text for l in lines]
                tp_cfg = CONFIG.get("translator_pro") or {}
                tgt = tp_cfg.get("target_lang", "ru")
                translated = gem.translate_lines(texts, tgt, app_name)
                items = [(QRect(int(l.x), int(l.y), int(l.w), int(l.h)), tr)
                         for l, tr in zip(lines, translated)]
                self.bridge.overlay_ready.emit(mon, items, frozen)
            except Exception as e:
                traceback.print_exc()
                self.bridge.error.emit(f"{t('Ошибка перевода')}: {e}")
                self._resume_paused_process()
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
            self.bridge.error.emit(t("Укажите API-ключ Gemini в Настройках → ИИ-источники."))
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
    if len(sys.argv) >= 3 and sys.argv[1] == "--import-dict":
        from app.dictionaries import run_cli_import
        sys.exit(run_cli_import(sys.argv[2]))

    # Windows показывает в панели задач иконку python.exe, пока у процесса нет
    # своего AppUserModelID. Задаём его — тогда таскбар берёт иконку окна.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("WordSnap.Desktop.App")
        except Exception:
            pass

    # Проверка на повторный запуск (Single Instance) через Win32 Mutex
    _single_mutex = None
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            mutex_name = "Global\\WordSnap_SingleInstance_Mutex"
            _single_mutex = kernel32.CreateMutexW(None, False, mutex_name)
            last_err = kernel32.GetLastError()
            if last_err == 183:  # ERROR_ALREADY_EXISTS
                print("WordSnap is already running. Exiting duplicate instance.")
                sys.exit(0)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("WordSnap")
    from PySide6.QtGui import QFont
    app.setFont(QFont("Segoe UI", 10))
    from app.ui.theme import apply_palette
    apply_palette(app)                  # палитра под выбранную тему (важно для светлой)
    app.setWindowIcon(make_app_icon())  # иконка приложения (панель задач)
    app.setQuitOnLastWindowClosed(False)
    ctl = Controller(app)
    ctl.bridge.error.connect(lambda m: ctl.tray.showMessage("WordSnap", m,
                                                            QSystemTrayIcon.Warning, 4000))

    def _on_about_to_quit():
        if getattr(ctl, "tray", None) is not None:
            try:
                ctl.tray.hide()
            except Exception:
                pass
        if ctl.window is not None:
            from app.ui.theme import save_window_size
            save_window_size("main_window", ctl.window, save_maximized=True, save_pos=True)
    app.aboutToQuit.connect(_on_about_to_quit)
    import signal
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    sig_timer = QTimer()
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start(400)
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    if "--import-dict" not in sys.argv:
        print("Starting WordSnap...")
    main()