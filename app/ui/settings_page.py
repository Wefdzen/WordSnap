import os
import sys
import threading

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
                               QComboBox, QPushButton, QLineEdit,
                               QButtonGroup, QFrame, QKeySequenceEdit,
                               QDialog, QListWidget, QMessageBox)
from PySide6.QtGui import QKeySequence

from ..config import CONFIG, LANGS
from ..anki import get_anki_client
from ..gemini import fetch_active_groq_models, fetch_active_gemini_models, Groq, Gemini
from .widgets import ToggleSwitch, SettingRow, flag_icon, FluentRadio
from .theme import TEXT_DIM, ACCENT, BG_CARD, BG_HOVER, BORDER, TEXT, apply_native_window_theme, save_window_size, restore_window_size
from .i18n import t
from .anki_dialog import AnkiCardsDialog
from .hotkey_dialog import HotkeyRecordDialog
from .thank_you_dialog import open_donation_support, APP_VERSION

def section(title: str) -> QLabel:
    l = QLabel(title); l.setObjectName("SectionTitle")
    return l

class WindowPickerDialog(QDialog):
    """Диалог выбора или ручного ввода целевого окна/процесса с возможностью моментального тестирования."""
    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self.key = key
        is_pause = (key == "autopause_window")
        self.setWindowTitle(t("Настройка целевого окна"))
        restore_window_size("window_picker", self, 520, 500)
        apply_native_window_theme(int(self.winId()))
        lay = QVBoxLayout(self); lay.setContentsMargins(20, 20, 20, 20); lay.setSpacing(10)

        desc = (t("Укажите заголовок или имя процесса игры/приложения, которое нужно автоматически ставить на паузу:")
                if is_pause else
                t("Укажите заголовок или имя процесса игры/приложения, которое нужно растягивать на весь экран:"))
        lbl = QLabel(desc); lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 13px; font-weight: 500;")
        lay.addWidget(lbl)

        self.edit = QLineEdit(CONFIG.get(key, ""))
        self.edit.setPlaceholderText(t("Например: eldenring, zen.exe, game..."))
        self.edit.setStyleSheet("padding: 8px 12px; font-size: 13px;")
        lay.addWidget(self.edit)

        lay.addWidget(QLabel(t("Выберите окно из списка запущенных приложений или введите часть заголовка/имени вручную:")))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(t("Фильтр приложений..."))
        self.filter_edit.textChanged.connect(self._filter_list)
        lay.addWidget(self.filter_edit)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("QListWidget::item { padding: 6px 10px; font-size: 13px; }")
        self.list_widget.itemClicked.connect(lambda it: self.edit.setText(it.text()))
        self.list_widget.itemDoubleClicked.connect(lambda it: (self.edit.setText(it.text()), self._save()))
        lay.addWidget(self.list_widget, 1)

        self._all_items = []
        self._load_processes()

        btn_bar = QHBoxLayout(); btn_bar.setSpacing(8)
        if not is_pause:
            btn_test = QPushButton("⤢ " + t("Развернуть окно сейчас (тест)"))
            btn_test.setCursor(Qt.PointingHandCursor)
            btn_test.clicked.connect(self._test_fullscreen)
            btn_bar.addWidget(btn_test)
        else:
            btn_test = QPushButton("⏸ " + t("Проверить паузу (на 3 сек)"))
            btn_test.setCursor(Qt.PointingHandCursor)
            btn_test.clicked.connect(self._test_pause)
            btn_bar.addWidget(btn_test)

        btn_clear = QPushButton(t("Отключить"))
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(lambda: self.edit.setText(""))
        btn_bar.addWidget(btn_clear)
        btn_bar.addStretch(1)

        btn_cancel = QPushButton(t("Отмена"))
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(btn_cancel)

        btn_save = QPushButton(t("Сохранить"))
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setObjectName("PrimaryBtn")
        btn_save.clicked.connect(self._save)
        btn_bar.addWidget(btn_save)

        lay.addLayout(btn_bar)

    def closeEvent(self, e):
        save_window_size("window_picker", self)
        super().closeEvent(e)

    def _load_processes(self):
        items = set()
        try:
            import subprocess
            out = subprocess.check_output("tasklist /FO CSV /NH", shell=True, text=True, errors="replace")
            for line in out.strip().splitlines():
                parts = [p.strip().strip('"') for p in line.split('","')]
                if parts and parts[0]:
                    exe = parts[0]
                    if exe.lower() not in ("svchost.exe", "conhost.exe", "system", "registry",
                                           "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
                                           "lsass.exe", "fontdrvhost.exe"):
                        items.add(exe)
        except Exception:
            pass
        self._all_items = sorted(items, key=lambda s: s.lower())
        self._filter_list("")

    def _filter_list(self, query: str = ""):
        self.list_widget.clear()
        q = query.strip().lower()
        for it in self._all_items:
            if not q or q in it.lower():
                self.list_widget.addItem(it)

    def _save(self):
        val = self.edit.text().strip()
        CONFIG.set(self.key, val)
        self.accept()

    def _test_fullscreen(self):
        val = self.edit.text().strip()
        if not val or sys.platform != "win32":
            return
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        target = val.lower()
        found_hwnd = 0

        def enum_cb(hwnd, _):
            nonlocal found_hwnd
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.lower()
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                pname = ""
                h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
                if h:
                    nbuf = ctypes.create_unicode_buffer(512)
                    size = wintypes.DWORD(512)
                    if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, nbuf, ctypes.byref(size)):
                        pname = os.path.basename(nbuf.value).lower()
                    ctypes.windll.kernel32.CloseHandle(h)
                if target in title or target in pname:
                    found_hwnd = hwnd
                    return False
            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(EnumWindowsProc(enum_cb), 0)

        if found_hwnd:
            GWL_STYLE = -16
            WS_CAPTION = 0x00C00000
            WS_THICKFRAME = 0x00040000
            WS_MINIMIZEBOX = 0x00020000
            WS_MAXIMIZEBOX = 0x00010000
            WS_SYSMENU = 0x00080000
            SWP_FRAMECHANGED = 0x0020
            SWP_SHOWWINDOW = 0x0040
            style = user32.GetWindowLongW(found_hwnd, GWL_STYLE)
            style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
            user32.SetWindowLongW(found_hwnd, GWL_STYLE, style)
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            user32.SetWindowPos(found_hwnd, 0, 0, 0, w, h, SWP_FRAMECHANGED | SWP_SHOWWINDOW)
            QMessageBox.information(self, t("Успех"), t("Окно успешно развёрнуто!"))
        else:
            QMessageBox.warning(self, t("Ошибка"), t("Окно/процесс не найдены. Убедитесь, что приложение запущено."))

    def _test_pause(self):
        val = self.edit.text().strip()
        if not val or sys.platform != "win32":
            return
        import ctypes, time, threading
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        target = val.lower()
        found_pid = 0

        def enum_cb(hwnd, _):
            nonlocal found_pid
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.lower()
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                pname = ""
                h = kernel32.OpenProcess(0x1000, False, pid.value)
                if h:
                    nbuf = ctypes.create_unicode_buffer(512)
                    size = wintypes.DWORD(512)
                    if kernel32.QueryFullProcessImageNameW(h, 0, nbuf, ctypes.byref(size)):
                        pname = os.path.basename(nbuf.value).lower()
                    kernel32.CloseHandle(h)
                if target in title or target in pname:
                    found_pid = pid.value
                    return False
            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(EnumWindowsProc(enum_cb), 0)

        if found_pid:
            def pause_worker():
                h_proc = kernel32.OpenProcess(0x0800, False, found_pid)
                if h_proc:
                    try:
                        ctypes.windll.ntdll.NtSuspendProcess(h_proc)
                        time.sleep(3.0)
                        ctypes.windll.ntdll.NtResumeProcess(h_proc)
                    finally:
                        kernel32.CloseHandle(h_proc)
            threading.Thread(target=pause_worker, daemon=True).start()
            QMessageBox.information(self, t("Успех"), t("Процесс приостановлен на 3 секунды..."))
        else:
            QMessageBox.warning(self, t("Ошибка"), t("Окно/процесс не найдены. Убедитесь, что приложение запущено."))


class SettingsPage(QWidget):
    hotkeys_changed = Signal()
    words_display_changed = Signal()      # изменились настройки отображения списка слов
    anki_settings_changed = Signal()
    groq_check_done = Signal(bool, str, list)
    gemini_check_done = Signal(bool, str, list)
    anki_check_done = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.groq_check_done.connect(self._on_groq_check_done)
        self.gemini_check_done.connect(self._on_gemini_check_done)
        self.anki_check_done.connect(self._on_anki_check_done)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        area = QScrollArea(); area.setWidgetResizable(True)
        outer.addWidget(area)
        host = QWidget(); area.setWidget(host)
        v = QVBoxLayout(host); v.setContentsMargins(24, 6, 24, 24); v.setSpacing(6)

        # ================= Общие =================
        v.addWidget(section(t("Общие")))

        mode_right = QWidget(); mr = QVBoxLayout(mode_right); mr.setSpacing(10)
        self.rb_tr = FluentRadio(t("Режим переводчика"))
        h1 = QLabel(t("Помещает перевод поверх текста. Удерживайте Alt, чтобы\n"
                      "смотреть отдельные слова в режиме словаря."))
        h1.setObjectName("Dim"); h1.setContentsMargins(26, 0, 0, 6)
        self.rb_dict = FluentRadio(t("Режим словаря (Режим изучения)"))
        h2 = QLabel(t("Определение и перевод слов во всплывающем окне.\n"
                      "Сохраняет слова в личный словарь."))
        h2.setObjectName("Dim"); h2.setContentsMargins(26, 0, 0, 0)
        for w in (self.rb_tr, h1, self.rb_dict, h2):
            mr.addWidget(w)
        grp = QButtonGroup(self); grp.addButton(self.rb_tr); grp.addButton(self.rb_dict)
        (self.rb_dict if CONFIG.get("mode") == "dictionary" else self.rb_tr).setChecked(True)
        self.rb_tr.toggled.connect(lambda on: on and CONFIG.set("mode", "translator"))
        self.rb_dict.toggled.connect(lambda on: on and CONFIG.set("mode", "dictionary"))
        v.addWidget(SettingRow("language-exchange.svg", t("Режим приложения"), right=mode_right))

        sw_auto = ToggleSwitch(CONFIG.get("autostart"))
        sw_auto.toggled.connect(self._set_autostart)
        v.addWidget(SettingRow("power.svg", t("Запускать при старте Windows"), right=sw_auto))

        btn_wizard = QPushButton(t("Запустить мастер первоначальной настройки"))
        btn_wizard.setCursor(Qt.PointingHandCursor)
        btn_wizard.clicked.connect(self._open_onboarding)
        v.addWidget(SettingRow("rocket.svg", t("Быстрый старт"),
                               t("Пройти пошаговую настройку языка, темы, режима и ИИ заново."),
                               btn_wizard))

        # ============ Внешний вид ============
        v.addWidget(section(t("Внешний вид")))
        self.cb_theme = QComboBox()
        for label, val in ((t("Тёмная"), "dark"), (t("Светлая"), "light"), (t("Системная"), "system")):
            self.cb_theme.addItem(label, val)
        self.cb_theme.setCurrentIndex(max(0, ["dark", "light", "system"].index(
            CONFIG.get("ui_theme", "dark"))))
        self.cb_theme.setFixedWidth(220)
        self.cb_theme.currentIndexChanged.connect(
            lambda: self._apply_restart("ui_theme", self.cb_theme.currentData()))
        v.addWidget(SettingRow("palette.svg", t("Тема оформления"),
                               t("Тёмная, светлая или как в системе."), self.cb_theme))

        self.cb_uilang = QComboBox()
        for label, val in (("English", "en"), ("Русский", "ru")):
            self.cb_uilang.addItem(label, val)
        self.cb_uilang.setCurrentIndex(0 if CONFIG.get("ui_lang", "en") == "en" else 1)
        self.cb_uilang.setFixedWidth(220)
        self.cb_uilang.currentIndexChanged.connect(
            lambda: self._apply_restart("ui_lang", self.cb_uilang.currentData()))
        v.addWidget(SettingRow("languages-world.svg", t("Язык интерфейса"),
                               t("Язык меню и настроек приложения."), self.cb_uilang))

        # ============ Горячие клавиши ============
        v.addWidget(section(t("Горячие клавиши")))
        hotkey_right = QWidget()
        hkh = QHBoxLayout(hotkey_right)
        hkh.setContentsMargins(0, 0, 0, 0)
        hkh.setSpacing(10)

        cur_hk = CONFIG.get("hotkey", "alt+q").upper()
        self.btn_hotkey = QPushButton(f"⌨  {cur_hk}")
        self.btn_hotkey.setCursor(Qt.PointingHandCursor)
        self.btn_hotkey.setMinimumWidth(120)
        self.btn_hotkey.setStyleSheet(f"""
            QPushButton {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 600;
                color: {TEXT};
            }}
            QPushButton:hover {{
                border-color: {ACCENT};
                background: {BG_HOVER};
            }}
        """)
        self.btn_hotkey.clicked.connect(self._open_hotkey_dialog)

        self.btn_assign_hk = QPushButton(t("Назначить"))
        self.btn_assign_hk.setCursor(Qt.PointingHandCursor)
        self.btn_assign_hk.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: #ffffff;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: #50bcf0;
            }}
        """)
        self.btn_assign_hk.clicked.connect(self._open_hotkey_dialog)

        hkh.addWidget(self.btn_hotkey)
        hkh.addWidget(self.btn_assign_hk)
        v.addWidget(SettingRow("keyboard.svg", t("Горячая клавиша"), right=hotkey_right))

        mouse_right = QWidget(); mh = QHBoxLayout(mouse_right); mh.setSpacing(8)
        self.cb_mod = QComboBox()
        for label, val in ((t("Без клавиши"), "none"), ("Alt", "alt"), ("Ctrl", "ctrl"), ("Shift", "shift")):
            self.cb_mod.addItem(f"🖥  {label}", val)
        self.cb_mod.setCurrentIndex(max(0, ["none", "alt", "ctrl", "shift"].index(
            CONFIG.get("mouse_hotkey_modifier", "none"))))
        mh.addWidget(self.cb_mod); mh.addWidget(QLabel("＋"))
        self.cb_btn = QComboBox()
        for label, val in ((t("Средняя кнопка"), "middle"), (t("Боковая 1 (X1)"), "x1"),
                           (t("Боковая 2 (X2)"), "x2"), (t("Отключено"), "none")):
            self.cb_btn.addItem(f"🖱  {label}", val)
        cur = CONFIG.get("mouse_hotkey_button", "middle")
        self.cb_btn.setCurrentIndex(max(0, ["middle", "x1", "x2", "none"].index(cur)))
        mh.addWidget(self.cb_btn)
        self.cb_mod.currentIndexChanged.connect(self._save_mouse)
        self.cb_btn.currentIndexChanged.connect(self._save_mouse)
        v.addWidget(SettingRow("mouse.svg", t("Горячая кнопка мыши"), right=mouse_right))

        # ===== Распознавание текста на экране (OCR) =====
        v.addWidget(section(t("Распознавание текста на экране (OCR)")))
        self.cb_ocr = QComboBox()
        self.cb_ocr.addItem(t("Рекомендуемый (Windows OCR)\nМаксимальная точность без установки."), "auto")
        self.cb_ocr.addItem(t("Tesseract\nТребует установленный Tesseract OCR."), "tesseract")
        self.cb_ocr.setCurrentIndex(0 if CONFIG.get("ocr_engine") in ("auto", "windows") else 1)
        self.cb_ocr.currentIndexChanged.connect(
            lambda: CONFIG.set("ocr_engine", self.cb_ocr.currentData()))
        self.cb_ocr.setFixedWidth(360)
        self.cb_ocr.setMinimumHeight(48)  # две строки текста должны помещаться целиком
        v.addWidget(SettingRow("microchip.svg", t("Движок OCR"), right=self.cb_ocr))

        lang_box = QWidget()
        lang_lay = QHBoxLayout(lang_box)
        lang_lay.setContentsMargins(0, 0, 0, 0)
        lang_lay.setSpacing(8)

        self.cb_lang = QComboBox()
        for code, name, fl in LANGS:
            self.cb_lang.addItem(flag_icon(code), f"  {name}", code)
            if code == CONFIG.get("ocr_lang"):
                self.cb_lang.setCurrentIndex(self.cb_lang.count() - 1)
        self.cb_lang.currentIndexChanged.connect(self._on_ocr_lang_changed)
        self.cb_lang.setFixedWidth(210)
        lang_lay.addWidget(self.cb_lang)

        self.btn_check_ocr = QPushButton(t("Проверить OCR"))
        self.btn_check_ocr.setCursor(Qt.PointingHandCursor)
        self.btn_check_ocr.setFixedHeight(34)
        self.btn_check_ocr.clicked.connect(self._check_ocr_status)
        lang_lay.addWidget(self.btn_check_ocr)

        v.addWidget(SettingRow("languages-world.svg", t("Язык распознавания"),
                               t("Выберите язык, соответствующий тексту на экране. "
                                 "Иначе распознавание может быть неправильным."), lang_box))

        # ===== Взаимодействие с играми и приложениями =====
        v.addWidget(section(t("Взаимодействие с играми и приложениями")))
        sw1 = ToggleSwitch(CONFIG.get("overlay_active_window"))
        sw1.toggled.connect(lambda on: CONFIG.set("overlay_active_window", on))
        v.addWidget(SettingRow("layers.svg", f"{t('Делать оверлей активным окном')}  ⓘ",
                               t("Одни игры работают лучше при включённой функции, другие — при "
                                 "выключенной."), sw1))
        sw2 = ToggleSwitch(CONFIG.get("freeze_screen"))
        sw2.toggled.connect(lambda on: CONFIG.set("freeze_screen", on))
        v.addWidget(SettingRow("snowflake.svg", t("Заморозка экрана"),
                               t("Фиксирует изображение в момент нажатия горячей клавиши. "
                                 "Не ставит игры и программы на паузу."), sw2))
        v.addWidget(SettingRow("pause.svg", t("Авто-пауза игр и приложений"),
                               t("Автоматически приостанавливает игры. Так вы точно не пропустите "
                                 "важные диалоги в кат-сценах."),
                               self._window_btn("autopause_window")))
        v.addWidget(SettingRow("arrow-up-right-and-arrow-down-left-from-center.svg", t("Развернуть игру во весь экран"),
                               t("Растягивает оконную игру на весь экран. Используйте это, если "
                                 "эксклюзивный полноэкранный режим игры не позволяет отобразить "
                                 "WordSnap."), self._window_btn("fullscreenize_window")))

        # ================= Слова =================
        v.addWidget(section(t("Слова")))
        sw3 = ToggleSwitch(CONFIG.get("auto_save_words", False))
        sw3.toggled.connect(lambda on: CONFIG.set("auto_save_words", on))
        v.addWidget(SettingRow("disk.svg", t("Автоматически сохранять слова"),
                               t("Сохранять каждое вызванное слово в личный словарь. Если выключено — сохранение только по кнопке 🔖 в окне перевода."),
                               right=sw3))
        sw4 = ToggleSwitch(CONFIG.get("auto_crop_screenshots"))
        sw4.toggled.connect(lambda on: CONFIG.set("auto_crop_screenshots", on))
        v.addWidget(SettingRow("scissors.svg", t("Автообрезка скриншотов"),
                               t("Автоматически обрезать скриншоты, оставляя только текст вокруг "
                                 "слова."), sw4))
        sw5 = ToggleSwitch(CONFIG.get("show_duplicate_badge"))
        sw5.toggled.connect(lambda on: (CONFIG.set("show_duplicate_badge", on),
                                        self.words_display_changed.emit()))
        v.addWidget(SettingRow("layers.svg", t("Помечать повторяющиеся слова"),
                               t("Показывать значок у слов, которые уже есть в словаре."), sw5))

        # ================= Anki =================
        v.addWidget(section(t("Anki")))

        self.sw_anki = ToggleSwitch(CONFIG.get("anki_enabled", False))
        self.sw_anki.toggled.connect(self._set_anki_enabled)
        v.addWidget(SettingRow("plug-connection.svg", t("Включить интеграцию с Anki"),
                               t("Добавление слов, определений, контекста и озвучки в колоду Anki через AnkiConnect."),
                               right=self.sw_anki))

        # Строка статуса подключения
        status_row = QFrame(); status_row.setObjectName("SettingRow")
        srl = QHBoxLayout(status_row); srl.setContentsMargins(16, 8, 16, 8); srl.setSpacing(12)
        ic_st = QLabel("ⓘ"); ic_st.setStyleSheet(f"color: {ACCENT}; font-size: 14px;")
        srl.addWidget(ic_st, 0, Qt.AlignVCenter)
        self.lbl_anki_status = QLabel()
        self.lbl_anki_status.setTextFormat(Qt.RichText)
        srl.addWidget(self.lbl_anki_status, 1)
        btn_chk = QPushButton("🔄 " + t("Проверить"))
        btn_chk.setCursor(Qt.PointingHandCursor)
        btn_chk.clicked.connect(self._check_anki_status)
        srl.addWidget(btn_chk, 0, Qt.AlignVCenter)
        v.addWidget(status_row)

        self.anki_server_input = QLineEdit(CONFIG.get("anki_server", "http://127.0.0.1:8765"))
        self.anki_server_input.setPlaceholderText("http://127.0.0.1:8765")
        self.anki_server_input.setFixedWidth(280)
        self.anki_server_input.editingFinished.connect(self._save_anki_server)
        v.addWidget(SettingRow("globe.svg", t("Адрес сервера AnkiConnect"),
                               t("URL-адрес сервера AnkiConnect (по умолчанию http://127.0.0.1:8765)."),
                               right=self.anki_server_input))

        self.anki_tags_input = QLineEdit(CONFIG.get("anki_tags", "wordsnap"))
        self.anki_tags_input.setPlaceholderText("wordsnap yomitan")
        self.anki_tags_input.setFixedWidth(280)
        self.anki_tags_input.editingFinished.connect(self._save_anki_tags)
        v.addWidget(SettingRow("layers.svg", t("Теги карточек"),
                               t("Список тегов через пробел или запятую, добавляемых к создаваемым карточкам."),
                               right=self.anki_tags_input))

        btn_config_anki = QPushButton(t("Настроить  ›"))
        btn_config_anki.setCursor(Qt.PointingHandCursor)
        btn_config_anki.setFixedWidth(130)
        btn_config_anki.clicked.connect(self._open_anki_cards_dialog)
        v.addWidget(SettingRow("file-export.svg", t("Настройка карточек Anki..."),
                               t("Выбор колоды (Deck), модели (Model) и сопоставление полей ({expression}, {glossary} и др.)."),
                               right=btn_config_anki))

        self._check_anki_status()

        # ================= ИИ-источники =================
        v.addWidget(section(t("ИИ-источники")))

        # --- выбор провайдера ---
        self.cb_provider = QComboBox()
        for label, val in ((t("Groq — быстрый"), "groq"), (t("Google Gemini"), "gemini")):
            self.cb_provider.addItem(label, val)
            if val == CONFIG.get("ai_provider"):
                self.cb_provider.setCurrentIndex(self.cb_provider.count() - 1)
        self.cb_provider.currentIndexChanged.connect(
            lambda: CONFIG.set("ai_provider", self.cb_provider.currentData()))
        self.cb_provider.setFixedWidth(260)
        v.addWidget(SettingRow("plug-connection.svg", t("Провайдер"),
                               t("Groq отвечает быстрее 1 секунды. "
                                 "Можно выбрать Google Gemini."), self.cb_provider))

        # --- Groq ---
        groq_right = QWidget(); gqr = QHBoxLayout(groq_right); gqr.setSpacing(8)
        self.groq_key = QLineEdit(CONFIG.get("groq_api_key"))
        self.groq_key.setEchoMode(QLineEdit.Password)
        self.groq_key.setPlaceholderText("gsk_…")
        self.groq_key.setFixedWidth(280)
        self.groq_key.editingFinished.connect(self._save_groq_key)
        gqr.addWidget(self.groq_key)
        gqr.addWidget(self._reveal_btn(self.groq_key))
        self.btn_check_groq = QPushButton(t("Проверить"))
        self.btn_check_groq.setCursor(Qt.PointingHandCursor)
        self.btn_check_groq.clicked.connect(self._check_groq_key)
        gqr.addWidget(self.btn_check_groq)
        v.addWidget(SettingRow("key.svg", t("API-ключ Groq"),
                               t("Бесплатно: console.groq.com/keys"), groq_right))

        self.cb_groq_model = QComboBox()
        self.cb_groq_model.setFixedWidth(280)
        self.cb_groq_model.currentIndexChanged.connect(
            lambda: CONFIG.set("groq_model", self.cb_groq_model.currentData()))
        self._populate_groq_models()
        v.addWidget(SettingRow("model-cube.svg", t("Модель Groq"),
                               t("«Авто» всегда использует самую новую и мощную модель без ручных обновлений."),
                               self.cb_groq_model))

        # --- Gemini ---
        key_right = QWidget(); kr = QHBoxLayout(key_right); kr.setSpacing(8)
        self.key_input = QLineEdit(CONFIG.get("gemini_api_key"))
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("AIza…")
        self.key_input.setFixedWidth(280)
        self.key_input.editingFinished.connect(self._save_gemini_key)
        kr.addWidget(self.key_input)
        kr.addWidget(self._reveal_btn(self.key_input))
        self.btn_check_gemini = QPushButton(t("Проверить"))
        self.btn_check_gemini.setCursor(Qt.PointingHandCursor)
        self.btn_check_gemini.clicked.connect(self._check_gemini_key)
        kr.addWidget(self.btn_check_gemini)
        v.addWidget(SettingRow("key.svg", t("API-ключ Gemini"),
                               t("aistudio.google.com → Get API key."), key_right))

        self.cb_model = QComboBox()
        self.cb_model.setFixedWidth(280)
        self.cb_model.currentIndexChanged.connect(
            lambda: CONFIG.set("gemini_model", self.cb_model.currentData()))
        self._populate_gemini_models()
        v.addWidget(SettingRow("model-cube.svg", t("Модель Gemini"),
                               t("«Авто» всегда использует самую новую и быструю модель Flash."),
                               self.cb_model))

        # ============ Подвал настроек (Footer) ============
        v.addSpacing(28)

        footer = QWidget()
        footer_lay = QHBoxLayout(footer)
        footer_lay.setContentsMargins(0, 0, 0, 0)
        footer_lay.setSpacing(10)
        footer_lay.setAlignment(Qt.AlignCenter)

        # Ссылка-кнопка "Поддержать разработчика"
        btn_donate = QPushButton(f"❤️  {t('Поддержать разработчика')}")
        btn_donate.setObjectName("FooterDonateBtn")
        btn_donate.setCursor(Qt.PointingHandCursor)
        btn_donate.setToolTip(t("Открыть страницу поддержки разработчика на DonationAlerts"))
        btn_donate.setStyleSheet(f"""
            #FooterDonateBtn {{
                background: transparent;
                border: none;
                color: #ff6b81;
                font-size: 13px;
                font-weight: 600;
                text-decoration: underline;
                padding: 4px 6px;
            }}
            #FooterDonateBtn:hover {{
                color: #ff8da1;
            }}
        """)
        btn_donate.clicked.connect(lambda: open_donation_support(self.window()))
        footer_lay.addWidget(btn_donate)

        # Надпись "by wefdzen v1.2.0"
        lbl_info = QLabel(f"•   by wefdzen v{APP_VERSION}")
        lbl_info.setObjectName("FooterInfoLbl")
        lbl_info.setStyleSheet(f"""
            #FooterInfoLbl {{
                color: {TEXT_DIM};
                font-size: 13px;
                font-weight: 500;
            }}
        """)
        footer_lay.addWidget(lbl_info)

        v.addWidget(footer)
        v.addSpacing(16)
        v.addStretch(1)

    # ------------------------------------------------------------------
    def _apply_restart(self, key: str, value):
        """Сохраняет тему/язык и предлагает перезапустить приложение, чтобы
        изменения применились ко всему интерфейсу."""
        if CONFIG.get(key) == value:
            return
        CONFIG.set(key, value)
        from PySide6.QtWidgets import QMessageBox, QApplication
        from PySide6.QtCore import QProcess
        box = QMessageBox(self)
        box.setWindowTitle(t("Настройки"))
        box.setText(t("Изменения применятся после перезапуска. Перезапустить сейчас?"))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if box.exec() == QMessageBox.Yes:
            if getattr(sys, "frozen", False):
                QProcess.startDetached(sys.executable, sys.argv[1:])
            else:
                QProcess.startDetached(sys.executable, sys.argv)
            QApplication.quit()

    def _window_btn(self, key: str) -> QPushButton:
        b = QPushButton()
        b.setCursor(Qt.PointingHandCursor)
        def update_label():
            val = CONFIG.get(key, "")
            prefix = "⏸ " if key == "autopause_window" else "⤢ "
            if val:
                b.setText(f"{prefix}{val[:16]}…")
                b.setToolTip(f"{t('Окно')}: {val}")
            else:
                b.setText(prefix + t("Выбрать окно"))
                b.setToolTip("")
        update_label()
        def pick():
            dlg = WindowPickerDialog(key, self)
            if dlg.exec():
                update_label()
        b.clicked.connect(pick)
        return b

    def _open_hotkey_dialog(self):
        cur = CONFIG.get("hotkey", "alt+q")
        dlg = HotkeyRecordDialog(cur, self)
        if dlg.exec() == QDialog.Accepted:
            new_hk = dlg.get_hotkey()
            if new_hk:
                CONFIG.set("hotkey", new_hk)
                self.btn_hotkey.setText(f"⌨  {new_hk.upper()}")
                self.hotkeys_changed.emit()

    def _save_mouse(self):
        CONFIG.set("mouse_hotkey_modifier", self.cb_mod.currentData(), save=False)
        CONFIG.set("mouse_hotkey_button", self.cb_btn.currentData(), save=False)
        CONFIG.set("mouse_hotkey_enabled", self.cb_btn.currentData() != "none")
        self.hotkeys_changed.emit()

    def _set_autostart(self, on: bool):
        CONFIG.set("autostart", on)
        if sys.platform != "win32":
            return
        try:
            import winreg
            run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0,
                                winreg.KEY_SET_VALUE) as k:
                if on:
                    exe = sys.executable if getattr(sys, "frozen", False) else \
                        f'"{sys.executable}" "{sys.argv[0]}"'
                    winreg.SetValueEx(k, "WordSnap", 0, winreg.REG_SZ, exe)
                else:
                    for old_name in ("WordSnap", "Lookupper"):
                        try:
                            winreg.DeleteValue(k, old_name)
                        except FileNotFoundError:
                            pass
        except Exception as e:
            print("autostart error:", e)

    def _reveal_btn(self, field: QLineEdit) -> QPushButton:
        """Кнопка «Показать/Скрыть» — переключает видимость введённого ключа."""
        b = QPushButton(t("Показать")); b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        def toggle(on):
            field.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
            b.setText(t("Скрыть") if on else t("Показать"))
        b.toggled.connect(toggle)
        return b

    def _set_anki_enabled(self, on: bool):
        CONFIG.set("anki_enabled", on)
        self.anki_settings_changed.emit()
        self._check_anki_status()

    def _save_anki_server(self):
        url = self.anki_server_input.text().strip()
        if url:
            CONFIG.set("anki_server", url)
            self._check_anki_status()
            self.anki_settings_changed.emit()

    def _save_anki_tags(self):
        tags = self.anki_tags_input.text().strip()
        CONFIG.set("anki_tags", tags)
        self.anki_settings_changed.emit()

    def _open_anki_cards_dialog(self):
        dlg = AnkiCardsDialog(self)
        dlg.settings_saved.connect(self.anki_settings_changed.emit)
        dlg.exec()

    def _check_anki_status(self):
        if not self.sw_anki.isChecked():
            self.lbl_anki_status.setText(
                t("Статус: <span style='color:#999;'>Включите функцию интеграции с Anki</span>")
            )
            return

        self.lbl_anki_status.setText(
            t("Статус: <span style='color:#999;'>⏳ Проверка...</span>")
        )
        def worker():
            try:
                client = get_anki_client()
                ok, msg = client.check_connection(timeout=2.0)
            except Exception as e:
                ok, msg = False, str(e)
            self.anki_check_done.emit(ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_anki_check_done(self, ok: bool, msg: str):
        if not self.sw_anki.isChecked():
            self.lbl_anki_status.setText(
                t("Статус: <span style='color:#999;'>Включите функцию интеграции с Anki</span>")
            )
            return
        if ok:
            self.lbl_anki_status.setText(
                t("Статус: <span style='color:#4caf50; font-weight:600;'>Подключено (%s)</span>") % msg
            )
        else:
            err_short = msg.split(".")[0] if "." in msg else msg[:50]
            self.lbl_anki_status.setText(
                t("Статус: <span style='color:#e0564b; font-weight:600;'>Ошибка подключения</span> "
                  "<span style='color:#999; font-size:11px;'>(%s)</span>") % err_short
            )

    def _save_groq_key(self):
        key = self.groq_key.text().strip()
        CONFIG.set("groq_api_key", key)
        self._populate_groq_models()

    def _populate_groq_models(self):
        """Наполняет список моделей Groq: Авто + активные модели из API."""
        key = CONFIG.get("groq_api_key", "")
        models = fetch_active_groq_models(key)
        cur = CONFIG.get("groq_model", "auto")

        self.cb_groq_model.blockSignals(True)
        self.cb_groq_model.clear()
        self.cb_groq_model.addItem(t("✨ Автоматически (Новейшая версия)"), "auto")

        for m in models:
            self.cb_groq_model.addItem(m, m)

        idx = self.cb_groq_model.findData(cur)
        if idx >= 0:
            self.cb_groq_model.setCurrentIndex(idx)
        else:
            self.cb_groq_model.setCurrentIndex(0)
            CONFIG.set("groq_model", "auto", save=False)

        self.cb_groq_model.blockSignals(False)

    def _save_gemini_key(self):
        key = self.key_input.text().strip()
        CONFIG.set("gemini_api_key", key)
        self._populate_gemini_models()

    def _populate_gemini_models(self):
        """Наполняет список моделей Gemini: Авто + активные Flash модели из API."""
        key = CONFIG.get("gemini_api_key", "")
        models = fetch_active_gemini_models(key)
        cur = CONFIG.get("gemini_model", "auto")

        self.cb_model.blockSignals(True)
        self.cb_model.clear()
        self.cb_model.addItem(t("✨ Автоматически (Новейшая версия)"), "auto")

        for m in models:
            self.cb_model.addItem(m, m)

        idx = self.cb_model.findData(cur)
        if idx >= 0:
            self.cb_model.setCurrentIndex(idx)
        else:
            self.cb_model.setCurrentIndex(0)
            CONFIG.set("gemini_model", "auto", save=False)

        self.cb_model.blockSignals(False)

    def _populate_groq_models_from_list(self, models: list):
        cur = CONFIG.get("groq_model", "auto")
        self.cb_groq_model.blockSignals(True)
        self.cb_groq_model.clear()
        self.cb_groq_model.addItem(t("✨ Автоматически (Новейшая версия)"), "auto")
        for m in models:
            self.cb_groq_model.addItem(m, m)
        idx = self.cb_groq_model.findData(cur)
        if idx >= 0:
            self.cb_groq_model.setCurrentIndex(idx)
        else:
            self.cb_groq_model.setCurrentIndex(0)
            CONFIG.set("groq_model", "auto", save=False)
        self.cb_groq_model.blockSignals(False)

    def _populate_gemini_models_from_list(self, models: list):
        cur = CONFIG.get("gemini_model", "auto")
        self.cb_model.blockSignals(True)
        self.cb_model.clear()
        self.cb_model.addItem(t("✨ Автоматически (Новейшая версия)"), "auto")
        for m in models:
            self.cb_model.addItem(m, m)
        idx = self.cb_model.findData(cur)
        if idx >= 0:
            self.cb_model.setCurrentIndex(idx)
        else:
            self.cb_model.setCurrentIndex(0)
            CONFIG.set("gemini_model", "auto", save=False)
        self.cb_model.blockSignals(False)

    def _on_groq_check_done(self, is_ok: bool, err_msg: str, models: list):
        self.btn_check_groq.setEnabled(True)
        if is_ok:
            self.btn_check_groq.setText("✓ OK")
            self.btn_check_groq.setStyleSheet("color: #4caf50; font-weight: bold; border: 1px solid #4caf50;")
            self.btn_check_groq.setToolTip(t("Ключ успешно проверен и работает!"))
            if models:
                self._populate_groq_models_from_list(models)
        else:
            self.btn_check_groq.setText(t("✗ Ошибка"))
            self.btn_check_groq.setStyleSheet("color: #e0564b; font-weight: bold; border: 1px solid #e0564b;")
            self.btn_check_groq.setToolTip(f"{t('Ошибка')}: {err_msg}")

    def _on_gemini_check_done(self, is_ok: bool, err_msg: str, models: list):
        self.btn_check_gemini.setEnabled(True)
        if is_ok:
            self.btn_check_gemini.setText("✓ OK")
            self.btn_check_gemini.setStyleSheet("color: #4caf50; font-weight: bold; border: 1px solid #4caf50;")
            self.btn_check_gemini.setToolTip(t("Ключ успешно проверен и работает!"))
            if models:
                self._populate_gemini_models_from_list(models)
        else:
            self.btn_check_gemini.setText(t("✗ Ошибка"))
            self.btn_check_gemini.setStyleSheet("color: #e0564b; font-weight: bold; border: 1px solid #e0564b;")
            self.btn_check_gemini.setToolTip(f"{t('Ошибка')}: {err_msg}")

    def _check_groq_key(self):
        import threading
        key = self.groq_key.text().strip()
        CONFIG.set("groq_api_key", key)
        if not key:
            self.btn_check_groq.setText(t("Ключ пуст"))
            self.btn_check_groq.setStyleSheet("color: #e0564b;")
            return
        self.btn_check_groq.setEnabled(False)
        self.btn_check_groq.setText(t("⏳ Проверка..."))
        self.btn_check_groq.setStyleSheet("")

        def worker():
            is_ok = False
            err_msg = ""
            models = []
            try:
                client = Groq(key, "auto")
                client.check_key()
                is_ok = True
                models = fetch_active_groq_models(key)
            except Exception as e:
                err_msg = str(e)
            self.groq_check_done.emit(is_ok, err_msg, models)

        threading.Thread(target=worker, daemon=True).start()

    def _check_gemini_key(self):
        import threading
        key = self.key_input.text().strip()
        CONFIG.set("gemini_api_key", key)
        if not key:
            self.btn_check_gemini.setText(t("Ключ пуст"))
            self.btn_check_gemini.setStyleSheet("color: #e0564b;")
            return
        self.btn_check_gemini.setEnabled(False)
        self.btn_check_gemini.setText(t("⏳ Проверка..."))
        self.btn_check_gemini.setStyleSheet("")

        def worker():
            is_ok = False
            err_msg = ""
            models = []
            try:
                client = Gemini(key, "auto")
                client.check_key()
                is_ok = True
                models = fetch_active_gemini_models(key)
            except Exception as e:
                err_msg = str(e)
            self.gemini_check_done.emit(is_ok, err_msg, models)

        threading.Thread(target=worker, daemon=True).start()

    def _open_onboarding(self):
        from .onboarding_dialog import OnboardingWizard
        dlg = OnboardingWizard(self.window())
        if dlg.exec():
            # Обновляем поля настроек при возвращении
            self.cb_theme.setCurrentIndex(
                max(0, ["dark", "light", "system"].index(CONFIG.get("ui_theme", "dark")))
            )
            self.cb_uilang.setCurrentIndex(
                0 if CONFIG.get("ui_lang", "en") == "en" else 1
            )
            (self.rb_dict if CONFIG.get("mode") == "dictionary" else self.rb_tr).setChecked(True)
            self.groq_key.setText(CONFIG.get("groq_api_key", ""))
            self.key_input.setText(CONFIG.get("gemini_api_key", ""))
            self.cb_provider.setCurrentIndex(
                max(0, ["groq", "gemini"].index(CONFIG.get("ai_provider", "groq")))
            )
            self._populate_groq_models()
            self._populate_gemini_models()

    def _on_ocr_lang_changed(self):
        CONFIG.set("ocr_lang", self.cb_lang.currentData())
        if hasattr(self, "btn_check_ocr"):
            self.btn_check_ocr.setText(t("Проверить OCR"))
            self.btn_check_ocr.setStyleSheet("")
            self.btn_check_ocr.setToolTip("")

    def _check_ocr_status(self):
        engine_type = CONFIG.get("ocr_engine", "auto")
        lang_code = self.cb_lang.currentData() or "en"
        from ..ocr import check_windows_ocr_language, get_ocr_missing_instructions

        if engine_type == "tesseract":
            import shutil
            has_tess = shutil.which("tesseract") is not None
            if has_tess:
                self.btn_check_ocr.setText("✓ OK")
                self.btn_check_ocr.setStyleSheet("color: #4caf50; font-weight: bold; border: 1px solid #4caf50;")
                self.btn_check_ocr.setToolTip(t("Tesseract найден в системе!"))
            else:
                self.btn_check_ocr.setText(t("✗ Не найден"))
                self.btn_check_ocr.setStyleSheet("color: #e0564b; font-weight: bold; border: 1px solid #e0564b;")
                self.btn_check_ocr.setToolTip(t("Tesseract OCR не найден в PATH."))
            return

        ok, tag, avail = check_windows_ocr_language(lang_code)
        if ok:
            self.btn_check_ocr.setText(f"✓ {t('Установлен')}")
            self.btn_check_ocr.setStyleSheet("color: #4caf50; font-weight: bold; border: 1px solid #4caf50;")
            self.btn_check_ocr.setToolTip(t("Windows OCR для языка «%s» установлен и готов к работе!") % tag)
        else:
            self.btn_check_ocr.setText(f"✗ {t('Не установлен')}")
            self.btn_check_ocr.setStyleSheet("color: #e0564b; font-weight: bold; border: 1px solid #e0564b;")
            msg = get_ocr_missing_instructions(tag, avail)
            self.btn_check_ocr.setToolTip(msg)

            box = QMessageBox(self)
            box.setWindowTitle(t("Проверка Windows OCR"))
            box.setIcon(QMessageBox.Warning)
            box.setText(msg)
            btn_open_win = box.addButton(t("Открыть параметры Windows"), QMessageBox.ActionRole)
            box.addButton(QMessageBox.Close)
            box.exec()
            if box.clickedButton() == btn_open_win:
                if sys.platform == "win32":
                    import os
                    os.system("start ms-settings:regionlanguage")



