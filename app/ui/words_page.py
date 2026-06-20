"""Вкладка «Слова»: личный словарь — список слева, карточка слова справа
(режим просмотра / режим редактирования)."""
import datetime
import html
import time

from PySide6.QtCore import Qt, Signal, QSize, QUrl, QEvent
from PySide6.QtGui import QPixmap, QPainter, QColor, QDesktopServices
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
                               QPushButton, QListWidget, QListWidgetItem, QScrollArea,
                               QFrame, QComboBox, QSplitter, QSplitterHandle, QTextEdit,
                               QFileDialog, QMessageBox, QGridLayout, QSizePolicy,
                               QDialog, QDialogButtonBox)

from ..config import CONFIG, flag_for, lang_name, LANGS
from ..storage import WORDS
from .. import tts
from .widgets import Badge, Hairline, InfoBanner, Collapsible, flag_label, flag_icon, svg_icon
from .theme import TEXT_DIM, ACCENT, BORDER, BG_CARD, ROW_HOVER, ROW_SEL, ICON
from .i18n import t

CEFR = ["A1", "A2", "B1", "B2", "C1", "C2"]

def _cefr_rank(e: dict) -> int:
    lv = (e.get("level") or "").upper()
    return CEFR.index(lv) if lv in CEFR else len(CEFR)

NEW_DAYS = 7  # «Новые» — добавленные за последние N дней

def _day_label(ts: float) -> str:
    d = datetime.date.fromtimestamp(ts)
    today = datetime.date.today()
    if d == today:
        return t("Сегодня")
    if d == today - datetime.timedelta(days=1):
        return t("Вчера")
    return d.strftime("%d.%m.%Y")

# известные браузеры: имя процесса -> красивое имя (в фильтре показываем именно
# его, а не заголовок вкладки — иначе там было бы название каждого видео/страницы)
_BROWSERS = {
    "chrome": "Google Chrome", "msedge": "Microsoft Edge", "edge": "Microsoft Edge",
    "firefox": "Mozilla Firefox", "librewolf": "LibreWolf", "waterfox": "Waterfox",
    "brave": "Brave", "opera": "Opera", "opera_gx": "Opera GX", "operagx": "Opera GX",
    "vivaldi": "Vivaldi", "zen": "Zen Browser", "arc": "Arc", "tor": "Tor Browser",
    "browser": "Yandex Browser", "yandex": "Yandex Browser", "iexplore": "Internet Explorer",
}

def _app_base(e: dict) -> str:
    """Имя процесса без пути и .exe (например 'zen')."""
    s = (e.get("source_app") or "").rsplit("\\", 1)[-1]
    if s.lower().endswith(".exe"):
        s = s[:-4]
    return s

def _browser_name(e: dict) -> str:
    """Если источник — браузер, вернуть его имя (без названия страницы/видео)."""
    base = _app_base(e).lower()
    if base in _BROWSERS:
        return _BROWSERS[base]
    # запасной разбор по заголовку окна вида «… — Zen Browser»
    title = e.get("source_title") or ""
    for sep in (" — ", " – ", " - "):
        if sep in title:
            tail = title.rsplit(sep, 1)[-1].strip().lower()
            for key, name in _BROWSERS.items():
                if key in tail or tail in name.lower():
                    return name
    return ""

def _src_key(e: dict) -> str:
    """Ключ источника слова, по которому фильтруем и группируем.
    Браузеры → имя браузера (стабильно, без названия вкладки);
    игры/приложения → полный заголовок окна (например «ELDEN RING»)."""
    b = _browser_name(e)
    if b:
        return b
    return (e.get("source_title") or e.get("source_app") or "").strip()

def _pretty_src(s: str) -> str:
    """Красивое имя источника: убираем путь и расширение .exe (если это имя
    процесса), полное название игры/браузера оставляем как есть."""
    s = s.rsplit("\\", 1)[-1]
    if s.lower().endswith(".exe"):
        s = s[:-4]
    return s or t("Без источника")

class GripHandle(QSplitterHandle):
    """Разделитель с маленькой «палочкой» посередине — подсказывает,
    что границу можно тянуть влево/вправо (как в оригинале)."""
    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BORDER).lighter(160))
        w, h = 4, 28
        x = (self.width() - w) // 2
        y = (self.height() - h) // 2
        p.drawRoundedRect(x, y, w, h, 2, 2)

class GripSplitter(QSplitter):
    def createHandle(self):
        return GripHandle(self.orientation(), self)

class ScalableImage(QLabel):
    """Скриншот, который подстраивает размер под ширину панели (и не выше max_h),
    сохраняя пропорции. Высоту считает сам движок раскладки через heightForWidth —
    поэтому ничего не дёргается, не вылезает за панель и не прячется при ресайзе."""
    def __init__(self, pixmap: QPixmap, max_h: int = 460, path: str = "", parent=None):
        super().__init__(parent)
        self._orig = pixmap
        self._max_h = max_h
        self._path = path                       # путь к файлу — открыть по клику
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(1, 1)
        if path:
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip(t("Открыть скриншот"))
        sp = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def mousePressEvent(self, e):
        # клик по скриншоту — открыть его в системном просмотрщике (как в Windows)
        if self._path and e.button() == Qt.LeftButton:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._path))
        super().mousePressEvent(e)

    def _h_for_w(self, w: int) -> int:
        if self._orig.isNull() or self._orig.width() == 0:
            return 0
        return min(self._max_h, round(w * self._orig.height() / self._orig.width()))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w: int) -> int:
        return self._h_for_w(max(1, w))

    def sizeHint(self):
        w = self.width() if self.width() > 1 else min(self._orig.width(), self._max_h * 2)
        return QSize(w, self._h_for_w(w))

    def minimumSizeHint(self):
        return QSize(1, 1)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._orig.isNull():
            return
        h = self._h_for_w(self.width())
        super().setPixmap(self._orig.scaled(self.width(), h,
                                            Qt.KeepAspectRatio, Qt.SmoothTransformation))

class WordRow(QFrame):
    clicked = Signal(str, bool)  # (entry_id, ctrl_held)
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry_id = entry["id"]
        self.setObjectName("WordRow")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            #WordRow {{ border-radius: 4px; background: transparent; }}
            #WordRow:hover {{ background: {ROW_HOVER}; }}
            #WordRow[selected="true"] {{ background: {ROW_SEL}; }}
            #WordRow[checked="true"] {{ background: rgba(96,205,255,0.16); }}
        """)
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 8, 12, 8); lay.setSpacing(12)
        self.bar = QFrame(); self.bar.setFixedSize(3, 22)
        self.bar.setStyleSheet(f"background: {ACCENT}; border-radius: 1px;")
        self.bar.setVisible(False)
        lay.addWidget(self.bar)
        # галочка множественного выбора (видна только когда выбрано через Ctrl)
        self.check = QLabel("✓")
        self.check.setFixedWidth(14)
        self.check.setStyleSheet(f"color: {ACCENT}; font-weight: 700; font-size: 13px;")
        self.check.setVisible(False)
        lay.addWidget(self.check)
        lay.addWidget(flag_label(entry.get("src_lang", "en"), 18))
        col = QVBoxLayout(); col.setSpacing(1)
        top = QHBoxLayout(); top.setSpacing(8)
        w = QLabel(entry.get("dict_form") or entry.get("word_in_text", "?"))
        w.setStyleSheet("font-size: 13px;")
        top.addWidget(w)
        if entry.get("level"):
            top.addWidget(Badge(entry["level"]))
        if entry.get("favorite"):
            star = QLabel("★"); star.setStyleSheet("color: #f5c542; font-size: 13px;")
            top.addWidget(star)
        top.addStretch(1)
        col.addLayout(top)
        if entry.get("word_translation"):
            tr = QLabel(entry["word_translation"]); tr.setObjectName("Dim")
            col.addWidget(tr)
        lay.addLayout(col, 1)

    def set_selected(self, on: bool):
        self.setProperty("selected", "true" if on else "false")
        self.bar.setVisible(on)
        self.style().unpolish(self); self.style().polish(self)

    def set_checked(self, on: bool):
        self.setProperty("checked", "true" if on else "false")
        self.check.setVisible(on)
        self.style().unpolish(self); self.style().polish(self)

    def mousePressEvent(self, e):
        ctrl = bool(e.modifiers() & Qt.ControlModifier)
        self.clicked.emit(self.entry_id, ctrl)
        super().mousePressEvent(e)

class WordsPage(QWidget):
    fetch_missing = Signal()  # «Получить недостающие данные»

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_id: str | None = None
        self.edit_mode = False
        self._rows: dict[str, WordRow] = {}
        self._selected: set[str] = set()  # выбранные через Ctrl для удаления
        self._build()
        self.reload()
        # горячие клавиши вкладки «Слова» — ловим на уровне приложения, но реагируем
        # только когда вкладка видима и активно главное окно (см. eventFilter)
        from PySide6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

    # --------------------------------------------------- горячие клавиши
    def eventFilter(self, obj, ev):
        if (ev.type() == QEvent.KeyPress and self.isVisible()
                and self.window() and self.window().isActiveWindow()):
            if self._handle_key(ev):
                return True
        return super().eventFilter(obj, ev)

    def _handle_key(self, e) -> bool:
        from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit, QComboBox
        k, mod = e.key(), e.modifiers()
        if mod & Qt.ControlModifier and k == Qt.Key_F:          # Ctrl+F — поиск
            self.search.setFocus(); self.search.selectAll(); return True
        if mod & Qt.ControlModifier and k == Qt.Key_D:          # Ctrl+D — избранное
            if self.current_id:
                self._toggle_favorite(self.current_id)
            return True
        # клавиши без модификатора не перехватываем, пока пользователь печатает
        if isinstance(QApplication.focusWidget(), (QLineEdit, QTextEdit, QComboBox)):
            return False
        if k == Qt.Key_Space:                                   # Space — озвучить
            self._speak_current(); return True
        if k == Qt.Key_Delete:                                  # Delete — удалить
            self._delete_selected(); return True
        if k == Qt.Key_Left:                                    # ← предыдущее
            self._nav(-1); return True
        if k == Qt.Key_Right:                                   # → следующее
            self._nav(1); return True
        return False

    def _nav(self, delta: int):
        ids = list(self._rows.keys())                # порядок строк = порядок показа
        if not ids:
            return
        i = ids.index(self.current_id) + delta if self.current_id in ids else 0
        i = max(0, min(len(ids) - 1, i))
        self.select_entry(ids[i])
        row = self._rows.get(ids[i])
        if row:
            self.list_area.ensureWidgetVisible(row)

    def _speak_current(self):
        e = WORDS.get(self.current_id) if self.current_id else None
        if e:
            tts.speak(e.get("dict_form", "") or e.get("word_in_text", ""),
                      e.get("src_lang", "en"))

    def _toggle_favorite(self, entry_id: str):
        WORDS.toggle_favorite(entry_id)
        self.reload()
        self._render_detail()      # обновить звёздочку в карточке

    def _update_stats(self):
        fav = sum(1 for e in WORDS.items if e.get("favorite"))
        self.stat_total.setText(f"{t('Всего слов')}: {len(WORDS.items)}")
        self.stat_fav.setText(f"★ {t('Избранные')}: {fav}")

    # ------------------------------------------------------------- каркас
    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(20, 8, 20, 16); root.setSpacing(10)

        def action_btn(icon, tip, slot):
            b = QPushButton(); b.setObjectName("IconBtn"); b.setToolTip(tip)
            b.setIcon(svg_icon(icon, ICON, 16)); b.setFixedSize(34, 30)
            b.setCursor(Qt.PointingHandCursor); b.clicked.connect(slot)
            return b

        def filter_combo(min_w, max_w):
            c = QComboBox()
            c.setMinimumWidth(min_w); c.setMaximumWidth(max_w)
            c.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            return c                            # сигнал подключим после наполнения

        # --- ряд 1: поиск + счётчик слов + действия справа ---
        row1 = QHBoxLayout(); row1.setSpacing(8)
        self.search = QLineEdit(); self.search.setPlaceholderText(t("Поиск"))
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(300)                 # компактный, не во всю ширину
        self.search.textChanged.connect(self.reload)
        row1.addWidget(self.search)
        row1.addStretch(1)
        self.stat_total = QLabel(); self.stat_total.setObjectName("Dim")
        self.stat_fav = QLabel(); self.stat_fav.setObjectName("Dim")
        row1.addWidget(self.stat_total)
        row1.addSpacing(16)
        row1.addWidget(self.stat_fav)
        row1.addSpacing(16)
        row1.addWidget(action_btn("border-all.svg", t("Выделить всё"), self._select_all))
        row1.addWidget(action_btn("recycle-bin.svg", t("Удалить"), self._delete_selected))
        row1.addWidget(action_btn("paper-plane-top.svg", t("Экспорт"), self._export))
        root.addLayout(row1)

        # --- ряд 2: фильтры (по содержимому, без обрезки) ---
        row2 = QHBoxLayout(); row2.setSpacing(8)
        self.lang_filter = filter_combo(185, 225)
        self.lang_filter.addItem(svg_icon("globe.svg", ICON, 16), t("  Все языки"), "")
        self.source_filter = filter_combo(190, 225)    # длинные названия игр обрезаются внутри
        self.source_filter.addItem(svg_icon("filter.svg", ICON, 16), t("  Все источники"), "")
        self.sort_combo = filter_combo(165, 205)
        self.sort_combo.addItem(svg_icon("bars-sort.svg", ICON, 16), t("  По дате"), "date")
        self.sort_combo.addItem(svg_icon("bars-sort.svg", ICON, 16), t("  По уровню"), "level")
        self.level_filter = filter_combo(140, 175)
        self.level_filter.addItem(t("  Все уровни"), "")
        for c in (self.lang_filter, self.source_filter, self.sort_combo, self.level_filter):
            c.currentIndexChanged.connect(self.reload)   # подключаем после наполнения
            row2.addWidget(c)
        # только избранное — компактная кнопка-звезда
        self.btn_fav = QPushButton("★"); self.btn_fav.setObjectName("IconBtn")
        self.btn_fav.setCheckable(True); self.btn_fav.setCursor(Qt.PointingHandCursor)
        self.btn_fav.setToolTip(t("Только избранные")); self.btn_fav.setFixedSize(34, 30)
        self.btn_fav.setStyleSheet("font-size: 15px;")
        self.btn_fav.toggled.connect(self.reload)
        row2.addWidget(self.btn_fav)
        row2.addStretch(1)
        root.addLayout(row2)

        split = GripSplitter(Qt.Horizontal)
        split.setHandleWidth(10)
        root.addWidget(split, 1)

        # ---------- слева: список ----------
        left = QFrame(); left.setObjectName("Panel")
        ll = QVBoxLayout(left); ll.setContentsMargins(8, 10, 8, 10); ll.setSpacing(4)
        self.list_area = QScrollArea(); self.list_area.setWidgetResizable(True)
        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(4, 0, 4, 0); self.list_lay.setSpacing(2)
        self.list_lay.addStretch(1)
        self.list_area.setWidget(self.list_host)
        ll.addWidget(self.list_area)
        split.addWidget(left)

        # ---------- справа: карточка ----------
        right_host = QWidget()
        rl = QVBoxLayout(right_host); rl.setContentsMargins(12, 0, 0, 0); rl.setSpacing(10)
        self.banner = InfoBanner(t("Некоторые данные отсутствуют или неполные."),
                                 t("Получить недостающие данные"))
        self.banner.action.connect(self.fetch_missing.emit)
        rl.addWidget(self.banner)

        mode_row = QHBoxLayout(); mode_row.addStretch(1)
        self.btn_view = QPushButton(""); self.btn_edit = QPushButton("")
        self.btn_view.setIcon(svg_icon("eye.svg", ICON, 16))
        self.btn_edit.setIcon(svg_icon("pencil.svg", ICON, 16))
        self.btn_view_ul = Hairline(color=ACCENT); self.btn_edit_ul = Hairline(color=ACCENT)
        for b, ul, tip in ((self.btn_view, self.btn_view_ul, t("Режим просмотра")),
                           (self.btn_edit, self.btn_edit_ul, t("Режим редактирования"))):
            b.setObjectName("IconBtn"); b.setCheckable(True)
            b.setToolTip(tip); b.setFixedSize(38, 30); ul.setFixedHeight(2)
            col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(2)
            col.addWidget(b); col.addWidget(ul)
            mode_row.addLayout(col)
        self.btn_view.clicked.connect(lambda: self._set_mode(False))
        self.btn_edit.clicked.connect(lambda: self._set_mode(True))
        rl.addLayout(mode_row)

        self.detail_area = QScrollArea(); self.detail_area.setWidgetResizable(True)
        self.detail_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.detail_host = QFrame(); self.detail_host.setObjectName("Panel")
        self.detail_lay = QVBoxLayout(self.detail_host)
        self.detail_lay.setContentsMargins(28, 24, 28, 24); self.detail_lay.setSpacing(14)
        self.detail_area.setWidget(self.detail_host)
        rl.addWidget(self.detail_area, 1)
        split.addWidget(right_host)
        split.setSizes([560, 540])

    # ------------------------------------------------------ фильтры
    def _refresh_filters(self):
        """Наполняет фильтры языков и источников только тем, что реально есть в словах."""
        def rebuild(combo, all_label, items, label_fn, icon_fn=None, all_icon=None):
            cur = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(all_label, "")
            if all_icon is not None:          # иконка для пункта «Все …» (не теряется при пересборке)
                combo.setItemIcon(0, all_icon)
            for val in items:
                if icon_fn is not None:
                    combo.addItem(icon_fn(val), label_fn(val), val)
                else:
                    combo.addItem(label_fn(val), val)
            idx = combo.findData(cur)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

        langs, seen = [], set()
        for e in WORDS.items:
            lg = e.get("src_lang")
            if lg and lg not in seen:
                seen.add(lg); langs.append(lg)
        rebuild(self.lang_filter, t("  Все языки"), langs,
                lambda c: f"  {lang_name(c)}", flag_icon,
                all_icon=svg_icon("globe.svg", ICON, 16))

        srcs, seen = [], set()
        for e in WORDS.items:
            s = _src_key(e)
            if s and s not in seen:
                seen.add(s); srcs.append(s)
        rebuild(self.source_filter, t("  Все источники"), srcs, _pretty_src,
                all_icon=svg_icon("filter.svg", ICON, 16))

        levels = [lv for lv in CEFR
                  if any((e.get("level") or "").upper() == lv for e in WORDS.items)]
        rebuild(self.level_filter, t("  Все уровни"), levels, lambda c: f"  {c}")

    # ----------------------------------------------------------- список
    def reload(self):
        self._refresh_filters()
        # очистить
        while self.list_lay.count() > 1:
            it = self.list_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._rows.clear()

        q = self.search.text().strip().lower()
        lang = self.lang_filter.currentData() if hasattr(self, "lang_filter") else ""
        src_f = self.source_filter.currentData() if hasattr(self, "source_filter") else ""
        lvl = self.level_filter.currentData() if hasattr(self, "level_filter") else ""
        fav_only = self.btn_fav.isChecked() if hasattr(self, "btn_fav") else False
        sort_by = self.sort_combo.currentData() if hasattr(self, "sort_combo") else "date"

        def match(e):
            hay = " ".join([e.get("dict_form", ""), e.get("word_in_text", ""),
                            e.get("word_translation", ""),
                            " ".join(e.get("tags", []))]).lower()
            if q and q not in hay:
                return False
            if lang and e.get("src_lang") != lang:
                return False
            if src_f and _src_key(e) != src_f:
                return False
            if lvl and (e.get("level") or "").upper() != lvl:
                return False
            if fav_only and not e.get("favorite"):
                return False
            return True

        items = [e for e in WORDS.items if match(e)]
        if sort_by == "level":  # по уровню (A1→C2), внутри уровня — новые сверху
            items.sort(key=lambda e: (_cefr_rank(e), -e.get("created", 0)))

        last_group = None
        insert_at = 0
        for e in items:
            group = (e.get("level") or t("Без уровня")) if sort_by == "level" \
                else _day_label(e.get("created", 0))
            if group != last_group:
                lbl = QLabel(group); lbl.setObjectName("SectionTitle")
                self.list_lay.insertWidget(insert_at, lbl); insert_at += 1
                hl = Hairline(); self.list_lay.insertWidget(insert_at, hl); insert_at += 1
                last_group = group
            row = WordRow(e)
            row.clicked.connect(self.select_entry)
            self.list_lay.insertWidget(insert_at, row); insert_at += 1
            self._rows[e["id"]] = row

        self._update_stats()

        # сохранить множественный выбор только для ещё существующих строк
        self._selected &= set(self._rows.keys())
        for rid in self._selected:
            self._rows[rid].set_checked(True)

        self.banner.setVisible(len(WORDS.incomplete()) > 0)
        if self.current_id and self.current_id in self._rows:
            self._rows[self.current_id].set_selected(True)
        elif WORDS.items:
            self.select_entry(WORDS.items[0]["id"])
        else:
            self._clear_detail()
            self.detail_lay.addWidget(QLabel(t("Здесь появятся сохранённые слова.\n"
                                               "Нажмите горячую клавишу над словом на экране.")))
            self.detail_lay.addStretch(1)

    def select_entry(self, entry_id: str, ctrl: bool = False):
        if ctrl:  # Ctrl+клик — добавить/убрать из множественного выбора
            if entry_id in self._selected:
                self._selected.discard(entry_id)
                self._rows[entry_id].set_checked(False)
            else:
                self._selected.add(entry_id)
                self._rows[entry_id].set_checked(True)
            return
        # обычный клик — сбросить множественный выбор и открыть слово
        if self._selected:
            for rid in self._selected:
                if rid in self._rows:
                    self._rows[rid].set_checked(False)
            self._selected.clear()
        for rid, row in self._rows.items():
            row.set_selected(rid == entry_id)
        self.current_id = entry_id
        self._render_detail()

    # ------------------------------------------------------- карточка
    def _set_mode(self, edit: bool):
        self.edit_mode = edit
        self._render_detail()

    def _clear_detail(self):
        while self.detail_lay.count():
            it = self.detail_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                while it.layout().count():
                    sub = it.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

    def _render_detail(self):
        self._clear_detail()
        self.btn_view.setChecked(not self.edit_mode)
        self.btn_edit.setChecked(self.edit_mode)
        self.btn_view_ul.setVisible(not self.edit_mode)
        self.btn_edit_ul.setVisible(self.edit_mode)
        for b in (self.btn_view, self.btn_edit):
            b.style().unpolish(b); b.style().polish(b)
        e = WORDS.get(self.current_id) if self.current_id else None
        if not e:
            return
        if self.edit_mode:
            self._render_edit(e)
        else:
            self._render_view(e)

    def _shot_label(self, e, max_h=460):
        if not e.get("screenshot"):
            return None
        path = WORDS.screenshot_path(e["screenshot"])
        pm = QPixmap(path)
        if pm.isNull():
            return None
        # ScalableImage сам подстраивается под ширину панели; клик открывает файл
        return ScalableImage(pm, max_h, path=path)

    def _render_view(self, e: dict):
        L = self.detail_lay
        # заголовок
        head = QHBoxLayout(); head.addStretch(1)
        title = QLabel(e.get("dict_form") or e.get("word_in_text", "")); title.setObjectName("H1")
        head.addWidget(title)
        sp = QPushButton("🔊"); sp.setObjectName("IconBtn")
        sp.clicked.connect(lambda: tts.speak(e.get("dict_form", ""), e.get("src_lang", "en")))
        head.addWidget(sp)
        fav_on = e.get("favorite", False)
        favb = QPushButton("★" if fav_on else "☆"); favb.setObjectName("IconBtn")
        favb.setToolTip(t("В избранное") + "  (Ctrl+D)")
        favb.setStyleSheet("font-size: 18px; color: %s;" % ("#f5c542" if fav_on else TEXT_DIM))
        favb.clicked.connect(lambda: self._toggle_favorite(e["id"]))
        head.addWidget(favb); head.addStretch(1)
        L.addLayout(head)
        if e.get("word_translation"):
            sub = QLabel(e["word_translation"]); sub.setAlignment(Qt.AlignCenter)
            sub.setStyleSheet(f"color: {TEXT_DIM}; font-size: 15px; font-weight: 600;")
            L.addWidget(sub)
        if e.get("tags"):
            trow = QHBoxLayout(); trow.setSpacing(6)
            for tg in e["tags"]:
                chip = QLabel("#" + tg)
                chip.setStyleSheet(f"background: {BG_CARD}; color: {TEXT_DIM}; "
                                   f"border: 1px solid {BORDER}; border-radius: 10px; "
                                   "padding: 2px 10px; font-size: 12px;")
                trow.addWidget(chip)
            trow.addStretch(1)
            tw = QWidget(); tw.setLayout(trow); L.addWidget(tw)
        shot = self._shot_label(e)
        if shot:
            L.addWidget(shot)
        # определение (цитата)
        if e.get("definition"):
            q = QFrame(); ql = QHBoxLayout(q); ql.setContentsMargins(0, 4, 0, 4); ql.setSpacing(12)
            bar = QFrame(); bar.setFixedWidth(3)
            bar.setStyleSheet(f"background: {ACCENT}; border-radius: 1px;")
            ql.addWidget(bar)
            d = QLabel(e["definition"]); d.setObjectName("Quote"); d.setWordWrap(True)
            ql.addWidget(d, 1)
            s2 = QPushButton("🔊"); s2.setObjectName("IconBtn")
            s2.clicked.connect(lambda: tts.speak(e.get("definition", ""), CONFIG.get("looktionary_pro")["def_lang"]))
            ql.addWidget(s2, 0, Qt.AlignTop)
            L.addWidget(q)
        # контекст с подсветкой слова
        ctx = e.get("context_translation") or e.get("context")
        if ctx:
            ctx_html = html.escape(ctx).replace("&lt;u&gt;", "<span style='background:#6b6b1e;'>") \
                                       .replace("&lt;/u&gt;", "</span>")
            c = QLabel(f"<i>{ctx_html}</i>"); c.setWordWrap(True); c.setTextFormat(Qt.RichText)
            c.setStyleSheet(f"background: {BG_CARD}; border-radius: 6px; padding: 12px;")
            L.addWidget(c)
        # источник
        src = e.get("source_title") or e.get("source_app")
        if src:
            s = QLabel(f"{t('Найдено в')} <b>{html.escape(src)}</b>")
            s.setObjectName("Dim"); s.setTextFormat(Qt.RichText)
            L.addWidget(s)
        L.addStretch(1)

    def _render_edit(self, e: dict):
        L = self.detail_lay

        def field(value, key, multi=False, h=70):
            if multi:
                w = QTextEdit(); w.setPlainText(value or ""); w.setFixedHeight(h)
                w.textChanged.connect(lambda: WORDS.update(e["id"], **{key: w.toPlainText()}))
            else:
                w = QLineEdit(value or "")
                w.editingFinished.connect(lambda: (WORDS.update(e["id"], **{key: w.text()}),
                                                   self.reload()))
            return w

        grid = QGridLayout(); grid.setHorizontalSpacing(16); grid.setVerticalSpacing(6)
        grid.addWidget(QLabel(t("Словарная форма")), 0, 0)
        grid.addWidget(QLabel(t("Слово в тексте")), 0, 1)
        grid.addWidget(field(e.get("dict_form"), "dict_form"), 1, 0)
        grid.addWidget(field(e.get("word_in_text"), "word_in_text"), 1, 1)
        L.addLayout(grid)

        L.addWidget(QLabel(t("Теги (через запятую)")))
        tagf = QLineEdit(", ".join(e.get("tags", [])))
        tagf.setPlaceholderText("#диалоги, #магия, #важное")
        tagf.editingFinished.connect(lambda: (
            WORDS.update(e["id"], tags=[x.strip().lstrip("#") for x in tagf.text().split(",") if x.strip()]),
            self.reload()))
        L.addWidget(tagf)

        L.addWidget(QLabel(t("Определение")))
        L.addWidget(field(e.get("definition"), "definition", multi=True))

        shot = self._shot_label(e, max_h=180)
        if shot:
            L.addWidget(shot)

        # Лингвистическая информация
        ling = QWidget(); lg = QGridLayout(ling); lg.setVerticalSpacing(6)
        lg.addWidget(QLabel(t("Уровень (CEFR)")), 0, 0); lg.addWidget(QLabel(t("Транскрипция")), 0, 1)
        lg.addWidget(field(e.get("level"), "level"), 1, 0)
        lg.addWidget(field(e.get("transcription"), "transcription"), 1, 1)
        lg.addWidget(QLabel(t("Часть речи / пометы")), 2, 0, 1, 2)
        tags = QLineEdit(", ".join(e.get("pos_tags", [])))
        tags.editingFinished.connect(lambda: WORDS.update(
            e["id"], pos_tags=[t.strip() for t in tags.text().split(",") if t.strip()]))
        lg.addWidget(tags, 3, 0, 1, 2)
        lg.addWidget(QLabel(t("Синонимы")), 4, 0, 1, 2)
        syn = QLineEdit(", ".join(e.get("synonyms", [])))
        syn.editingFinished.connect(lambda: WORDS.update(
            e["id"], synonyms=[t.strip() for t in syn.text().split(",") if t.strip()]))
        lg.addWidget(syn, 5, 0, 1, 2)
        L.addWidget(Collapsible(t("Лингвистическая информация"), ling))

        # Детали источника
        srcw = QWidget(); sg = QGridLayout(srcw); sg.setVerticalSpacing(6)
        sg.addWidget(QLabel(t("Приложение")), 0, 0); sg.addWidget(QLabel(t("Заголовок окна")), 0, 1)
        sg.addWidget(field(e.get("source_app"), "source_app"), 1, 0)
        sg.addWidget(field(e.get("source_title"), "source_title"), 1, 1)
        L.addWidget(Collapsible(t("Детали источника"), srcw))

        # Перевод
        h2 = QLabel(t("Перевод")); h2.setObjectName("H2")
        L.addWidget(h2)
        L.addWidget(QLabel(t("Контекст")))
        L.addWidget(field(e.get("context"), "context", multi=True, h=90))
        grid2 = QGridLayout(); grid2.setHorizontalSpacing(16); grid2.setVerticalSpacing(6)
        grid2.addWidget(QLabel(t("Перевод слова")), 0, 0)
        grid2.addWidget(QLabel(t("Перевод контекста")), 0, 1)
        grid2.addWidget(field(e.get("word_translation"), "word_translation"), 1, 0)
        grid2.addWidget(field(e.get("context_translation"), "context_translation",
                              multi=True, h=110), 1, 1)
        L.addLayout(grid2)
        L.addStretch(1)

    # ------------------------------------------------------------ действия
    def _select_all(self):
        """Отметить/снять все видимые слова (для удаления)."""
        if self._selected >= set(self._rows.keys()) and self._rows:
            # уже все выбраны — снять выделение
            for row in self._rows.values():
                row.set_checked(False)
            self._selected.clear()
        else:
            for rid, row in self._rows.items():
                row.set_checked(True)
                self._selected.add(rid)

    def _delete_selected(self):
        ids = list(self._selected) if self._selected else \
            ([self.current_id] if self.current_id else [])
        if not ids:
            return
        if len(ids) == 1:
            e = WORDS.get(ids[0])
            word = e.get("dict_form", "") if e else ""
            msg = t("Удалить слово «%s»?") % word
        else:
            msg = t("Удалить выбранные слова (%d)?") % len(ids)
        if QMessageBox.question(self, t("Удалить"), msg) == QMessageBox.Yes:
            WORDS.delete(ids)
            self._selected -= set(ids)
            if self.current_id in ids:
                self.current_id = None
            self.reload()

    def _export(self):
        # спрашиваем язык, источник (игра/приложение) и стартовое слово диапазона
        chosen = self._ask_export_options()
        if chosen is None:               # отмена в диалоге
            return
        lang, src, since = chosen        # пустые == «все»; since==0 — все слова

        sel = [e for e in WORDS.items
               if (not lang or e.get("src_lang") == lang)
               and (not src or _src_key(e) == src)
               and e.get("created", 0) >= since]
        # ids=None означает «всё» — отдаём только когда реально нет фильтра
        ids = None if (not lang and not src and since <= 0) else [e["id"] for e in sel]
        if ids is not None and not ids:
            return

        suffix = ""
        if lang:
            suffix += "_" + lang
        if src:
            suffix += "_" + _pretty_src(src).replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self, t("Экспорт слов"), f"wordsnap{suffix}_anki.txt",
            "Anki (*.txt);;CSV (*.csv);;JSON (*.json)")
        if path:
            WORDS.export(path, ids)

    def _ask_export_options(self) -> tuple[str, str, float] | None:
        """Диалог экспорта: язык + источник + слово, с которого брать (до самого нового).
        Возвращает (язык, ключ источника, метку времени старта) или None при отмене.
        Пустые строки — «все языки/источники»; метка 0.0 — все слова."""
        langs, seen = [], set()
        for e in WORDS.items:
            lg = e.get("src_lang")
            if lg and lg not in seen:
                seen.add(lg); langs.append(lg)
        srcs, seen = [], set()
        for e in WORDS.items:
            s = _src_key(e)
            if s and s not in seen:
                seen.add(s); srcs.append(s)

        dlg = QDialog(self)
        dlg.setWindowTitle(t("Экспорт слов"))
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 16); lay.setSpacing(8)
        dlg.setMinimumWidth(360)

        lay.addWidget(QLabel(t("Язык для экспорта:")))
        lang_combo = QComboBox()
        lang_combo.addItem(svg_icon("globe.svg", ICON, 16), t("  Все языки"), "")
        for lg in langs:
            lang_combo.addItem(flag_icon(lg), f"  {lang_name(lg)}", lg)
        cl = self.lang_filter.currentData() if hasattr(self, "lang_filter") else ""
        i = lang_combo.findData(cl)
        lang_combo.setCurrentIndex(i if i >= 0 else 0)
        lay.addWidget(lang_combo)

        lay.addSpacing(6)
        lay.addWidget(QLabel(t("Источник для экспорта:")))
        src_combo = QComboBox()
        src_combo.addItem(svg_icon("filter.svg", ICON, 16), t("  Все источники"), "")
        for s in srcs:
            src_combo.addItem(_pretty_src(s), s)
        cur = self.source_filter.currentData() if hasattr(self, "source_filter") else ""
        idx = src_combo.findData(cur)
        src_combo.setCurrentIndex(idx if idx >= 0 else 0)
        lay.addWidget(src_combo)

        lay.addSpacing(6)
        lay.addWidget(QLabel(t("Начиная со слова (до самого нового):")))
        from_combo = QComboBox()
        lay.addWidget(from_combo)

        def fill_words():
            lg = lang_combo.currentData()
            src = src_combo.currentData()
            words = [e for e in WORDS.items
                     if (not lg or e.get("src_lang") == lg)
                     and (not src or _src_key(e) == src)]
            words.sort(key=lambda e: e.get("created", 0))      # от старых к новым
            from_combo.blockSignals(True)
            from_combo.clear()
            from_combo.addItem(t("  Все слова"), 0.0)
            for e in words:
                ts = e.get("created", 0)
                label = e.get("dict_form") or e.get("word_in_text") or "—"
                if ts:
                    label = f"{label}   ·   {datetime.date.fromtimestamp(ts).strftime('%d.%m.%Y')}"
                from_combo.addItem(label, float(ts or 0.0))
            from_combo.setCurrentIndex(0)
            from_combo.blockSignals(False)

        lang_combo.currentIndexChanged.connect(fill_words)
        src_combo.currentIndexChanged.connect(fill_words)
        fill_words()

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        lay.addSpacing(6)
        lay.addWidget(box)

        if dlg.exec() != QDialog.Accepted:
            return None
        return (lang_combo.currentData(), src_combo.currentData(),
                float(from_combo.currentData() or 0.0))
