import sys
import threading
from PySide6.QtCore import Qt, QTimer, Signal, QUrl
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QStackedWidget, QFileDialog,
    QFrame, QApplication, QMessageBox, QComboBox, QCheckBox
)
from PySide6.QtGui import QCursor, QPalette, QColor, QDesktopServices

from ..config import CONFIG, detect_system_lang
from .theme import resolve, apply_theme_live, apply_native_window_theme, save_window_size, restore_window_size
from .i18n import t
from ..gemini import Groq, Gemini
from ..anki import get_anki_client
from ..dictionaries import DICTIONARIES, dict_key
from .dict_installer import DictionaryInstallDialog

UI_LANGS = [
    ("en", "English", "🇺🇸"),
    ("ru", "Русский", "🇷🇺"),
]


class StepCard(QFrame):
    """Интерактивная карточка для выбора опции с динамическим обновлением темы."""
    clicked = Signal()

    def __init__(self, title: str, desc: str, icon_text: str = "", parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self._selected = False
        self.setObjectName("Card")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)

        if icon_text:
            self.lbl_icon = QLabel(icon_text)
            self.lbl_icon.setStyleSheet("font-size: 26px; min-width: 36px; max-width: 36px; background: transparent;")
            self.lbl_icon.setAlignment(Qt.AlignCenter)
            self.lbl_icon.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            lay.addWidget(self.lbl_icon)

        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("CardTitle")
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: 600; background: transparent;")
        self.lbl_title.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.lbl_desc = QLabel(desc)
        self.lbl_desc.setObjectName("CardDesc")
        self.lbl_desc.setStyleSheet("font-size: 12px; background: transparent;")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        text_box.addWidget(self.lbl_title)
        text_box.addWidget(self.lbl_desc)
        lay.addLayout(text_box, 1)

        self.lbl_check = QLabel("")
        self.lbl_check.setObjectName("CardCheck")
        self.lbl_check.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent;")
        self.lbl_check.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay.addWidget(self.lbl_check)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self._selected = selected
        self.lbl_check.setText("✓" if selected else "")
        self.setObjectName("CardSelected" if selected else "Card")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class OnboardingWizard(QDialog):
    """Мастер первого запуска WordSnap: язык (дропдаун), тема, режим работы, ИИ и словари."""
    ai_check_done = Signal(bool, str)
    anki_check_done = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ai_check_done.connect(self._on_ai_check_done)
        self.anki_check_done.connect(self._on_anki_check_done)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle("WordSnap — " + t("Быстрый старт"))
        self.setMinimumSize(640, 520)
        restore_window_size("onboarding", self, 680, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        apply_native_window_theme(int(self.winId()))

        self._current_theme_name = CONFIG.get("ui_theme", "dark")

        # Главный макет
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(32, 28, 32, 24)
        self.root_layout.setSpacing(18)

        # Верхний заголовок и индикатор шагов
        self._build_header()

        # Страницы шагов
        self.stack = QStackedWidget()
        self._build_step_1_appearance()
        self._build_step_2_mode()
        self._build_step_3_ai()
        self._build_step_4_dicts_anki()
        self._build_step_5_finish()
        self.root_layout.addWidget(self.stack, 1)

        # Нижняя панель навигации
        self._build_footer()
        self._update_nav_buttons()

        # Применяем полную цветовую схему для диалога
        self._apply_dialog_theme(self._current_theme_name)

    # ------------------------------------------------------------- Стилизация диалога
    def _apply_dialog_theme(self, theme_name: str):
        """Мгновенно обновляет оформление диалога под выбранную тему (без глобального лага)."""
        self._current_theme_name = theme_name
        p = resolve(theme_name)

        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(p["BG"]))
        pal.setColor(QPalette.Base, QColor(p["BG"]))
        pal.setColor(QPalette.Text, QColor(p["TEXT"]))
        pal.setColor(QPalette.WindowText, QColor(p["TEXT"]))
        self.setPalette(pal)

        qss = f"""
            QDialog, OnboardingWizard {{
                background-color: {p['BG']};
                color: {p['TEXT']};
            }}
            QLabel {{
                color: {p['TEXT']};
                background: transparent;
            }}
            QLabel#Dim {{
                color: {p['TEXT_DIM']};
                background: transparent;
            }}
            QLabel#H1 {{
                font-size: 20px;
                font-weight: 700;
                color: {p['TEXT']};
                background: transparent;
            }}
            QFrame#Card {{
                background-color: {p['BG_CARD']};
                border: 1px solid {p['BORDER']};
                border-radius: 8px;
            }}
            QFrame#Card:hover {{
                background-color: {p['BG_HOVER']};
                border: 1px solid {p['TEXT_DIM']};
            }}
            QFrame#CardSelected {{
                background-color: {p['BG_HOVER']};
                border: 2px solid {p['ACCENT']};
                border-radius: 8px;
            }}
            QLabel#CardTitle {{
                color: {p['TEXT']};
                font-size: 14px;
                font-weight: 600;
            }}
            QLabel#CardDesc {{
                color: {p['TEXT_DIM']};
                font-size: 12px;
            }}
            QLabel#CardCheck {{
                color: {p['ACCENT']};
                font-size: 16px;
                font-weight: bold;
            }}
            QComboBox {{
                background-color: {p['BG_CARD']};
                color: {p['TEXT']};
                border: 1px solid {p['BORDER']};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
                min-height: 26px;
            }}
            QComboBox:hover {{
                background-color: {p['BG_HOVER']};
                border-color: {p['TEXT_DIM']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {p['BG_CARD']};
                color: {p['TEXT']};
                border: 1px solid {p['BORDER']};
                selection-background-color: {p['BG_HOVER']};
                selection-color: {p['TEXT']};
                padding: 4px;
            }}
            QLineEdit {{
                background-color: {p['BG_CARD']};
                color: {p['TEXT']};
                border: 1px solid {p['BORDER']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {p['ACCENT']};
            }}
            QPushButton {{
                background-color: {p['BG_CARD']};
                color: {p['TEXT']};
                border: 1px solid {p['BORDER']};
                border-radius: 6px;
                padding: 7px 16px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {p['BG_HOVER']};
                border-color: {p['TEXT_DIM']};
            }}
            QPushButton:pressed {{
                background-color: {p['PRESSED']};
            }}
            QPushButton#Accent {{
                background-color: {p['ACCENT']};
                color: {'#ffffff' if p is resolve('light') else '#003a57'};
                border: none;
                font-weight: 600;
                padding: 8px 20px;
            }}
            QPushButton#Accent:hover {{
                background-color: {p['ACCENT_HOVER']};
            }}
            QPushButton#Flat {{
                background: transparent;
                border: none;
                color: {p['TEXT_DIM']};
                padding: 6px 12px;
            }}
            QPushButton#Flat:hover {{
                color: {p['TEXT']};
                background-color: {p['BG_HOVER']};
                border-radius: 4px;
            }}
            QFrame#InnerPanel {{
                background-color: {p['BG_CARD']};
                border: 1px solid {p['BORDER']};
                border-radius: 8px;
                padding: 12px;
            }}
        """
        self.setStyleSheet(qss)

    # ------------------------------------------------------------- Header
    def _build_header(self):
        header_box = QHBoxLayout()
        header_box.setSpacing(12)

        logo_title = QHBoxLayout()
        logo_title.setSpacing(8)
        self.lbl_logo = QLabel("✨")
        self.lbl_logo.setStyleSheet("font-size: 20px; background: transparent;")
        self.lbl_header_title = QLabel("WordSnap")
        self.lbl_header_title.setStyleSheet("font-size: 18px; font-weight: 700; background: transparent;")
        logo_title.addWidget(self.lbl_logo)
        logo_title.addWidget(self.lbl_header_title)
        header_box.addLayout(logo_title)

        header_box.addStretch(1)

        self.lbl_step_indicator = QLabel("1 / 5")
        self.lbl_step_indicator.setObjectName("Dim")
        self.lbl_step_indicator.setStyleSheet("font-size: 13px; font-weight: 600;")
        header_box.addWidget(self.lbl_step_indicator)

        self.root_layout.addLayout(header_box)

    # ------------------------------------------------------------- Шаг 1: Язык (дропдаун) и тема
    def _build_step_1_appearance(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.s1_title = QLabel(t("Добро пожаловать в WordSnap!"))
        self.s1_title.setObjectName("H1")
        lay.addWidget(self.s1_title)

        self.s1_desc = QLabel(t("Выберите язык интерфейса и тему оформления. Изменить их можно в любой момент."))
        self.s1_desc.setObjectName("Dim")
        self.s1_desc.setWordWrap(True)
        lay.addWidget(self.s1_desc)
        lay.addSpacing(6)

        # Выбор языка — ВЫДВИЖНОЙ СПИСОК (Game-style Dropdown)
        self.s1_lbl_lang = QLabel(t("Язык интерфейса:"))
        self.s1_lbl_lang.setStyleSheet("font-size: 13px; font-weight: 600;")
        lay.addWidget(self.s1_lbl_lang)

        self.cb_lang = QComboBox()
        self.cb_lang.setFixedWidth(320)
        self.cb_lang.setCursor(Qt.PointingHandCursor)

        # Заполняем язык: English, Русский (только поддерживаемые языки интерфейса)
        for code, name, fl in UI_LANGS:
            self.cb_lang.addItem(f"{fl}  {name}", code)

        cur_lang = CONFIG.get("ui_lang") or detect_system_lang()
        idx = self.cb_lang.findData(cur_lang)
        if idx >= 0:
            self.cb_lang.setCurrentIndex(idx)
        else:
            self.cb_lang.setCurrentIndex(0)
        self.cb_lang.currentIndexChanged.connect(self._on_lang_combo_changed)
        lay.addWidget(self.cb_lang)
        lay.addSpacing(10)

        # Выбор темы (3 карточки)
        self.s1_lbl_theme = QLabel(t("Тема оформления:"))
        self.s1_lbl_theme.setStyleSheet("font-size: 13px; font-weight: 600;")
        lay.addWidget(self.s1_lbl_theme)

        theme_box = QHBoxLayout()
        theme_box.setSpacing(10)
        self.card_dark = StepCard(t("Тёмная"), t("Стильная тёмная тема"), "🌙")
        self.card_light = StepCard(t("Светлая"), t("Светлая аккуратная тема"), "☀️")
        self.card_system = StepCard(t("Системная"), t("Как в вашей Windows"), "💻")

        cur_theme = CONFIG.get("ui_theme", "dark")
        self.card_dark.set_selected(cur_theme == "dark")
        self.card_light.set_selected(cur_theme == "light")
        self.card_system.set_selected(cur_theme == "system")

        self.card_dark.clicked.connect(lambda: self._select_theme("dark"))
        self.card_light.clicked.connect(lambda: self._select_theme("light"))
        self.card_system.clicked.connect(lambda: self._select_theme("system"))

        theme_box.addWidget(self.card_dark)
        theme_box.addWidget(self.card_light)
        theme_box.addWidget(self.card_system)
        lay.addLayout(theme_box)

        lay.addStretch(1)
        self.stack.addWidget(page)

    def _on_lang_combo_changed(self):
        lang = self.cb_lang.currentData()
        if lang:
            CONFIG.set("ui_lang", lang, save=True)
            self._retranslate_ui()

    def _select_theme(self, theme: str):
        CONFIG.set("ui_theme", theme, save=True)
        self.card_dark.set_selected(theme == "dark")
        self.card_light.set_selected(theme == "light")
        self.card_system.set_selected(theme == "system")

        # Мгновенно обновляем стили диалога (без блокировки UI и лагов)
        self._apply_dialog_theme(theme)

    # ------------------------------------------------------------- Шаг 2: Режим работы
    def _build_step_2_mode(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.s2_title = QLabel(t("Выберите основной режим работы"))
        self.s2_title.setObjectName("H1")
        lay.addWidget(self.s2_title)

        self.s2_desc = QLabel(t("Как вы чаще всего будете использовать приложение? Режим можно менять в один клик."))
        self.s2_desc.setObjectName("Dim")
        self.s2_desc.setWordWrap(True)
        lay.addWidget(self.s2_desc)
        lay.addSpacing(10)

        cur_mode = CONFIG.get("mode", "dictionary")

        self.card_dict_mode = StepCard(
            t("Режим словаря (AI & Изучение языков)"),
            t("Кликните по любому слову на экране в игре, книге или видео — всплывёт окно с транскрипцией, определением, озвучкой и кнопкой сохранения в Anki или личный словарь."),
            "📖"
        )
        self.card_trans_mode = StepCard(
            t("Экранный переводчик (Translator)"),
            t("Мгновенно распознаёт и переводит все строки на экране (диалоги, субтитры, кнопки меню) прямо поверх окна в их исходных позициях."),
            "🌐"
        )

        self.card_dict_mode.set_selected(cur_mode == "dictionary")
        self.card_trans_mode.set_selected(cur_mode == "translator")

        self.card_dict_mode.clicked.connect(lambda: self._select_mode("dictionary"))
        self.card_trans_mode.clicked.connect(lambda: self._select_mode("translator"))

        lay.addWidget(self.card_dict_mode)
        lay.addWidget(self.card_trans_mode)

        self.s2_hint = QLabel(t("💡 Подсказка: в режиме переводчика зажатие Alt переключает на выбор отдельного слова."))
        self.s2_hint.setObjectName("Dim")
        lay.addWidget(self.s2_hint)

        lay.addStretch(1)
        self.stack.addWidget(page)

    def _select_mode(self, mode: str):
        CONFIG.set("mode", mode, save=True)
        self.card_dict_mode.set_selected(mode == "dictionary")
        self.card_trans_mode.set_selected(mode == "translator")
        self._apply_dialog_theme(self._current_theme_name)

    # ------------------------------------------------------------- Шаг 3: ИИ-провайдер
    def _build_step_3_ai(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.s3_title = QLabel(t("Подключение ИИ для умного перевода"))
        self.s3_title.setObjectName("H1")
        lay.addWidget(self.s3_title)

        self.s3_desc = QLabel(t("Нейросеть мгновенно исправляет OCR-опечатки, понимает игровой сленг и даёт живой перевод."))
        self.s3_desc.setObjectName("Dim")
        self.s3_desc.setWordWrap(True)
        lay.addWidget(self.s3_desc)
        lay.addSpacing(6)

        cur_provider = CONFIG.get("ai_provider", "groq")
        prov_box = QHBoxLayout()
        prov_box.setSpacing(10)
        self.card_groq = StepCard(t("Groq (Рекомендуется)"), t("Сверхбыстрый (<1 сек), бесплатный"), "⚡")
        self.card_gemini = StepCard("Google Gemini", t("Высокое качество, бесплатный"), "🌟")

        self.card_groq.set_selected(cur_provider == "groq")
        self.card_gemini.set_selected(cur_provider == "gemini")

        self.card_groq.clicked.connect(lambda: self._select_provider("groq"))
        self.card_gemini.clicked.connect(lambda: self._select_provider("gemini"))

        prov_box.addWidget(self.card_groq)
        prov_box.addWidget(self.card_gemini)
        lay.addLayout(prov_box)
        lay.addSpacing(6)

        # Поле ввода API ключа
        self.s3_lbl_key = QLabel(t("API-ключ:"))
        self.s3_lbl_key.setStyleSheet("font-size: 13px; font-weight: 600;")
        lay.addWidget(self.s3_lbl_key)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.Password)
        self._update_key_input_state()
        self.txt_api_key.textChanged.connect(self._on_key_typed)
        key_row.addWidget(self.txt_api_key, 1)

        self.btn_reveal_key = QPushButton("👁")
        self.btn_reveal_key.setFixedWidth(38)
        self.btn_reveal_key.setCursor(Qt.PointingHandCursor)
        self.btn_reveal_key.clicked.connect(self._toggle_reveal_key)
        key_row.addWidget(self.btn_reveal_key)

        self.btn_check_key = QPushButton(t("Проверить"))
        self.btn_check_key.setCursor(Qt.PointingHandCursor)
        self.btn_check_key.clicked.connect(self._check_ai_key)
        key_row.addWidget(self.btn_check_key)
        lay.addLayout(key_row)

        self.lbl_key_hint = QLabel("")
        self.lbl_key_hint.setObjectName("Dim")
        self.lbl_key_hint.setOpenExternalLinks(True)
        lay.addWidget(self.lbl_key_hint)
        self._update_key_hint()

        lay.addStretch(1)
        self.stack.addWidget(page)

    def _select_provider(self, prov: str):
        CONFIG.set("ai_provider", prov, save=True)
        self.card_groq.set_selected(prov == "groq")
        self.card_gemini.set_selected(prov == "gemini")
        self._update_key_input_state()
        self._update_key_hint()
        self.btn_check_key.setText(t("Проверить"))
        self.btn_check_key.setStyleSheet("")
        self._apply_dialog_theme(self._current_theme_name)

    def _update_key_input_state(self):
        prov = CONFIG.get("ai_provider", "groq")
        if prov == "groq":
            self.txt_api_key.setPlaceholderText("gsk_…")
            self.txt_api_key.setText(CONFIG.get("groq_api_key", ""))
        else:
            self.txt_api_key.setPlaceholderText("AIza…")
            self.txt_api_key.setText(CONFIG.get("gemini_api_key", ""))

    def _update_key_hint(self):
        prov = CONFIG.get("ai_provider", "groq")
        if prov == "groq":
            self.lbl_key_hint.setText(
                t("Бесплатный ключ за 30 сек: <a href='https://console.groq.com/keys' style='color:#60cdff;'>console.groq.com/keys</a> (можно пропустить и ввести позже).")
            )
        else:
            self.lbl_key_hint.setText(
                t("Бесплатный ключ: <a href='https://aistudio.google.com' style='color:#60cdff;'>aistudio.google.com</a> (можно пропустить и ввести позже).")
            )

    def _on_key_typed(self, text: str):
        prov = CONFIG.get("ai_provider", "groq")
        if prov == "groq":
            CONFIG.set("groq_api_key", text.strip(), save=True)
        else:
            CONFIG.set("gemini_api_key", text.strip(), save=True)
        self.btn_check_key.setText(t("Проверить"))
        self.btn_check_key.setStyleSheet("")

    def _toggle_reveal_key(self):
        if self.txt_api_key.echoMode() == QLineEdit.Password:
            self.txt_api_key.setEchoMode(QLineEdit.Normal)
            self.btn_reveal_key.setText("🔒")
        else:
            self.txt_api_key.setEchoMode(QLineEdit.Password)
            self.btn_reveal_key.setText("👁")

    def _check_ai_key(self):
        key = self.txt_api_key.text().strip()
        prov = CONFIG.get("ai_provider", "groq")
        if not key:
            self.btn_check_key.setText(t("Ключ пуст"))
            self.btn_check_key.setStyleSheet("color: #e0564b; font-weight: bold;")
            return

        self.btn_check_key.setEnabled(False)
        self.btn_check_key.setText(t("⏳ Проверка..."))
        self.btn_check_key.setStyleSheet("")

        def worker():
            err_msg = ""
            is_ok = False
            try:
                if prov == "groq":
                    client = Groq(key, "auto")
                else:
                    client = Gemini(key, "auto")
                client.check_key()
                is_ok = True
            except Exception as e:
                err_msg = str(e)
            self.ai_check_done.emit(is_ok, err_msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_check_done(self, is_ok: bool, err_msg: str):
        self.btn_check_key.setEnabled(True)
        if is_ok:
            self.btn_check_key.setText("✓ OK")
            self.btn_check_key.setStyleSheet("color: #4caf50; font-weight: bold; border: 1px solid #4caf50;")
            self.btn_check_key.setToolTip(t("Ключ успешно проверен!"))
        else:
            self.btn_check_key.setText(t("✗ Ошибка"))
            self.btn_check_key.setStyleSheet("color: #e0564b; font-weight: bold; border: 1px solid #e0564b;")
            self.btn_check_key.setToolTip(f"{t('Ошибка')}: {err_msg}")

    # ------------------------------------------------------------- Шаг 4: Словари и Anki
    def _build_step_4_dicts_anki(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.s4_title = QLabel(t("Офлайн-словари и карточки Anki"))
        self.s4_title.setObjectName("H1")
        lay.addWidget(self.s4_title)

        self.s4_desc = QLabel(t("Вы можете добавить свои словари формата Yomitan (.zip) и сохранять карточки в Anki."))
        self.s4_desc.setObjectName("Dim")
        self.s4_desc.setWordWrap(True)
        lay.addWidget(self.s4_desc)
        lay.addSpacing(6)

        # Блок словарей
        dict_card = QFrame()
        dict_card.setObjectName("InnerPanel")
        dc_lay = QVBoxLayout(dict_card)
        dc_lay.setSpacing(8)

        dc_head = QLabel("📚 " + t("Офлайн-словари (мгновенный поиск без интернета)"))
        dc_head.setStyleSheet("font-size: 13px; font-weight: 600;")
        dc_desc = QLabel(t("Поддерживаются любые словари Yomitan/Yomichan в ZIP-архивах (например, wty-en-ru.zip)."))
        dc_desc.setObjectName("Dim")
        dc_desc.setWordWrap(True)

        dict_btns = QHBoxLayout()
        dict_btns.setSpacing(10)
        self.btn_install_dict = QPushButton("📁 " + t("Установить словарь (.zip)"))
        self.btn_install_dict.setCursor(Qt.PointingHandCursor)
        self.btn_install_dict.clicked.connect(self._install_dict_dialog)
        dict_btns.addWidget(self.btn_install_dict)

        self.btn_dl_dicts = QPushButton("🌐 " + t("Скачать словари (Wiktionary)"))
        self.btn_dl_dicts.setCursor(Qt.PointingHandCursor)
        self.btn_dl_dicts.setObjectName("Flat")
        self.btn_dl_dicts.setStyleSheet("color: #60cdff; font-weight: 600; padding: 4px 8px; font-size: 12px;")
        self.btn_dl_dicts.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://yomidevs.github.io/wiktionary-to-yomitan/download/")))
        dict_btns.addWidget(self.btn_dl_dicts)
        dict_btns.addStretch(1)

        dc_lay.addWidget(dc_head)
        dc_lay.addWidget(dc_desc)
        dc_lay.addLayout(dict_btns)
        lay.addWidget(dict_card)
        lay.addSpacing(6)

        # Блок Anki
        anki_card = QFrame()
        anki_card.setObjectName("InnerPanel")
        ac_lay = QVBoxLayout(anki_card)
        ac_lay.setSpacing(8)

        ac_head_row = QHBoxLayout()
        ac_head = QLabel("🎴 " + t("Интеграция с Anki (AnkiConnect)"))
        ac_head.setStyleSheet("font-size: 13px; font-weight: 600;")
        ac_head_row.addWidget(ac_head)
        ac_head_row.addStretch(1)

        self.btn_anki_details = QPushButton("ℹ️ " + t("Подробнее"))
        self.btn_anki_details.setObjectName("Flat")
        self.btn_anki_details.setCursor(Qt.PointingHandCursor)
        self.btn_anki_details.setStyleSheet("color: #60cdff; font-size: 12px; font-weight: 600;")
        self.btn_anki_details.clicked.connect(self._show_anki_guide)
        ac_head_row.addWidget(self.btn_anki_details)

        self.sw_anki = QCheckBox(t("Включить сохранение карточек в Anki"))
        self.sw_anki.setChecked(CONFIG.get("anki_enabled", False))
        self.sw_anki.stateChanged.connect(lambda st: CONFIG.set("anki_enabled", bool(st)))

        self.lbl_anki_status = QLabel(t("⏳ Проверка подключения к AnkiConnect..."))
        self.lbl_anki_status.setObjectName("Dim")
        self.lbl_anki_status.setWordWrap(True)

        ac_lay.addLayout(ac_head_row)
        ac_lay.addWidget(self.sw_anki)
        ac_lay.addWidget(self.lbl_anki_status)
        lay.addWidget(anki_card)

        self._check_anki_async()

        lay.addStretch(1)
        self.stack.addWidget(page)

    def _show_anki_guide(self):
        msg = (
            "<h3>" + t("Как подключить Anki к WordSnap") + "</h3>"
            "<ol style='line-height: 160%; margin-left: -20px;'>"
            "<li>" + t("Запустите приложение <b>Anki</b> на компьютере.") + "</li>"
            "<li>" + t("В верхнем меню Anki выберите <b>Инструменты (Tools) → Дополнения (Add-ons)</b>.") + "</li>"
            "<li>" + t("Нажмите кнопку <b>Загрузить дополнения (Get Add-ons...)</b>.") + "</li>"
            "<li>" + t("В поле «Код» введите <b>2055492159</b> (плагин AnkiConnect) и нажмите <b>ОК</b>.") + "</li>"
            "<li>" + t("<b>Перезапустите Anki</b>, чтобы плагин активировался.") + "</li>"
            "</ol>"
            "<p style='color: #a0a0a0; font-size: 12px; margin-top: 8px;'>" +
            t("После этого включите галочку интеграции, и WordSnap сможет автоматически сохранять карточки слов с переводом, контекстом и скриншотом!") +
            "</p>"
        )
        box = QMessageBox(self)
        box.setWindowTitle(t("Подключение Anki"))
        box.setTextFormat(Qt.RichText)
        box.setText(msg)
        btn_recheck = box.addButton(t("Проверить снова"), QMessageBox.ActionRole)
        box.addButton(t("Понятно"), QMessageBox.AcceptRole)
        box.exec()
        if box.clickedButton() == btn_recheck:
            self.lbl_anki_status.setText(t("⏳ Проверка подключения к AnkiConnect..."))
            self._check_anki_async()

    def _install_dict_dialog(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, t("Выберите файл словаря Yomitan"), "", "ZIP archives (*.zip)"
        )
        if fn:
            dlg = DictionaryInstallDialog(self, fn)
            if dlg.exec() == QDialog.Accepted and dlg.result:
                res = dlg.result
                k = dict_key(res["id"])
                order = list(CONFIG.get("sources_order", []))
                if k not in order:
                    order.append(k)
                    CONFIG.set("sources_order", order)
                en = dict(CONFIG.get("sources_enabled", {}))
                en[k] = True
                CONFIG.set("sources_enabled", en)

                title = res.get("title", res.get("id"))
                QMessageBox.information(
                    self, t("Словарь установлен"),
                    t("Словарь «%s» успешно установлен и активирован!") % title
                )
                self.btn_install_dict.setText(f"✓ {title} " + t("установлен"))
                self.btn_install_dict.setStyleSheet("color: #4caf50; font-weight: bold;")
            elif dlg.error:
                QMessageBox.critical(self, t("Ошибка"), f"{t('Ошибка установки словаря')}: {dlg.error}")

    def _check_anki_async(self):
        def worker():
            ok, msg = False, ""
            try:
                client = get_anki_client(CONFIG)
                ok, msg = client.check_connection(timeout=2.0)
            except Exception as e:
                ok, msg = False, str(e)
            self.anki_check_done.emit(ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_anki_check_done(self, ok: bool, msg: str):
        if ok:
            self.lbl_anki_status.setText(
                "✓ <span style='color:#4caf50; font-weight:600;'>" +
                t("AnkiConnect обнаружен!") + f"</span> ({msg})<br>" +
                t("Зелёный плюсик в окне словаря готов создавать карточки в колоду.")
            )
        else:
            self.lbl_anki_status.setText(
                "<span style='color:#e0564b; font-weight:600;'>" + t("AnkiConnect не обнаружен") + "</span>. " +
                t("Если вы используете Anki, просто включите плагин AnkiConnect (порт 8765). Вы всегда можете настроить его позже.")
            )

    # ------------------------------------------------------------- Шаг 5: Готово
    def _build_step_5_finish(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.s5_title = QLabel("🎉 " + t("Всё готово к работе!"))
        self.s5_title.setObjectName("H1")
        lay.addWidget(self.s5_title)

        self.s5_desc = QLabel(t("Основные настройки завершены. Вот несколько быстрых советов:"))
        self.s5_desc.setObjectName("Dim")
        lay.addWidget(self.s5_desc)
        lay.addSpacing(10)

        hk = CONFIG.get("hotkey", "alt+q").upper()
        tips = [
            ("⌨️", f"<b>{hk}</b> " + t("или средняя кнопка мыши (СКМ):"), t("наведите курсор на слово или текст на экране и нажмите горячую клавишу.")),
            ("🏷️", t("Иконка в трее:"), t("WordSnap работает в фоновом режиме и всегда доступен около часов.")),
            ("⚙️", t("Полная кастомизация:"), t("все настройки (хоткеи, колоды Anki, источники, оверлей) доступны в окне Настроек.")),
        ]

        for icon, title, desc in tips:
            row = QFrame()
            row.setObjectName("InnerPanel")
            rlay = QHBoxLayout(row)
            rlay.setSpacing(12)
            licon = QLabel(icon)
            licon.setStyleSheet("font-size: 22px; background: transparent;")
            rtxt = QVBoxLayout()
            rtxt.setSpacing(2)
            rtitle = QLabel(title)
            rtitle.setStyleSheet("font-size: 13px; font-weight: 600; background: transparent;")
            rdesc = QLabel(desc)
            rdesc.setObjectName("Dim")
            rdesc.setStyleSheet("font-size: 12px; background: transparent;")
            rdesc.setWordWrap(True)
            rtxt.addWidget(rtitle)
            rtxt.addWidget(rdesc)
            rlay.addWidget(licon)
            rlay.addLayout(rtxt, 1)
            lay.addWidget(row)

        lay.addStretch(1)
        self.stack.addWidget(page)

    # ------------------------------------------------------------- Footer & Nav
    def _build_footer(self):
        footer_box = QHBoxLayout()
        footer_box.setSpacing(10)

        self.btn_skip = QPushButton(t("Пропустить шаг"))
        self.btn_skip.setObjectName("Flat")
        self.btn_skip.setCursor(Qt.PointingHandCursor)
        self.btn_skip.clicked.connect(self._go_next)
        footer_box.addWidget(self.btn_skip)

        footer_box.addStretch(1)

        self.btn_back = QPushButton(t("Назад"))
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.clicked.connect(self._go_back)
        footer_box.addWidget(self.btn_back)

        self.btn_next = QPushButton(t("Далее"))
        self.btn_next.setObjectName("Accent")
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.clicked.connect(self._go_next)
        footer_box.addWidget(self.btn_next)

        self.root_layout.addLayout(footer_box)

    def _update_nav_buttons(self):
        idx = self.stack.currentIndex()
        count = self.stack.count()
        self.lbl_step_indicator.setText(f"{idx + 1} / {count}")

        self.btn_back.setVisible(idx > 0)
        if idx == count - 1:
            self.btn_next.setText(t("Начать работу 🚀"))
            self.btn_skip.setVisible(False)
        else:
            self.btn_next.setText(t("Далее"))
            self.btn_skip.setVisible(True)

    def _go_back(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_nav_buttons()

    def _go_next(self):
        idx = self.stack.currentIndex()
        if idx < self.stack.count() - 1:
            self.stack.setCurrentIndex(idx + 1)
            self._update_nav_buttons()
        else:
            self._finish_wizard()

    def _finish_wizard(self):
        CONFIG.set("first_setup_done", True, save=True)
        self.accept()

    def _retranslate_ui(self):
        self.setWindowTitle("WordSnap — " + t("Быстрый старт"))
        self.s1_title.setText(t("Добро пожаловать в WordSnap!"))
        self.s1_desc.setText(t("Выберите язык интерфейса и тему оформления. Изменить их можно в любой момент."))
        self.s1_lbl_lang.setText(t("Язык интерфейса:"))
        self.s1_lbl_theme.setText(t("Тема оформления:"))
        self.card_dark.lbl_title.setText(t("Тёмная"))
        self.card_dark.lbl_desc.setText(t("Стильная тёмная тема"))
        self.card_light.lbl_title.setText(t("Светлая"))
        self.card_light.lbl_desc.setText(t("Светлая аккуратная тема"))
        self.card_system.lbl_title.setText(t("Системная"))
        self.card_system.lbl_desc.setText(t("Как в вашей Windows"))
        self.s2_title.setText(t("Выберите основной режим работы"))
        self.s2_desc.setText(t("Как вы чаще всего будете использовать приложение? Режим можно менять в один клик."))
        self.s2_hint.setText(t("💡 Подсказка: в режиме переводчика зажатие Alt переключает на выбор отдельного слова."))
        self.card_dict_mode.lbl_title.setText(t("Режим словаря (AI & Изучение языков)"))
        self.card_dict_mode.lbl_desc.setText(t("Кликните по любому слову на экране в игре, книге или видео — всплывёт окно с транскрипцией, определением, озвучкой и кнопкой сохранения в Anki или личный словарь."))
        self.card_trans_mode.lbl_title.setText(t("Экранный переводчик (Translator)"))
        self.card_trans_mode.lbl_desc.setText(t("Мгновенно распознаёт и переводит все строки на экране (диалоги, субтитры, кнопки меню) прямо поверх окна в их исходных позициях."))
        self.s3_title.setText(t("Подключение ИИ для умного перевода"))
        self.s3_desc.setText(t("Нейросеть мгновенно исправляет OCR-опечатки, понимает игровой сленг и даёт живой перевод."))
        self.card_groq.lbl_title.setText(t("Groq (Рекомендуется)"))
        self.card_groq.lbl_desc.setText(t("Сверхбыстрый (<1 сек), бесплатный"))
        self.card_gemini.lbl_desc.setText(t("Высокое качество, бесплатный"))
        self.s3_lbl_key.setText(t("API-ключ:"))
        self._update_key_hint()
        self.s4_title.setText(t("Офлайн-словари и карточки Anki"))
        self.s4_desc.setText(t("Вы можете добавить свои словари формата Yomitan (.zip) и сохранять карточки в Anki."))
        self.btn_install_dict.setText("📁 " + t("Установить словарь (.zip)"))
        self.s5_title.setText("🎉 " + t("Всё готово к работе!"))
        self.s5_desc.setText(t("Основные настройки завершены. Вот несколько быстрых советов:"))
        self.btn_skip.setText(t("Пропустить шаг"))
        self.btn_back.setText(t("Назад"))
        self._update_nav_buttons()

    def closeEvent(self, e):
        save_window_size("onboarding", self)
        super().closeEvent(e)
