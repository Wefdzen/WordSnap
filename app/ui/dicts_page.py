"""Вкладка «Переводчик и словари»: список источников слева (с порядком и тумблерами),
настройки выбранного источника справа (включая офлайн-словари Yomitan)."""
import html
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QFrame, QStackedWidget, QComboBox,
                               QPushButton, QFileDialog, QAbstractItemView, QLineEdit,
                               QTextBrowser, QMessageBox, QApplication, QScrollArea)

from ..config import CONFIG, LANGS
from ..dictionaries import DICTIONARIES, dict_key, normalize_key
from .widgets import ToggleSwitch, SettingRow, flag_icon, Badge
from .theme import TEXT_DIM, ACCENT, ROW_HOVER, ROW_SEL, BG_CARD, BORDER, TEXT
from .i18n import t

BUILTIN_SOURCES = {
    "translator_pro": ("Переводчик", "✦",
        "ИИ-переводчик экранного текста. Переводит с учётом контекста, особенностей "
        "запущенного приложения и игрового лора, а также показывает точное значение отдельных слов."),
    "looktionary_pro": ("Словарь (AI)", "✦",
        "ИИ-словарь для изучающих языки. Даёт точное значение слов в контексте с качественной "
        "озвучкой. Предоставляет все данные для сохранения слов: перевод, начальную форму, "
        "транскрипцию, синонимы и другие детали."),
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
    def __init__(self, key: str, name: str, spark: str = "", parent=None):
        super().__init__(parent)
        self.key = key
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 10, 12, 10); lay.setSpacing(10)
        self.bar = QFrame(); self.bar.setFixedSize(3, 20)
        self.bar.setStyleSheet(f"background: {ACCENT}; border-radius: 1px;")
        self.bar.setVisible(False)
        lay.addWidget(self.bar)
        if spark:
            s = QLabel(spark); s.setStyleSheet(f"color: {ACCENT};")
            lay.addWidget(s)
        lbl = QLabel(t(name))
        lbl.setStyleSheet("font-size: 13.5px;")
        lay.addWidget(lbl, 1)

        is_enabled = CONFIG.get("sources_enabled", {}).get(key, True)
        self.sw = ToggleSwitch(is_enabled, with_label=False)
        self.sw.toggled.connect(lambda on: self.toggled.emit(self.key, on))
        lay.addWidget(self.sw)

class DictsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.panels = {}
        self._init_ui()

    def _init_ui(self):
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
        self.list.currentRowChanged.connect(self._on_select)
        self.list.model().rowsMoved.connect(self._order_changed)
        ll.addWidget(self.list, 1)

        b = QPushButton(t("＋  Установить офлайн-словари")); b.setObjectName("Flat")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self._install_dict)
        ll.addWidget(b, 0, Qt.AlignLeft)
        root.addWidget(left, 4)

        # ---------- справа ----------
        right = QFrame()
        rl = QVBoxLayout(right); rl.setContentsMargins(24, 12, 12, 12); rl.setSpacing(12)
        self.stack = QStackedWidget()
        rl.addWidget(self.stack, 1)
        root.addWidget(right, 6)

        self._sync_and_populate()

    def _sync_and_populate(self):
        """Синхронизирует список источников с базой офлайн-словарей и заполняет UI."""
        self.list.blockSignals(True)
        self.list.clear()

        # Очищаем старые панели из стека
        while self.stack.count() > 0:
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.panels.clear()

        # Дополняем sources_order новыми офлайн-словарями
        saved_order = list(CONFIG.get("sources_order", []))
        installed_dicts = {d["id"]: d for d in DICTIONARIES.list_dictionaries()}

        # Проверяем наличие установленных словарей в порядке
        order = []
        for k in saved_order:
            if k in BUILTIN_SOURCES:
                order.append(k)
            else:
                d_id = normalize_key(k)
                if d_id in installed_dicts:
                    order.append(dict_key(d_id))

        # Добавляем в конец те, которых ещё не было в порядке
        for d_id in installed_dicts:
            dk = dict_key(d_id)
            if dk not in order and d_id not in order:
                order.append(dk)

        CONFIG.set("sources_order", order)

        # Синхронизируем sources_enabled
        en = dict(CONFIG.get("sources_enabled", {}))
        for k in order:
            if k not in en:
                d_id = normalize_key(k)
                if d_id in installed_dicts:
                    en[k] = bool(installed_dicts[d_id].get("enabled", 1))
                else:
                    en[k] = True
        CONFIG.set("sources_enabled", en)

        # Добавляем элементы в список и создаем панели
        for key in order:
            info = self._get_source_info(key)
            if not info:
                continue
            name, spark, _ = info
            it = QListWidgetItem()
            it.setData(Qt.UserRole, key)
            it.setSizeHint(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(0, 46))
            self.list.addItem(it)
            row = SourceRow(key, name, spark)
            row.toggled.connect(self._on_toggle)
            self.list.setItemWidget(it, row)

            p = self._build_panel(key)
            self.panels[key] = p
            self.stack.addWidget(p)

        self.list.blockSignals(False)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def _get_source_info(self, key: str) -> tuple[str, str, str] | None:
        if key in BUILTIN_SOURCES:
            return BUILTIN_SOURCES[key]
        d_id = normalize_key(key)
        d = DICTIONARIES.get_dictionary(d_id)
        if d:
            name = d.get("title") or d_id
            desc = d.get("description") or f"Офлайн-словарь Yomitan ({d.get('term_count', 0)} статей)."
            return (name, "📖", desc)
        return None

    def _on_select(self, idx: int):
        if idx < 0 or idx >= self.list.count():
            return
        key = self.list.item(idx).data(Qt.UserRole)
        for i in range(self.list.count()):
            w = self.list.itemWidget(self.list.item(i))
            if w:
                w.bar.setVisible(i == idx)
        if key in self.panels:
            self.stack.setCurrentWidget(self.panels[key])

    def _on_toggle(self, key: str, on: bool):
        en = CONFIG.get("sources_enabled", {})
        en[key] = on
        CONFIG.set("sources_enabled", en)
        if key not in BUILTIN_SOURCES:
            d_id = normalize_key(key)
            DICTIONARIES.toggle_dictionary(d_id, on)

    def _order_changed(self, *_):
        order = [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]
        CONFIG.set("sources_order", order)

    def _install_dict(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, t("Установить офлайн-словарь Yomitan"), "",
            "Yomitan Dictionary (*.zip);;Zip Archives (*.zip);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            res = DICTIONARIES.import_zip(file_path)
            k = dict_key(res["id"])
            order = list(CONFIG.get("sources_order", []))
            if k not in order:
                order.append(k)
                CONFIG.set("sources_order", order)
            en = dict(CONFIG.get("sources_enabled", {}))
            en[k] = True
            CONFIG.set("sources_enabled", en)

            QApplication.restoreOverrideCursor()
            msg = t("Словарь «%s» успешно установлен!\nВсего загружено %s словарных статей.") % (res['title'], f"{res['term_count']:,}")
            QMessageBox.information(self, t("Словарь установлен"), msg)
            self._sync_and_populate()

            # Выбираем добавленный словарь
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole) == k:
                    self.list.setCurrentRow(i)
                    break
        except Exception as ex:
            QApplication.restoreOverrideCursor()
            msg = t("Не удалось импортировать словарь:\n%s") % str(ex)
            QMessageBox.critical(self, t("Ошибка установки словаря"), msg)

    def _delete_dict(self, dict_id: str):
        d = DICTIONARIES.get_dictionary(dict_id)
        name = d.get("title", dict_id) if d else dict_id
        msg = t("Вы уверены, что хотите удалить словарь «%s»?\nВсе словарные статьи будут стёрты.") % name
        rep = QMessageBox.question(
            self, t("Удаление словаря"), msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if rep != QMessageBox.Yes:
            return

        DICTIONARIES.delete_dictionary(dict_id)
        k = dict_key(dict_id)
        order = [x for x in CONFIG.get("sources_order", []) if x != k and x != dict_id]
        CONFIG.set("sources_order", order)
        en = dict(CONFIG.get("sources_enabled", {}))
        en.pop(k, None)
        en.pop(dict_id, None)
        CONFIG.set("sources_enabled", en)

        self._sync_and_populate()

    # ------------------------------------------------------ панели справа
    def _build_panel(self, key: str) -> QWidget:
        if key in BUILTIN_SOURCES:
            return self._build_builtin_panel(key)
        else:
            return self._build_offline_dict_panel(key)

    def _build_builtin_panel(self, key: str) -> QWidget:
        name, spark, desc = BUILTIN_SOURCES[key]
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
        v.addStretch(1)
        return host

    def _build_offline_dict_panel(self, key: str) -> QWidget:
        d_id = normalize_key(key)
        d = DICTIONARIES.get_dictionary(d_id) or {}
        host = QWidget()
        v = QVBoxLayout(host); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(12)

        # Заголовок с бейджами
        h_row = QHBoxLayout(); h_row.setSpacing(8)
        title = QLabel(d.get("title", d_id))
        title.setObjectName("H2")
        h_row.addWidget(title)
        terms = d.get("term_count", 0)
        h_row.addWidget(Badge(f"{terms:,} " + t("статей")))
        rev = d.get("revision")
        if rev:
            h_row.addWidget(Badge(f"v{rev}"))
        h_row.addStretch(1)
        v.addLayout(h_row)

        # Описание
        desc_text = d.get("description") or t("Офлайн-словарь Yomitan.")
        desc = QLabel(desc_text); desc.setWordWrap(True); desc.setStyleSheet("font-size: 13px; color:#c0c0c0;")
        v.addWidget(desc)

        # Автор / Языки
        author = d.get("author")
        if author:
            auth_lbl = QLabel(f"<b>{t('Автор/Источник')}:</b> {html.escape(author)}")
            auth_lbl.setTextFormat(Qt.RichText)
            auth_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
            v.addWidget(auth_lbl)

        # Блок интерактивной проверки словаря
        test_frame = QFrame()
        test_frame.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; padding: 12px;")
        tf_lay = QVBoxLayout(test_frame); tf_lay.setSpacing(8); tf_lay.setContentsMargins(12, 10, 12, 10)

        tf_head = QLabel(t("🔍  Быстрая проверка слова в этом словаре:"))
        tf_head.setStyleSheet("font-weight: 600; font-size: 13px;")
        tf_lay.addWidget(tf_head)

        search_row = QHBoxLayout(); search_row.setSpacing(8)
        inp = QLineEdit()
        inp.setPlaceholderText(t("Например: struggle, hello, house..."))
        inp.setStyleSheet(f"background: #1e1e1e; border: 1px solid {BORDER}; border-radius: 4px; padding: 6px 10px; color: {TEXT};")
        search_row.addWidget(inp, 1)

        btn_find = QPushButton(t("Найти"))
        btn_find.setStyleSheet(f"background: {ACCENT}; color: #000; font-weight: 600; border-radius: 4px; padding: 6px 16px; border: none;")
        btn_find.setCursor(Qt.PointingHandCursor)
        search_row.addWidget(btn_find)
        tf_lay.addLayout(search_row)

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setMinimumHeight(180)
        preview_scroll.setMaximumHeight(360)
        preview_scroll.setStyleSheet(f"background: #181818; border: 1px solid {BORDER}; border-radius: 6px;")

        preview_host = QWidget()
        preview_host.setStyleSheet("background: transparent;")
        preview_lay = QVBoxLayout(preview_host)
        preview_lay.setContentsMargins(12, 10, 12, 10)
        preview_lay.setSpacing(8)

        lbl_placeholder = QLabel(t("Введите слово выше и нажмите «Найти» для проверки статей..."))
        lbl_placeholder.setStyleSheet("color: #777777; font-size: 13px; background: transparent;")
        preview_lay.addWidget(lbl_placeholder)
        preview_lay.addStretch(1)
        preview_scroll.setWidget(preview_host)
        tf_lay.addWidget(preview_scroll)

        def do_test_lookup():
            query = inp.text().strip()
            # Очищаем предыдущее содержимое
            while preview_lay.count():
                it = preview_lay.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()

            if not query:
                lbl = QLabel(t("Введите слово для поиска."))
                lbl.setStyleSheet("color: #777777; font-size: 13px; background: transparent;")
                preview_lay.addWidget(lbl)
                preview_lay.addStretch(1)
                return

            results = DICTIONARIES.lookup(query, d_id)
            if not results:
                not_found = t("Слово «%s» не найдено в этом словаре.") % query
                lbl = QLabel(not_found)
                lbl.setStyleSheet("color: #ff8888; font-size: 13px; background: transparent;")
                lbl.setWordWrap(True)
                preview_lay.addWidget(lbl)
                preview_lay.addStretch(1)
            else:
                from .popup import YomitanSenseWidget
                for idx, entry in enumerate(results, 1):
                    w = YomitanSenseWidget(idx, entry)
                    preview_lay.addWidget(w)
                preview_lay.addStretch(1)

        btn_find.clicked.connect(do_test_lookup)
        inp.returnPressed.connect(do_test_lookup)

        v.addWidget(test_frame)

        # Нижняя панель действий (Удалить словарь)
        act_row = QHBoxLayout()
        btn_del = QPushButton(t("🗑  Удалить этот словарь"))
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #ff6b6b;
                border: 1px solid #772b2b;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background: #441818;
                border-color: #ff4444;
            }
        """)
        btn_del.clicked.connect(lambda: self._delete_dict(d_id))
        act_row.addWidget(btn_del)
        act_row.addStretch(1)
        v.addLayout(act_row)

        v.addStretch(1)
        return host
