"""Диалоговое окно настройки карточек Anki (по аналогии с Yomitan 'Anki Cards').

Позволяет:
- Выбрать колоду (Deck) из существующих в Anki
- Выбрать тип записи / модель (Model)
- Настроить сопоставление полей (Field -> Value) с поддержкой маркеров Yomitan:
  {expression}, {glossary}, {reading}, {sentence}, {audio}, {screenshot} и других
- Сохранить настройки в конфигурации
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QComboBox, QPushButton, QFrame, QScrollArea,
                               QWidget, QGridLayout, QMessageBox, QApplication)

from ..config import CONFIG
from ..anki import get_anki_client, ANKI_MARKERS
from .theme import BG, BG_CARD, BG_PANEL, BG_HOVER, BORDER, ACCENT, TEXT, TEXT_DIM, apply_native_window_theme, save_window_size, restore_window_size
from .widgets import Hairline, svg_icon
from .i18n import t

def get_yomitan_value_options() -> list[str]:
    """Возвращает список маркеров с учётом установленных офлайн-словарей."""
    from ..dictionaries import DICTIONARIES
    options = [
        "{expression}",
        "{reading}",
        "{phonetic-transcriptions}",
        "{glossary}",
        "{glossary-offline}",
        "{glossary-ai}",
        "{dictionary}",
        "{glossary-brief}",
        "{glossary-first}",
        "{definition}",
        "{word-translation}",
        "{sentence}",
        "{sentence-plain}",
        "{sentence-translation}",
        "{audio}",
        "{screenshot}",
        "{part-of-speech}",
        "{frequencies}",
        "{synonyms}",
        "{document-title}",
        "{source-app}",
        "{clipboard-text}",
        "{tags}",
        "{date}",
    ]
    try:
        for d in DICTIONARIES.list_dictionaries():
            d_id = d["id"]
            tok = f"{{single-glossary-{d_id}}}"
            if tok not in options:
                options.append(tok)
    except Exception:
        pass
    options.append(t("(пусто)"))
    return options

class AnkiCardsDialog(QDialog):
    settings_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Настройка карточек Anki"))
        self.setMinimumSize(700, 640)
        restore_window_size("anki_cards", self, 740, 750)
        apply_native_window_theme(int(self.winId()))
        self.setStyleSheet(f"""
            QDialog {{ background: {BG}; }}
            QLabel {{ color: {TEXT}; font-family: 'Segoe UI', sans-serif; }}
            QComboBox {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 6px 12px;
                color: {TEXT};
                min-height: 28px;
            }}
            QComboBox:hover {{ background: {BG_HOVER}; }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox QAbstractItemView {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                selection-background-color: {BG_HOVER};
                selection-color: {TEXT};
                outline: none;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 28px;
                padding: 4px 8px;
                color: {TEXT};
            }}
            QPushButton#PrimaryBtn {{
                background: {ACCENT};
                color: #000000;
                font-weight: 600;
                border-radius: 4px;
                padding: 8px 20px;
                border: none;
            }}
            QPushButton#PrimaryBtn:hover {{
                background: #79d6ff;
            }}
            QPushButton#SecondaryBtn {{
                background: {BG_CARD};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 8px 18px;
            }}
            QPushButton#SecondaryBtn:hover {{
                background: {BG_HOVER};
            }}
        """)

        self.client = get_anki_client()
        self.field_combos: dict[str, QComboBox] = {}
        self._current_model = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        # Заголовок
        h_row = QHBoxLayout()
        title = QLabel(t("Anki Cards"))
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        h_row.addWidget(title)
        h_row.addStretch(1)
        root.addLayout(h_row)

        # Вкладки (как в Yomitan: вкладка Expression с активной линией)
        tab_row = QHBoxLayout(); tab_row.setSpacing(16)
        tab_expr = QPushButton(t("Expression"))
        tab_expr.setCursor(Qt.PointingHandCursor)
        tab_expr.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {TEXT};
                font-size: 14px;
                font-weight: 600;
                padding: 4px 6px;
            }}
        """)
        tab_row.addWidget(tab_expr)
        tab_row.addStretch(1)
        root.addLayout(tab_row)

        # Активная подчеркивающая линия под вкладкой
        tab_line = QFrame()
        tab_line.setFixedHeight(2)
        tab_line.setStyleSheet(f"background: {ACCENT};")
        tab_line.setFixedWidth(80)
        root.addWidget(tab_line)

        # Баннер ошибки подключения (скрыт по умолчанию)
        self.err_banner = QFrame()
        self.err_banner.setStyleSheet("background: #442020; border: 1px solid #883333; border-radius: 6px; padding: 10px;")
        eb_lay = QHBoxLayout(self.err_banner)
        self.err_label = QLabel(t("Не удалось связаться с AnkiConnect."))
        self.err_label.setStyleSheet("color: #ff9999;")
        eb_lay.addWidget(self.err_label, 1)
        btn_retry = QPushButton(t("Повторить"))
        btn_retry.setObjectName("SecondaryBtn")
        btn_retry.clicked.connect(self.reload_data)
        eb_lay.addWidget(btn_retry)
        self.err_banner.setVisible(False)
        root.addWidget(self.err_banner)

        # Выбор Deck и Model
        sel_frame = QFrame()
        sel_frame.setStyleSheet(f"background: {BG_CARD}; border-radius: 6px; padding: 12px;")
        sel_grid = QGridLayout(sel_frame)
        sel_grid.setContentsMargins(14, 10, 14, 10)
        sel_grid.setSpacing(12)

        lbl_deck = QLabel(t("Deck"))
        lbl_deck.setStyleSheet("font-weight: 600; font-size: 13.5px;")
        sel_grid.addWidget(lbl_deck, 0, 0)
        self.cb_deck = QComboBox()
        self.cb_deck.setMinimumWidth(320)
        self.cb_deck.currentIndexChanged.connect(self._on_deck_changed)
        sel_grid.addWidget(self.cb_deck, 0, 1)

        lbl_model = QLabel(t("Model"))
        lbl_model.setStyleSheet("font-weight: 600; font-size: 13.5px;")
        sel_grid.addWidget(lbl_model, 1, 0)
        self.cb_model = QComboBox()
        self.cb_model.setMinimumWidth(320)
        self.cb_model.currentIndexChanged.connect(self._on_model_changed)
        sel_grid.addWidget(self.cb_model, 1, 1)

        root.addWidget(sel_frame)

        # Разделитель
        root.addWidget(Hairline(color=BORDER))

        # Заголовок таблицы Field | Value
        tbl_head = QHBoxLayout()
        tbl_head.setContentsMargins(12, 4, 12, 4)
        lbl_f = QLabel(t("Field"))
        lbl_f.setStyleSheet(f"font-weight: 700; color: {TEXT_DIM}; font-size: 12px; text-transform: uppercase;")
        lbl_f.setFixedWidth(160)
        tbl_head.addWidget(lbl_f)
        lbl_v = QLabel(t("Value"))
        lbl_v.setStyleSheet(f"font-weight: 700; color: {TEXT_DIM}; font-size: 12px; text-transform: uppercase;")
        tbl_head.addWidget(lbl_v, 1)
        root.addLayout(tbl_head)

        # Область прокрутки полей модели
        self.fields_area = QScrollArea()
        self.fields_area.setWidgetResizable(True)
        self.fields_area.setFrameShape(QFrame.NoFrame)
        self.fields_area.setStyleSheet("background: transparent; border: none;")

        self.fields_host = QWidget()
        self.fields_host.setStyleSheet("background: transparent;")
        self.fields_lay = QVBoxLayout(self.fields_host)
        self.fields_lay.setContentsMargins(0, 0, 0, 0)
        self.fields_lay.setSpacing(10)
        self.fields_lay.addStretch(1)

        self.fields_area.setWidget(self.fields_host)
        root.addWidget(self.fields_area, 1)

        # Подсказка по маркерам
        hint_lbl = QLabel(t(
            "💡 Маркер {glossary} автоматически форматирует статьи офлайн-словарей "
            "(как в Yomitan) или ИИ. Также можно использовать {glossary-offline}, {glossary-ai} "
            "или конкретный словарь {single-glossary-...}."
        ))
        hint_lbl.setStyleSheet("color: #888888; font-size: 11.5px; padding: 2px 4px;")
        hint_lbl.setWordWrap(True)
        root.addWidget(hint_lbl)

        # Нижняя панель действий
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        btn_test = QPushButton(t("Тестовая карточка"))
        btn_test.setObjectName("SecondaryBtn")
        btn_test.setToolTip(t("Создать проверочную карточку со словом 'test' в Anki"))
        btn_test.clicked.connect(self._test_card)
        bottom_bar.addWidget(btn_test)

        bottom_bar.addStretch(1)

        btn_close = QPushButton(t("Отмена"))
        btn_close.setObjectName("SecondaryBtn")
        btn_close.clicked.connect(self.reject)
        bottom_bar.addWidget(btn_close)

        btn_save = QPushButton(t("Сохранить"))
        btn_save.setObjectName("PrimaryBtn")
        btn_save.clicked.connect(self._save_and_accept)
        bottom_bar.addWidget(btn_save)

        root.addLayout(bottom_bar)

        self.reload_data()

    def closeEvent(self, e):
        save_window_size("anki_cards", self)
        super().closeEvent(e)

    def reload_data(self):
        """Загружает список колод и моделей из AnkiConnect."""
        ok, msg = self.client.check_connection()
        if not ok:
            self.err_banner.setVisible(True)
            self.err_label.setText(f"{t('AnkiConnect недоступен')}: {msg}")
            return

        self.err_banner.setVisible(False)
        decks = self.client.get_decks()
        models = self.client.get_models()

        cur_deck = CONFIG.get("anki_deck", "")
        cur_model = CONFIG.get("anki_model", "")

        self.cb_deck.blockSignals(True)
        self.cb_deck.clear()
        for d in decks:
            self.cb_deck.addItem(d, d)
        idx_d = self.cb_deck.findData(cur_deck)
        if idx_d >= 0:
            self.cb_deck.setCurrentIndex(idx_d)
        elif self.cb_deck.count() > 0:
            self.cb_deck.setCurrentIndex(0)
            CONFIG.set("anki_deck", self.cb_deck.currentData(), save=False)
        self.cb_deck.blockSignals(False)

        self.cb_model.blockSignals(True)
        self.cb_model.clear()
        for m in models:
            self.cb_model.addItem(m, m)
        idx_m = self.cb_model.findData(cur_model)
        if idx_m >= 0:
            self.cb_model.setCurrentIndex(idx_m)
        elif self.cb_model.count() > 0:
            self.cb_model.setCurrentIndex(0)
            CONFIG.set("anki_model", self.cb_model.currentData(), save=False)
        self.cb_model.blockSignals(False)

        self._render_fields_for_model(self.cb_model.currentData() or "")

    def _on_deck_changed(self):
        d = self.cb_deck.currentData()
        if d:
            CONFIG.set("anki_deck", d, save=False)

    def _on_model_changed(self):
        m = self.cb_model.currentData()
        if m:
            CONFIG.set("anki_model", m, save=False)
            self._render_fields_for_model(m)

    def _render_fields_for_model(self, model_name: str):
        """Очищает и наполняет таблицу Field | Value для выбранной модели."""
        self._current_model = model_name
        self.field_combos.clear()

        # Очистка
        while self.fields_lay.count() > 1:
            item = self.fields_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not model_name:
            return

        fields = self.client.get_model_fields(model_name)
        saved_all = CONFIG.get("anki_fields", {})
        saved_model = saved_all.get(model_name, {})

        for f in fields:
            row_frame = QFrame()
            row_frame.setStyleSheet(f"background: {BG_CARD}; border-radius: 5px; padding: 6px 12px;")
            rh = QHBoxLayout(row_frame)
            rh.setContentsMargins(10, 6, 10, 6)
            rh.setSpacing(14)

            name_lbl = QLabel(f)
            name_lbl.setStyleSheet("font-weight: 600; font-size: 13.5px;")
            name_lbl.setFixedWidth(150)
            rh.addWidget(name_lbl)

            cb = QComboBox()
            cb.setEditable(True)
            cb.setInsertPolicy(QComboBox.NoInsert)
            for opt in get_yomitan_value_options():
                cb.addItem(opt)

            # Определяем начальное значение
            val = saved_model.get(f)
            if val is None:
                fl = f.lower()
                if "front" in fl or "word" in fl or "expression" in fl or "термин" in fl:
                    val = "{expression}"
                elif "back" in fl or "glossary" in fl or "перевод" in fl or "значение" in fl:
                    val = "{glossary}"
                elif "reading" in fl or "transcription" in fl or "чтение" in fl:
                    val = "{reading}"
                elif "sentence" in fl or "context" in fl or "пример" in fl:
                    val = "{sentence}"
                elif "image" in fl or "picture" in fl or "screenshot" in fl or "картинка" in fl:
                    val = "{screenshot}"
                elif "audio" in fl or "sound" in fl or "звук" in fl:
                    val = "{audio}"
                else:
                    val = ""

            idx = cb.findText(val)
            if idx >= 0:
                cb.setCurrentIndex(idx)
            else:
                cb.setEditText(val)

            self.field_combos[f] = cb
            rh.addWidget(cb, 1)

            self.fields_lay.insertWidget(self.fields_lay.count() - 1, row_frame)

    def _save_and_accept(self):
        """Сохраняет сопоставление полей, выбранную колоду и модель."""
        deck = self.cb_deck.currentData()
        model = self.cb_model.currentData()
        if deck:
            CONFIG.set("anki_deck", deck, save=False)
        if model:
            CONFIG.set("anki_model", model, save=False)

        if model and self.field_combos:
            all_fields = CONFIG.get("anki_fields", {})
            curr_map = {}
            for f_name, cb in self.field_combos.items():
                txt = cb.currentText().strip()
                if txt in ("(пусто)", "(none)", t("(пусто)")):
                    txt = ""
                curr_map[f_name] = txt
            all_fields[model] = curr_map
            CONFIG.set("anki_fields", all_fields, save=False)

        CONFIG.save()
        self.settings_saved.emit()
        self.accept()

    def _test_card(self):
        """Создает тестовую карточку для проверки текущих настроек."""
        test_entry = {
            "dict_form": "test",
            "word_in_text": "testing",
            "src_lang": "en",
            "transcription": "/test/",
            "definition": "A procedure intended to establish the quality, performance, or reliability of something.",
            "word_translation": "тест, проверка",
            "pos_tags": ["Noun", "Verb"],
            "level": "A1",
            "synonyms": ["trial", "experiment"],
            "context": "This is a simple test sentence for Anki verification.",
            "context_translation": "Это простое тестовое предложение для проверки Anki.",
            "source_title": "WordSnap Test",
            "source_app": "WordSnap.exe",
        }

        # Текущие настройки из диалога
        deck = self.cb_deck.currentData()
        model = self.cb_model.currentData()
        field_map = {}
        for f_name, cb in self.field_combos.items():
            t_val = cb.currentText().strip()
            if t_val in ("(пусто)", "(none)", t("(пусто)")):
                t_val = ""
            field_map[f_name] = t_val

        try:
            note_id = self.client.add_word_note(test_entry, deck=deck, model=model,
                                                field_mappings=field_map, tags=["wordsnap-test"])
            msg = (t("Тестовая карточка успешно создана в Anki!") +
                   f"\nID: {note_id}\n{t('Колода')}: {deck}\n{t('Модель')}: {model}")
            QMessageBox.information(self, t("Успех"), msg)
        except Exception as e:
            QMessageBox.warning(self, t("Ошибка"), f"{t('Не удалось создать карточку')}:\n{e}")
