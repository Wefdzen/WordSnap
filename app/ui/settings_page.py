"""Вкладка «Настройки»: режим приложения, горячие клавиши, OCR,
взаимодействие с играми, слова, ИИ (Gemini)."""
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
                               QComboBox, QPushButton, QLineEdit,
                               QButtonGroup, QFrame, QKeySequenceEdit)
from PySide6.QtGui import QKeySequence

from ..config import CONFIG, LANGS
from .widgets import ToggleSwitch, SettingRow, flag_icon, FluentRadio
from .theme import TEXT_DIM, ACCENT
from .i18n import t

def section(title: str) -> QLabel:
    l = QLabel(title); l.setObjectName("SectionTitle")
    return l

class SettingsPage(QWidget):
    hotkeys_changed = Signal()
    words_display_changed = Signal()      # изменились настройки отображения списка слов

    def __init__(self, parent=None):
        super().__init__(parent)
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
        for label, val in (("Русский", "ru"), ("English", "en")):
            self.cb_uilang.addItem(label, val)
        self.cb_uilang.setCurrentIndex(0 if CONFIG.get("ui_lang", "ru") == "ru" else 1)
        self.cb_uilang.setFixedWidth(220)
        self.cb_uilang.currentIndexChanged.connect(
            lambda: self._apply_restart("ui_lang", self.cb_uilang.currentData()))
        v.addWidget(SettingRow("languages-world.svg", t("Язык интерфейса"),
                               t("Язык меню и настроек приложения."), self.cb_uilang))

        # ============ Горячие клавиши ============
        v.addWidget(section(t("Горячие клавиши")))
        self.key_edit = QKeySequenceEdit(QKeySequence(CONFIG.get("hotkey").replace("+", "+").title()))
        self.key_edit.setFixedWidth(300)
        self.key_edit.editingFinished.connect(self._save_hotkey)
        v.addWidget(SettingRow("keyboard.svg", t("Горячая клавиша"), right=self.key_edit))

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
        v.addWidget(SettingRow("microchip.svg", "Движок OCR", right=self.cb_ocr))

        self.cb_lang = QComboBox()
        for code, name, fl in LANGS:
            self.cb_lang.addItem(flag_icon(code), f"  {name}", code)
            if code == CONFIG.get("ocr_lang"):
                self.cb_lang.setCurrentIndex(self.cb_lang.count() - 1)
        self.cb_lang.currentIndexChanged.connect(
            lambda: CONFIG.set("ocr_lang", self.cb_lang.currentData()))
        self.cb_lang.setFixedWidth(220)
        v.addWidget(SettingRow("languages-world.svg", t("Язык распознавания"),
                               t("Выберите язык, соответствующий тексту на экране. "
                                 "Иначе распознавание может быть неправильным."), self.cb_lang))

        # ===== Взаимодействие с играми и приложениями =====
        v.addWidget(section(t("Взаимодействие с играми и приложениями")))
        sw1 = ToggleSwitch(CONFIG.get("overlay_active_window"))
        sw1.toggled.connect(lambda on: CONFIG.set("overlay_active_window", on))
        v.addWidget(SettingRow("layers.svg", t("Делать оверлей активным окном  ⓘ"),
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
                                 "Lookupper."), self._window_btn("fullscreenize_window")))

        # ================= Слова =================
        v.addWidget(section(t("Слова")))
        sw3 = ToggleSwitch(CONFIG.get("auto_save_words"))
        sw3.toggled.connect(lambda on: CONFIG.set("auto_save_words", on))
        v.addWidget(SettingRow("disk.svg", t("Автоматически сохранять слова"), right=sw3))
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
        self.groq_key.setFixedWidth(320)
        self.groq_key.editingFinished.connect(
            lambda: CONFIG.set("groq_api_key", self.groq_key.text().strip()))
        gqr.addWidget(self.groq_key)
        gqr.addWidget(self._reveal_btn(self.groq_key))
        v.addWidget(SettingRow("key.svg", t("API-ключ Groq"),
                               t("Бесплатно: console.groq.com/keys"), groq_right))
        self.cb_groq_model = QComboBox()
        for m in ("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"):
            self.cb_groq_model.addItem(m, m)
            if m == CONFIG.get("groq_model"):
                self.cb_groq_model.setCurrentIndex(self.cb_groq_model.count() - 1)
        self.cb_groq_model.currentIndexChanged.connect(
            lambda: CONFIG.set("groq_model", self.cb_groq_model.currentData()))
        self.cb_groq_model.setFixedWidth(260)
        v.addWidget(SettingRow("model-cube.svg", t("Модель Groq"),
                               t("70b — точнее, 8b-instant — быстрее."), self.cb_groq_model))

        # --- Gemini ---
        key_right = QWidget(); kr = QHBoxLayout(key_right); kr.setSpacing(8)
        self.key_input = QLineEdit(CONFIG.get("gemini_api_key"))
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("AIza…")
        self.key_input.setFixedWidth(320)
        self.key_input.editingFinished.connect(
            lambda: CONFIG.set("gemini_api_key", self.key_input.text().strip()))
        kr.addWidget(self.key_input)
        kr.addWidget(self._reveal_btn(self.key_input))
        v.addWidget(SettingRow("key.svg", t("API-ключ Gemini"),
                               t("aistudio.google.com → Get API key."), key_right))
        self.cb_model = QComboBox()
        for m in ("gemini-2.5-flash", "gemini-2.5-flash-lite",
                  "gemini-2.0-flash", "gemini-2.0-flash-lite"):
            self.cb_model.addItem(m, m)
            if m == CONFIG.get("gemini_model"):
                self.cb_model.setCurrentIndex(self.cb_model.count() - 1)
        self.cb_model.currentIndexChanged.connect(
            lambda: CONFIG.set("gemini_model", self.cb_model.currentData()))
        self.cb_model.setFixedWidth(260)
        v.addWidget(SettingRow("model-cube.svg", t("Модель Gemini"), right=self.cb_model))

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
        b = QPushButton(("⏸ " if key == "autopause_window" else "⤢ ") + t("Выбрать окно"))
        def pick():
            from PySide6.QtWidgets import QInputDialog
            txt, ok = QInputDialog.getText(self, t("Выбрать окно"),
                                           t("Часть заголовка окна (пусто — отключить):"),
                                           text=CONFIG.get(key, ""))
            if ok:
                CONFIG.set(key, txt.strip())
        b.clicked.connect(pick)
        return b

    def _save_hotkey(self):
        seq = self.key_edit.keySequence().toString()  # "Alt+Q"
        if seq:
            CONFIG.set("hotkey", seq.lower())
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
                    winreg.SetValueEx(k, "Lookupper", 0, winreg.REG_SZ, exe)
                else:
                    try:
                        winreg.DeleteValue(k, "Lookupper")
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
