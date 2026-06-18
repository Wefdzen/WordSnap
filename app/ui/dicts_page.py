"""Вкладка «Переводчик и словари»: список источников слева (с порядком и тумблерами),
настройки выбранного источника справа."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QFrame, QStackedWidget, QComboBox,
                               QPushButton, QFileDialog, QAbstractItemView)

from ..config import CONFIG, LANGS
from .widgets import ToggleSwitch, SettingRow, flag_icon
from .theme import TEXT_DIM, ACCENT, ROW_HOVER, ROW_SEL
from .i18n import t

SOURCES = {
    "translator_pro": ("Переводчик", "✦",
        "ИИ-переводчик экранного текста. Переводит с учётом контекста, особенностей "
        "запущенного приложения и игрового лора, а также показывает точное значение отдельных слов."),
    "looktionary_pro": ("Looktionary", "✦",
        "ИИ-словарь для изучающих языки. Даёт точное значение слов в контексте с качественной "
        "озвучкой. Предоставляет все данные для сохранения слов: перевод, начальную форму, "
        "транскрипцию, синонимы и другие детали."),
    "oxford": ("Oxford (Английский → Русский)", "",
        "Офлайн-словарь. Базовые определения и переводы без подключения к интернету."),
}

def lang_combo(current: str) -> QComboBox:
    cb = QComboBox()
    for code, name, fl in LANGS:
        cb.addItem(flag_icon(code), f"  {name}", code)
        if code == current:
            cb.setCurrentIndex(cb.count() - 1)
    return cb

class SourceRow(QWidget):
    toggled = Signal(str, bool)
    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self.key = key
        name, spark, _ = SOURCES[key]
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 10, 12, 10); lay.setSpacing(10)
        self.bar = QFrame(); self.bar.setFixedSize(3, 20)
        self.bar.setStyleSheet(f"background: {ACCENT}; border-radius: 1px;")
        self.bar.setVisible(False)
        lay.addWidget(self.bar)
        if spark:
            s = QLabel(spark); s.setStyleSheet(f"color: {ACCENT};")
            lay.addWidget(s)
        lay.addWidget(QLabel(t(name)), 1)
        self.sw = ToggleSwitch(CONFIG.get("sources_enabled").get(key, True), with_label=False)
        self.sw.toggled.connect(lambda on: self.toggled.emit(self.key, on))
        lay.addWidget(self.sw)

class DictsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QHBoxLayout(self); root.setContentsMargins(20, 8, 20, 16); root.setSpacing(2)

        # ---------- слева ----------
        left = QFrame(); left.setObjectName("Panel")
        ll = QVBoxLayout(left); ll.setContentsMargins(10, 12, 10, 12); ll.setSpacing(8)
        hint = QLabel(t("✥  Перетащите, чтобы изменить порядок отображения в режиме словаря"))
        hint.setObjectName("Dim")
        ll.addWidget(hint)
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setStyleSheet(f"""
            QListWidget::item {{ background: transparent; border-radius: 6px; margin: 2px 0; }}
            QListWidget::item:hover {{ background: {ROW_HOVER}; }}
            QListWidget::item:selected {{ background: {ROW_SEL}; }}
        """)
        for key in CONFIG.get("sources_order"):
            self._add_item(key)
        self.list.currentRowChanged.connect(self._on_select)
        self.list.model().rowsMoved.connect(self._order_changed)
        ll.addWidget(self.list, 1)
        b = QPushButton(t("＋  Установить офлайн-словари")); b.setObjectName("Flat")
        b.clicked.connect(self._install_dict)
        ll.addWidget(b, 0, Qt.AlignLeft)
        root.addWidget(left, 4)

        # ---------- справа ----------
        right = QFrame()
        rl = QVBoxLayout(right); rl.setContentsMargins(24, 12, 12, 12); rl.setSpacing(12)
        self.stack = QStackedWidget()
        self.panels = {}
        for key in SOURCES:
            p = self._build_panel(key)
            self.panels[key] = p
            self.stack.addWidget(p)
        rl.addWidget(self.stack); rl.addStretch(1)
        root.addWidget(right, 6)

        self.list.setCurrentRow(0)

    def _add_item(self, key):
        it = QListWidgetItem()
        it.setData(Qt.UserRole, key)
        it.setSizeHint(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(0, 46))
        self.list.addItem(it)
        row = SourceRow(key)
        row.toggled.connect(self._on_toggle)
        self.list.setItemWidget(it, row)

    def _on_select(self, idx: int):
        if idx < 0:
            return
        key = self.list.item(idx).data(Qt.UserRole)
        for i in range(self.list.count()):
            w = self.list.itemWidget(self.list.item(i))
            if w:
                w.bar.setVisible(i == idx)
        self.stack.setCurrentWidget(self.panels[key])

    def _on_toggle(self, key: str, on: bool):
        en = CONFIG.get("sources_enabled"); en[key] = on
        CONFIG.set("sources_enabled", en)

    def _order_changed(self, *_):
        order = [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]
        CONFIG.set("sources_order", order)

    def _install_dict(self):
        QFileDialog.getOpenFileName(self, t("Установить офлайн-словарь"), "",
                                    "Dictionaries (*.dsl *.zip *.ifo *.json)")

    # ------------------------------------------------------ панели справа
    def _build_panel(self, key: str) -> QWidget:
        name, spark, desc = SOURCES[key]
        host = QWidget()
        v = QVBoxLayout(host); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(14)
        title = QLabel(f"{t(name)}  <span style='color:{ACCENT}'>{spark}</span>")
        title.setObjectName("H2"); title.setTextFormat(Qt.RichText)
        v.addWidget(title)
        d = QLabel(t(desc)); d.setWordWrap(True); d.setStyleSheet("font-size: 13px;")
        v.addWidget(d)

        tp = CONFIG.get("translator_pro"); lk = CONFIG.get("looktionary_pro")
        if key == "translator_pro":
            cb = lang_combo(tp["target_lang"])
            cb.currentIndexChanged.connect(lambda: (tp.__setitem__("target_lang", cb.currentData()),
                                                    CONFIG.set("translator_pro", tp)))
            v.addWidget(SettingRow("globe.svg", t("Язык перевода"),
                                   t("На какой язык переводить распознанный на экране текст."), cb))
            sw = ToggleSwitch(tp["hide_in_dict_mode"])
            sw.toggled.connect(lambda on: (tp.__setitem__("hide_in_dict_mode", on),
                                           CONFIG.set("translator_pro", tp)))
            v.addWidget(SettingRow("🙈", t("Скрыть перевод в режиме словаря"),
                                   t("Перевод будет скрыт под спойлером."), sw))
        elif key == "looktionary_pro":
            cb1 = lang_combo(lk["def_lang"])
            cb1.currentIndexChanged.connect(lambda: (lk.__setitem__("def_lang", cb1.currentData()),
                                                     CONFIG.set("looktionary_pro", lk)))
            v.addWidget(SettingRow("globe.svg", t("Язык определения"),
                                   t("На каком языке показывать определение слова."), cb1))
            cb2 = lang_combo(lk["word_trans_lang"])
            cb2.currentIndexChanged.connect(lambda: (lk.__setitem__("word_trans_lang", cb2.currentData()),
                                                     CONFIG.set("looktionary_pro", lk)))
            v.addWidget(SettingRow("globe.svg", t("Язык перевода слова"),
                                   t("На какой язык переводить само слово."), cb2))
            sw = ToggleSwitch(lk["hide_word_translation"])
            sw.toggled.connect(lambda on: (lk.__setitem__("hide_word_translation", on),
                                           CONFIG.set("looktionary_pro", lk)))
            v.addWidget(SettingRow("🙈", t("Скрыть перевод слова"),
                                   t("Перевод будет скрыт под спойлером."), sw))
        else:
            info = QLabel(t("Слот офлайн-словаря. Используется свободный словарь "
                            "(dictionaryapi.dev) для английских слов; собственные офлайн-словари "
                            "можно подключить кнопкой слева."))
            info.setObjectName("Dim"); info.setWordWrap(True)
            v.addWidget(info)
        v.addStretch(1)
        return host
