import html
import sys

from PySide6.QtCore import (Qt, Signal, QPoint, QRect, QPropertyAnimation,
                            QParallelAnimationGroup, QEasingCurve, QTimer)
from PySide6.QtGui import QGuiApplication, QCursor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QFrame, QScrollArea, QApplication)

from ..config import CONFIG
from .. import tts
from .widgets import Badge, Hairline, Collapsible, flag_label
from .theme import ACCENT, BG_PANEL, BORDER, TEXT_DIM, BG_CARD, IS_WIN11, IS_WIN10
from .i18n import t as _tr

# жёлто-оливковая подсветка слова (как в оригинале Lookupper)
HILITE = "#7f801e"
POPUP_W = 580   # ширина окна перевода (как в оригинале)
POPUP_MAX_H = 520  # максимальная высота — дальше появляется прокрутка
RESIZE_MARGIN = 6  # рамка захвата для ручного ресайза окна мышкой


class Spoiler(QLabel):
    """Скрытый перевод: текст под «спойлером», открывается по клику."""
    def __init__(self, text: str, cover: str = "#3a3a3a", parent=None):
        super().__init__(parent)
        self._text = text
        self._cover = cover
        self._open = False
        self.setCursor(Qt.PointingHandCursor)
        self.setText(text)
        self._render()

    def _render(self):
        if self._open:
            self.setStyleSheet("background: transparent;")
        else:
            self.setStyleSheet(f"background: {self._cover}; color: {self._cover}; border-radius: 3px;")

    def mousePressEvent(self, e):
        self._open = True
        self._render()


class SourceSection(QFrame):
    """Секция одного источника внутри попапа."""
    def __init__(self, title: str, sparkle: bool, dim: str = TEXT_DIM,
                 line_color: str = BORDER, parent=None):
        super().__init__(parent)
        self._dim = dim
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(0, 6, 0, 10)
        self.v.setSpacing(8)
        head = QHBoxLayout(); head.setSpacing(6)
        t = QLabel(title + ("  ✦" if sparkle else ""))
        t.setStyleSheet(f"color: {dim}; font-size: 13px; background: transparent;")
        head.addWidget(t)
        info = QLabel("ⓘ"); info.setStyleSheet(f"color: {dim}; background: transparent;")
        head.addWidget(info)
        line = Hairline(color=line_color)
        head.addWidget(line, 1)
        self.v.addLayout(head)
        self.body = QVBoxLayout(); self.body.setSpacing(8)
        self.v.addLayout(self.body)
        self._loading = QLabel(_tr("…  загрузка"))
        self._loading.setStyleSheet(f"color: {dim}; background: transparent;")
        self.body.addWidget(self._loading)

    def clear_loading(self):
        if self._loading:
            self._loading.deleteLater()
            self._loading = None

    def clear_body(self):
        self.clear_loading()
        while self.body.count():
            item = self.body.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def add(self, w):
        self.clear_loading()
        self.body.addWidget(w)

    def fail(self, msg: str):
        self.clear_loading()
        l = QLabel(msg); l.setWordWrap(True)
        l.setStyleSheet(f"color: {self._dim}; background: transparent;")
        self.body.addWidget(l)


def highlighted(text: str) -> QLabel:
    """Текст с <u>словом</u> → подсветка жёлто-оливковым, как в оригинале."""
    t = html.escape(text).replace("&lt;u&gt;", f"<span style='background:{HILITE};'>") \
                         .replace("&lt;/u&gt;", "</span>")
    l = QLabel(t); l.setTextFormat(Qt.RichText); l.setWordWrap(True)
    l.setStyleSheet("font-size: 13px;")
class YomitanSenseWidget(QWidget):
    """Словарная статья офлайн-словаря в стиле Yomitan:
    - Заголовок с номером, бейджем части речи (n) и фиолетовым бейджем словаря
    - Сворачиваемая «▶  Этимология» (по умолчанию закрыта, открывается по клику)
    - Нумерованные определения с кнопкой «▸» для раскрытия примеров употребления
    - Ссылки на первоисточники (Wiktionary ↗ | Kaikki ↗) справа
    """
    def __init__(self, index: int, entry: dict, on_toggle=None, parent=None):
        super().__init__(parent)
        self.on_toggle = on_toggle
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 4, 0, 10)
        v.setSpacing(4)

        pos = entry.get("pos", "").strip()
        d_title = entry.get("dict_title", entry.get("dict_id", "")).strip()

        if index > 1:
            div = Hairline(color="#3e3e3e")
            v.addWidget(div)
            v.addSpacing(6)

        term_text = entry.get("term", "")

        # 1. Заголовок слова (в стиле Yomitan: ▶ term   [🔊])
        head_row = QHBoxLayout()
        head_row.setContentsMargins(0, 0, 0, 0)
        head_row.setSpacing(6)

        arrow_lbl = QLabel("▶")
        arrow_lbl.setStyleSheet("color: #4ea8de; font-size: 13px; font-weight: bold; background: transparent;")
        head_row.addWidget(arrow_lbl)

        term_lbl = QLabel(term_text)
        term_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff; background: transparent;")
        term_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        head_row.addWidget(term_lbl)

        reading = entry.get("reading", "").strip()
        if reading and reading != term_text:
            read_lbl = QLabel(f"/{reading}/")
            read_lbl.setStyleSheet("font-size: 13px; color: #999999; background: transparent; padding-top: 3px;")
            head_row.addWidget(read_lbl)

        head_row.addStretch(1)

        btn_spk = QPushButton("🔊")
        btn_spk.setCursor(Qt.PointingHandCursor)
        btn_spk.setToolTip(_tr("Озвучить"))
        btn_spk.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 13px; padding: 2px 4px; color: #e06c75; } "
            "QPushButton:hover { background: rgba(255, 255, 255, 0.12); border-radius: 4px; }"
        )
        btn_spk.clicked.connect(lambda: tts.speak(term_text))
        head_row.addWidget(btn_spk)

        v.addLayout(head_row)

        # 2. Бейджи (🧩 ing, (v), [wty-en-ru])
        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(14, 0, 0, 2)
        badge_row.setSpacing(6)

        inf_tag = entry.get("inflection_tag")
        deinf = entry.get("deinflected_from")
        if inf_tag:
            puzzle_badge = QLabel(f"🧩 {inf_tag}")
            puzzle_badge.setStyleSheet(
                "background: #193822; color: #4ade80; border: 1px solid #275635; "
                "border-radius: 4px; padding: 1px 7px; font-size: 11px; font-weight: 600;"
            )
            if deinf:
                puzzle_badge.setToolTip(f"{term_text} ← {deinf}")
            badge_row.addWidget(puzzle_badge)
        elif deinf:
            deinf_badge = QLabel(f"{term_text} ← {deinf}")
            deinf_badge.setStyleSheet(
                "background: #1a3a5c; color: #60cdff; border: 1px solid #2a5a8c; "
                "border-radius: 4px; padding: 1px 7px; font-size: 11px; font-weight: 600;"
            )
            badge_row.addWidget(deinf_badge)

        if pos:
            pos_badge = QLabel(f"({pos})")
            pos_badge.setStyleSheet(
                "background: #383838; color: #cccccc; border: 1px solid #484848; "
                "border-radius: 9px; padding: 1px 7px; font-size: 11px; font-weight: 600;"
            )
            badge_row.addWidget(pos_badge)

        if d_title:
            dict_badge = QLabel(d_title)
            dict_badge.setStyleSheet(
                "background: #7042a6; color: #ffffff; border-radius: 4px; "
                "padding: 1px 6px; font-size: 11px; font-weight: 600;"
            )
            badge_row.addWidget(dict_badge)

        badge_row.addStretch(1)
        v.addLayout(badge_row)

        parsed = entry.get("parsed")
        if not parsed:
            fallback = QLabel(entry.get("html", "") or entry.get("text", ""))
            fallback.setTextFormat(Qt.RichText)
            fallback.setWordWrap(True)
            fallback.setTextInteractionFlags(Qt.TextSelectableByMouse)
            fallback.setStyleSheet("color: #cccccc; font-size: 13px; padding-left: 14px; margin-top: 4px;")
            v.addWidget(fallback)
            return

        # 2. Этимология (СВЁРНУТА ПО УМОЛЧАНИЮ)
        for etym in parsed.get("etymologies", []):
            summ_text = etym.get("summary", _tr("Этимология"))
            btn_etym = QPushButton(f"▶  {summ_text}")
            btn_etym.setCursor(Qt.PointingHandCursor)
            btn_etym.setStyleSheet(
                "background: transparent; border: none; color: #4ea8de; "
                "font-size: 13px; font-weight: 500; text-align: left; padding: 2px 0 2px 14px;"
            )

            etym_box = QWidget()
            etym_box.setVisible(False)
            eb_lay = QVBoxLayout(etym_box)
            eb_lay.setContentsMargins(14, 2, 0, 4)
            etym_lbl = QLabel(etym.get("body", ""))
            etym_lbl.setTextFormat(Qt.RichText)
            etym_lbl.setWordWrap(True)
            etym_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            etym_lbl.setStyleSheet(
                "color: #cccccc; font-size: 12px; border-left: 2px solid #484848; "
                "padding-left: 8px; line-height: 1.45;"
            )
            eb_lay.addWidget(etym_lbl)

            def make_etym_toggler(btn, box, title):
                def toggle():
                    is_vis = not box.isVisible()
                    box.setVisible(is_vis)
                    btn.setText(f"▼  {title}" if is_vis else f"▶  {title}")
                    if self.on_toggle:
                        self.on_toggle()
                return toggle

            btn_etym.clicked.connect(make_etym_toggler(btn_etym, etym_box, summ_text))
            v.addWidget(btn_etym)
            v.addWidget(etym_box)

        # 3. Определения (список glosses)
        glosses = parsed.get("glosses", [])
        for g_idx, g in enumerate(glosses, 1):
            gloss_widget = QWidget()
            gw_lay = QVBoxLayout(gloss_widget)
            gw_lay.setContentsMargins(14, 1, 0, 2)
            gw_lay.setSpacing(2)

            main_line = QHBoxLayout()
            main_line.setContentsMargins(0, 0, 0, 0)
            main_line.setSpacing(6)

            text_lbl = QLabel(f"{g_idx}.  {g['text']}")
            text_lbl.setTextFormat(Qt.RichText)
            text_lbl.setWordWrap(True)
            text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            text_lbl.setStyleSheet("color: #ffffff; font-size: 13px;")
            main_line.addWidget(text_lbl)

            # Если есть примеры
            if g.get("examples"):
                btn_ex = QPushButton("▸")
                btn_ex.setToolTip(_tr("Показать примеры"))
                btn_ex.setCursor(Qt.PointingHandCursor)
                btn_ex.setStyleSheet(
                    "background: transparent; border: none; color: #4ea8de; "
                    "font-size: 13px; font-weight: bold; padding: 0 4px;"
                )
                main_line.addWidget(btn_ex)

                ex_box = QWidget()
                ex_box.setVisible(False)
                ex_lay = QVBoxLayout(ex_box)
                ex_lay.setContentsMargins(18, 2, 0, 4)
                ex_lay.setSpacing(2)

                for ex in g["examples"]:
                    if ex.get("a"):
                        la = QLabel(ex["a"])
                        la.setTextFormat(Qt.RichText); la.setWordWrap(True)
                        la.setStyleSheet("color: #dcdcdc; font-size: 12px;")
                        ex_lay.addWidget(la)
                    if ex.get("b"):
                        lb = QLabel(ex["b"])
                        lb.setTextFormat(Qt.RichText); lb.setWordWrap(True)
                        lb.setStyleSheet("color: #999999; font-size: 12px;")
                        ex_lay.addWidget(lb)

                def make_ex_toggler(btn, box):
                    def toggle():
                        is_vis = not box.isVisible()
                        box.setVisible(is_vis)
                        btn.setText("▾" if is_vis else "▸")
                        if self.on_toggle:
                            self.on_toggle()
                    return toggle

                btn_ex.clicked.connect(make_ex_toggler(btn_ex, ex_box))
                gw_lay.addLayout(main_line)
                gw_lay.addWidget(ex_box)
            else:
                main_line.addStretch(1)
                gw_lay.addLayout(main_line)

            v.addWidget(gloss_widget)

        # 4. Backlinks (Wiktionary ↗ | Kaikki ↗)
        backlinks = parsed.get("backlinks", [])
        if backlinks:
            bl_row = QHBoxLayout()
            bl_row.setContentsMargins(0, 2, 0, 0)
            bl_row.addStretch(1)
            links_parts = [
                f"<a href='{html.escape(b['href'])}' style='color:#4ea8de; text-decoration:none;'>{html.escape(b['title'])} ↗</a>"
                for b in backlinks
            ]
            bl_lbl = QLabel("  |  ".join(links_parts))
            bl_lbl.setTextFormat(Qt.RichText)
            bl_lbl.setOpenExternalLinks(True)
            bl_lbl.setStyleSheet("font-size: 11px; color: #888888;")
            bl_row.addWidget(bl_lbl)
            v.addLayout(bl_row)


class DictionaryPopup(QWidget):
    bookmark_clicked = Signal()
    anki_clicked = Signal()
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        outer = QVBoxLayout(self); outer.setContentsMargins(8, 8, 8, 8)
        self.card = QFrame(); self.card.setObjectName("PopupCard")
        self._anki_state = "idle"
        self._apply_theme(light=False)
        outer.addWidget(self.card)
        cv = QVBoxLayout(self.card); cv.setContentsMargins(0, 0, 0, 0); cv.setSpacing(0)

        # верхняя панель: Anki (＋) и закладка (сохранить слово)
        topbar = QHBoxLayout(); topbar.setContentsMargins(16, 8, 10, 0)
        topbar.addStretch(1)

        self.btn_anki = QPushButton("＋")
        self.btn_anki.setObjectName("AnkiBtn")
        self.btn_anki.setToolTip(_tr("Добавить слово в Anki"))
        self.btn_anki.setCursor(Qt.PointingHandCursor)
        self.btn_anki.clicked.connect(self._on_anki_click)
        self.set_anki_state("idle")
        topbar.addWidget(self.btn_anki)
        topbar.addSpacing(4)

        self.btn_bookmark = QPushButton("🔖")
        self.btn_bookmark.setObjectName("BookmarkBtn")
        self.btn_bookmark.setToolTip(_tr("Сохранить слово в личный словарь"))
        self.btn_bookmark.setCursor(Qt.PointingHandCursor)
        self.btn_bookmark.setStyleSheet(
            "QPushButton { font-size: 15px; background: transparent; border: none; border-radius: 4px; padding: 1px 4px; } "
            "QPushButton:hover { background: rgba(255, 255, 255, 0.12); }"
        )
        self.btn_bookmark.clicked.connect(self._on_bookmark)
        topbar.addWidget(self.btn_bookmark)
        cv.addLayout(topbar)

        self.area = QScrollArea(); self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.NoFrame)          # без рамки/лишней линии
        self.area.setStyleSheet("background: transparent; border: none;")
        self.area.viewport().setStyleSheet("background: transparent;")
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        host = QWidget(); host.setStyleSheet("background: transparent;")
        self.body = QVBoxLayout(host)
        self.body.setContentsMargins(18, 2, 18, 14); self.body.setSpacing(4)
        self.body.addStretch(1)
        self.area.setWidget(host)
        cv.addWidget(self.area)

        self.setFixedWidth(POPUP_W)
        self.setMouseTracking(True)
        self.card.setMouseTracking(True)
        self.sections: dict[str, SourceSection] = {}
        self._saved = False
        self._anim_grp: QParallelAnimationGroup | None = None
        self._move_anim: QPropertyAnimation | None = None
        self._resize_anim: QParallelAnimationGroup | None = None
        self._close_anim: QParallelAnimationGroup | None = None
        self._zooming = False
        self._closing = False
        self._target_h = 0
        self._pending_pos: tuple[int, int] | None = None
        self._word_rect: tuple[int, int, int, int] | None = None  # (x,y,w,h) подсвеченного слова
        self._placement = "below"                                 # "below" | "above" — с какой стороны от слова

    def _get_resize_edges(self, pos: QPoint) -> Qt.Edge:
        edges = Qt.Edge(0)
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = RESIZE_MARGIN
        if x <= m:
            edges |= Qt.LeftEdge
        elif x >= w - m:
            edges |= Qt.RightEdge
        if y <= m:
            edges |= Qt.TopEdge
        elif y >= h - m:
            edges |= Qt.BottomEdge
        return edges

    def _update_resize_cursor(self, edges: Qt.Edge):
        if (edges & Qt.LeftEdge and edges & Qt.TopEdge) or (edges & Qt.RightEdge and edges & Qt.BottomEdge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif (edges & Qt.RightEdge and edges & Qt.TopEdge) or (edges & Qt.LeftEdge and edges & Qt.BottomEdge):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edges & (Qt.LeftEdge | Qt.RightEdge):
            self.setCursor(Qt.SizeHorCursor)
        elif edges & (Qt.TopEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.unsetCursor()

    def mouseMoveEvent(self, e):
        if not self._zooming and not self._closing:
            edges = self._get_resize_edges(e.position().toPoint())
            self._update_resize_cursor(edges)
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self._zooming and not self._closing:
            edges = self._get_resize_edges(e.position().toPoint())
            if edges:
                self.setMinimumSize(320, 120)
                self.setMaximumSize(16777215, 16777215)
                handle = self.windowHandle()
                if handle and hasattr(handle, "startSystemResize"):
                    if handle.startSystemResize(edges):
                        e.accept()
                        return
        super().mousePressEvent(e)

    def leaveEvent(self, e):
        self.unsetCursor()
        super().leaveEvent(e)

    def nativeEvent(self, eventType, message):
        if sys.platform == "win32" and eventType == "windows_generic_MSG":
            try:
                import ctypes
                from ctypes import wintypes
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == 0x0084:  # WM_NCHITTEST
                    if self._zooming or self._closing:
                        return False, 0
                    x = ctypes.c_short(msg.lParam & 0xFFFF).value
                    y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                    dpr = self.devicePixelRatioF()
                    if dpr > 0 and dpr != 1.0:
                        p = self.mapFromGlobal(QPoint(int(x / dpr), int(y / dpr)))
                    else:
                        p = self.mapFromGlobal(QPoint(x, y))

                    px, py = p.x(), p.y()
                    w, h = self.width(), self.height()
                    m = RESIZE_MARGIN

                    left = px < m
                    right = px >= w - m
                    top = py < m
                    bottom = py >= h - m

                    if top and left:
                        return True, 13  # HTTOPLEFT
                    if top and right:
                        return True, 14  # HTTOPRIGHT
                    if bottom and left:
                        return True, 16  # HTBOTTOMLEFT
                    if bottom and right:
                        return True, 17  # HTBOTTOMRIGHT
                    if left:
                        return True, 10  # HTLEFT
                    if right:
                        return True, 11  # HTRIGHT
                    if top:
                        return True, 12  # HTTOP
                    if bottom:
                        return True, 15  # HTBOTTOM
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    def _apply_theme(self, light: bool):
        """Светлая/тёмная тема попапа в зависимости от фона под курсором (идея адаптации)."""
        self._light = light
        if light:
            self.c = dict(card="#f4f4f4", text="#1b1b1b", dim="#6a6a6a",
                          tag_bg="#e7e7e7", tag_brd="#cfcfcf", tag_text="#3a3a3a",
                          hl="#ffe27a", spoiler="#d2d2d2", coll_bg="#ececec", line="#d8d8d8")
        else:
            self.c = dict(card="#2b2b2b", text="#ffffff", dim="#a0a0a0",
                          tag_bg="#383838", tag_brd="#454545", tag_text="#dcdcdc",
                          hl=HILITE, spoiler="#3a3a3a", coll_bg="#333333", line="#3a3a3a")
        c = self.c
        # стилизуем только карточку (#PopupCard), цвет текста — всем меткам внутри
        self.card.setStyleSheet(
            f"QFrame#PopupCard {{ background: {c['card']}; border-radius: 8px; }} "
            f"QLabel {{ color: {c['text']}; background: transparent; }}")

    def _highlighted(self, text: str) -> QLabel:
        """Текст с <u>словом</u> → подсветка цветом текущей темы."""
        t = html.escape(text).replace(
            "&lt;u&gt;", f"<span style='background:{self.c['hl']}; color:#1b1b1b;'>") \
            .replace("&lt;/u&gt;", "</span>")
        l = QLabel(t); l.setTextFormat(Qt.RichText); l.setWordWrap(True)
        l.setStyleSheet("font-size: 14px; background: transparent;")
        return l

    def set_target_word(self, word: str):
        """Устанавливает целевое слово для корректной подсветки в секции Переводчика."""
        self._current_target_word = word

    # ------------------------------------------------------------------
    def open_at(self, x: int, y: int, sources: list[str], light: bool = False, target_word: str = ""):
        """Создаёт пустые секции в порядке источников и показывает окно у курсора."""
        self._current_target_word = target_word
        self._apply_theme(light)
        # очистка
        while self.body.count() > 1:
            it = self.body.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.sections.clear()
        self._saved = False
        self._word_rect = None          # слово ещё не найдено — привязки к нему нет
        self.set_bookmark_saved(False)
        self.set_anki_state("idle")

        titles = {"translator_pro": (_tr("Переводчик"), True),
                  "looktionary_pro": (_tr("Словарь (AI)"), True)}
        from ..dictionaries import DICTIONARIES, normalize_key
        for key in sources:
            if key in titles:
                t, sp = titles[key]
            else:
                d_id = normalize_key(key)
                d = DICTIONARIES.get_dictionary(d_id)
                t = (d.get("title") or d_id) if d else d_id
                sp = False
            sec = SourceSection(t, sp, dim=self.c["dim"], line_color=self.c["line"])
            self.sections[key] = sec
            self.body.insertWidget(self.body.count() - 1, sec)

        # позиционирование возле курсора, не вылезая за экран
        scr = QGuiApplication.screenAt(QPoint(x, y)) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        self.adjustSize()
        px = min(max(x - 40, g.left()), g.right() - self.width())
        py = y + 18
        if py + POPUP_MAX_H > g.bottom():
            py = max(g.top(), y - POPUP_MAX_H - 18)
        self._animate_in(px, py)
        QTimer.singleShot(0, self._fit_to_content)

    def _animate_in(self, px: int, py: int):
        """Появление: окно «выпрыгивает» из уменьшенной копии до полного размера
        с лёгким отскоком (OutBack) и проявлением. Масштаб делаем через
        min/max-размер окна, а НЕ через geometry — именно этот путь корректно
        перерисовывает прозрачное безрамочное окно на Windows (анимация geometry
        там часто не рендерится, окно просто «прыгает» в финал)."""
        for a in (self._anim_grp, self._resize_anim, self._close_anim):
            if a:
                a.stop()
        self._pending_pos = None
        self._closing = False
        
        # Гарантируем, что контент виден при открытии
        self.area.show()
        
        # целевая высота при фиксированной ширине
        self.setFixedWidth(POPUP_W)
        self.adjustSize()
        h = max(self.height(), 120)
        self._target_h = h
        sw, sh = int(POPUP_W * 0.20), int(h * 0.20)          # стартуем с 20% размера
        self.setMinimumSize(sw, sh); self.setMaximumSize(sw, sh)
        self.resize(sw, sh)
        self.move(px, py)
        self.setWindowOpacity(0.0)
        self.show(); self.raise_()
        self._zooming = True
        
        grp = QParallelAnimationGroup(self)
        for prop, start, end in ((b"minimumWidth", sw, POPUP_W), (b"maximumWidth", sw, POPUP_W),
                                 (b"minimumHeight", sh, h), (b"maximumHeight", sh, h)):
            a = QPropertyAnimation(self, prop)
            a.setDuration(320); a.setEasingCurve(QEasingCurve.OutBack) # Тот самый легкий отскок в конце
            a.setStartValue(start); a.setEndValue(end)
            grp.addAnimation(a)
            
        op_a = QPropertyAnimation(self, b"windowOpacity")
        op_a.setDuration(180); op_a.setEasingCurve(QEasingCurve.OutCubic)
        op_a.setStartValue(0.0); op_a.setEndValue(0.95) # Задаем прозрачность 95% при открытии
        grp.addAnimation(op_a)
        
        grp.finished.connect(self._on_appear_done)
        grp.start()
        self._anim_grp = grp        # держим ссылку, иначе GC оборвёт анимацию

    def _on_appear_done(self):
        self._zooming = False
        self.setWindowOpacity(0.95)  # Фиксируем ровно 95% прозрачности в открытом состоянии
        # возвращаем фикс-ширину, а высоту отпускаем — её подгонит _fit_to_content
        if IS_WIN11:
            self.setMinimumWidth(0); self.setMaximumWidth(16777215)
            self.setFixedWidth(POPUP_W)
            self.setMinimumHeight(0); self.setMaximumHeight(16777215)
        else:
            self.setMinimumSize(320, 120)
            self.setMaximumSize(16777215, 16777215)
            self.resize(POPUP_W, self.height())
        if self._pending_pos is not None:       # за время появления нашли слово — переезжаем
            px, py = self._pending_pos
            self._pending_pos = None
            self._animate_move(px, py)
        self._fit_to_content()

    # ------------------------------------------------- закрытие с анимацией в 0
    def close_animated(self):
        """Esc/закрытие: окно сжимается полностью в ноль и плавно гаснет, затем прячется."""
        if not self.isVisible() or self._closing:
            return
        self._closing = True
        self._zooming = True            # блокируем подгонку высоты во время закрытия
        
        for a in (self._anim_grp, self._resize_anim, self._move_anim):
            if a:
                a.stop()
                
        w, h = self.width(), self.height()
        
        # Сбрасываем ограничения, чтобы Qt разрешил сжать окно меньше размеров виджетов
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        
        # Скрываем область скролла, чтобы текст и кнопки внутри не мешали сжатию в 0px
        self.area.hide()
        
        grp = QParallelAnimationGroup(self)
        
        # Анимируем размеры строго до 0
        for prop, s, e in ((b"minimumWidth", w, 0), (b"maximumWidth", w, 0),
                           (b"minimumHeight", h, 0), (b"maximumHeight", h, 0)):
            a = QPropertyAnimation(self, prop)
            a.setDuration(220) 
            a.setEasingCurve(QEasingCurve.InBack) # Эффект "всасывания" в точку перед исчезновением
            a.setStartValue(s); a.setEndValue(e)
            grp.addAnimation(a)
            
        # Уводим прозрачность из текущего состояния (0.95) до полного нуля
        op = QPropertyAnimation(self, b"windowOpacity")
        op.setDuration(180); op.setEasingCurve(QEasingCurve.InCubic)
        op.setStartValue(self.windowOpacity()); op.setEndValue(0.0)
        grp.addAnimation(op)
        
        grp.finished.connect(self._finish_close)
        grp.start()
        self._close_anim = grp

    def _finish_close(self):
        self._closing = False
        self._zooming = False
        self.hide()                     # отсюда вылетит closed → снимется подсветка слова
        
        self.area.show()                # Возвращаем видимость контента для следующих открытий
        self.setWindowOpacity(0.95)     # Дефолтная прозрачность для будущего спавна
        self.setMinimumSize(0, 0); self.setMaximumSize(16777215, 16777215)
        self.setFixedWidth(POPUP_W)

    def scroll_by_delta(self, delta: int):
        """Прокручивает содержимое окна словаря колесиком мыши."""
        if hasattr(self, "area") and self.area.isVisible():
            bar = self.area.verticalScrollBar()
            steps = int(delta / 120.0 * 48.0)
            bar.setValue(bar.value() - steps)

    def wheelEvent(self, e):
        delta = e.angleDelta().y()
        self.scroll_by_delta(delta)
        e.accept()

    # -------------------------------------- позиционирование над/под словом
    def place_near_word(self, wx: int, wy: int, ww: int, wh: int):
        """Решает, с какой стороны от слова показать окно (там, где больше места),
        и привязывает окно к этой стороне — чтобы при дальнейшем росте под текст
        оно НИКОГДА не наползало на само слово."""
        if not self.isVisible():
            return
        self._word_rect = (wx, wy, ww, wh)
        scr = (QGuiApplication.screenAt(QPoint(wx + ww // 2, wy + wh // 2))
               or QGuiApplication.primaryScreen())
        g = scr.availableGeometry()
        gap = 16
        space_below = g.bottom() - (wy + wh + gap)
        space_above = (wy - gap) - g.top()
        # ставим снизу, если внизу влезает целиком ИЛИ места там не меньше, чем сверху
        self._placement = "below" if space_below >= min(self._target_h, space_above) \
            else "above"
        self._reposition(animate=not self._zooming)

    def _reposition(self, animate: bool):
        """Двигает окно к выбранной стороне слова под текущую/целевую высоту."""
        if not self._word_rect:
            return
        wx, wy, ww, wh = self._word_rect
        scr = (QGuiApplication.screenAt(QPoint(wx + ww // 2, wy + wh // 2))
               or QGuiApplication.primaryScreen())
        g = scr.availableGeometry()
        gap = 16
        pw = POPUP_W
        ph = self._target_h if self._zooming else self.height()
        px = min(max(wx + ww // 2 - pw // 2, g.left()), g.right() - pw)
        if self._placement == "above":
            py = (wy - gap) - ph                 # нижний край окна — над словом
        else:
            py = wy + wh + gap                   # верхний край окна — под словом
        py = max(g.top(), min(py, g.bottom() - ph))
        if self._zooming or not animate:
            self.move(px, py)                    # окно «вырастает» уже на нужном месте
            self._pending_pos = None
        else:
            self._animate_move(px, py)

    def _animate_move(self, px: int, py: int):
        if (px, py) == (self.x(), self.y()):
            return
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(160); anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(self.pos()); anim.setEndValue(QPoint(px, py))
        anim.start()
        self._move_anim = anim

    def _fit_to_content(self):
        """Подгоняет высоту окна под контент (по мере прихода переводов),
        чтобы не появлялась полоса прокрутки. Высота меняется ПЛАВНО (анимацией),
        поэтому окно «дорастает» под текст на том же окне, а не спавнит новое."""
        if self._zooming:        # во время zoom высоту не трогаем — иначе дёрнется
            return
        if self.layout():
            self.layout().invalidate()
            self.layout().activate()
        host = self.area.widget()
        if not host:
            return
        if host.layout():
            host.layout().invalidate()
            host.layout().activate()
        host.adjustSize()
        chrome = self.btn_bookmark.sizeHint().height() + 8 + 16 + 16
        target = host.sizeHint().height() + chrome + 8
        scr = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        gap = 16

        if self._word_rect:
            # есть привязка к слову — растём в сторону, выбранную в place_near_word,
            # и ограничиваем высоту местом с этой стороны, чтобы не накрыть слово
            _wx, wy, _ww, wh = self._word_rect
            if self._placement == "above":
                avail = (wy - gap) - g.top()
            else:
                avail = g.bottom() - (wy + wh + gap)
            h = min(target, POPUP_MAX_H, max(140, avail))
            if h == self.height():
                return
            if self._placement == "above":
                y = (wy - gap) - h             # нижний край прибит над словом
            else:
                y = wy + wh + gap              # верхний край прибит под словом
            y = max(g.top(), min(y, g.bottom() - h))
        else:
            # слово не найдено — окно стоит у курсора, растём вниз, не вылезая за край
            h = min(target, POPUP_MAX_H, g.height() - 40)
            if h == self.height():
                return
            y = self.y()
            if y + h > g.bottom():
                y = max(g.top(), g.bottom() - h)

        if IS_WIN11:
            self._animate_resize(h, y)
        else:
            if self._resize_anim:
                self._resize_anim.stop()
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.setGeometry(self.x(), y, self.width(), h)
            if self.layout():
                self.layout().invalidate()
                self.layout().activate()

    def _animate_resize(self, h: int, y: int):
        """Плавно тянет высоту окна (через min/maxHeight) и при необходимости
        подвигает его, чтобы не вылезти за нижний край экрана."""
        if self._resize_anim:
            self._resize_anim.stop()
        cur = self.height()
        grp = QParallelAnimationGroup(self)
        for prop in (b"minimumHeight", b"maximumHeight"):
            a = QPropertyAnimation(self, prop)
            a.setDuration(180); a.setEasingCurve(QEasingCurve.OutCubic)
            a.setStartValue(cur); a.setEndValue(h)
            grp.addAnimation(a)
        if y != self.y():
            ap = QPropertyAnimation(self, b"pos")
            ap.setDuration(180); ap.setEasingCurve(QEasingCurve.OutCubic)
            ap.setStartValue(self.pos()); ap.setEndValue(QPoint(self.x(), y))
            grp.addAnimation(ap)
        grp.start()
        self._resize_anim = grp        # держим ссылку, иначе GC оборвёт анимацию

    # ----------------------------------------------- заполнение секций
    def fill_translator(self, translation_html: str):
        sec = self.sections.get("translator_pro")
        if not sec:
            return

        target_word = getattr(self, "_current_target_word", "")
        # Если строка содержит исходное предложение и перевод, разделённые двоеточием
        if ":" in translation_html or "：" in translation_html:
            delim = ":" if ":" in translation_html else "："
            orig_part, trans_part = translation_html.split(delim, 1)
            # Убираем ложные <u> теги с части перевода после двоеточия
            trans_part = trans_part.replace("<u>", "").replace("</u>", "")
            orig_part = orig_part.replace("<u>", "").replace("</u>", "")
            # Оборачиваем именно целевое слово (word_in_text) в исходном предложении
            if target_word and target_word in orig_part:
                orig_part = orig_part.replace(target_word, f"<u>{target_word}</u>", 1)
            translation_html = f"{orig_part}{delim}{trans_part}"
        elif target_word and target_word in translation_html:
            clean = translation_html.replace("<u>", "").replace("</u>", "")
            translation_html = clean.replace(target_word, f"<u>{target_word}</u>", 1)

        if CONFIG.get("translator_pro")["hide_in_dict_mode"]:
            sp = Spoiler(translation_html.replace("<u>", "").replace("</u>", ""),
                         self.c["spoiler"])
            sec.add(sp)
        else:
            sec.add(self._highlighted(translation_html))
        QTimer.singleShot(0, self._fit_to_content)

    def fill_looktionary(self, data: dict):
        sec = self.sections.get("looktionary_pro")
        if not sec:
            return
        # слово + озвучка + уровень + транскрипция
        head = QHBoxLayout(); head.setSpacing(10)
        w = QLabel(data.get("dict_form", "")); w.setStyleSheet("font-size: 24px; font-weight: 700;")
        head.addWidget(w)
        for speed in ("🔊", "🔉"):
            b = QPushButton(speed); b.setObjectName("IconBtn")
            b.clicked.connect(lambda _, t=data.get("dict_form", ""),
                              l=data.get("src_lang", "en"): tts.speak(t, l))
            head.addWidget(b)
        head.addStretch(1)
        hw = QWidget(); hw.setLayout(head)
        sec.add(hw)
        sub = QHBoxLayout(); sub.setSpacing(8)
        if data.get("level"):
            sub.addWidget(Badge(data["level"]))
        if data.get("transcription"):
            tr = QLabel(data["transcription"])
            tr.setStyleSheet(f"color: {self.c['dim']}; background: transparent; font-size: 12px;")
            sub.addWidget(tr)
        sub.addStretch(1)
        sw = QWidget(); sw.setLayout(sub)
        sec.add(sw)
        # пометы-теги
        if data.get("pos_tags"):
            tags = QHBoxLayout(); tags.setSpacing(6)
            for t in data["pos_tags"][:4]:
                l = QLabel(t)
                l.setStyleSheet(f"background: {self.c['tag_bg']}; color: {self.c['tag_text']}; "
                                f"border: 1px solid {self.c['tag_brd']}; "
                                "border-radius: 3px; padding: 2px 7px; font-size: 11px;")
                tags.addWidget(l)
            tags.addStretch(1)
            tw = QWidget(); tw.setLayout(tags)
            sec.add(tw)
        # определение
        if data.get("definition"):
            d = QLabel(data["definition"]); d.setWordWrap(True)
            d.setStyleSheet("font-size: 14px; background: transparent;")
            sec.add(d)
        # перевод слова (флаг + слово)
        if data.get("word_translation"):
            lang = CONFIG.get("looktionary_pro")["word_trans_lang"]
            row = QHBoxLayout(); row.setSpacing(8)
            row.addWidget(flag_label(lang, 18))
            if CONFIG.get("looktionary_pro")["hide_word_translation"]:
                row.addWidget(Spoiler(data["word_translation"], self.c["spoiler"]))
            else:
                t = QLabel(data["word_translation"]); t.setStyleSheet("font-weight: 600;")
                row.addWidget(t)
            row.addStretch(1)
            rw = QWidget(); rw.setLayout(row)
            sec.add(rw)
        # синонимы
        if data.get("synonyms"):
            s = QLabel(f"{_tr('Синонимы')}: <i>" + ", ".join(map(html.escape, data["synonyms"])) + "</i>")
            s.setTextFormat(Qt.RichText); s.setWordWrap(True)
            s.setStyleSheet(f"color: {self.c['dim']}; background: transparent; font-size: 12px;")
            sec.add(s)
        # использованный контекст (сворачиваемый)
        if data.get("context_translation"):
            inner = QWidget(); iv = QVBoxLayout(inner)
            iv.addWidget(self._highlighted(data["context_translation"]))
            coll = Collapsible(_tr("Использованный контекст"), inner)
            coll.setStyleSheet(
                f"QFrame {{ background: {self.c['coll_bg']}; border-radius: 4px; }} "
                f"QPushButton {{ background: transparent; color: {self.c['text']}; "
                "text-align: left; padding: 13px 16px; font-size: 13px; }")
            sec.add(coll)
        QTimer.singleShot(0, self._fit_to_content)

    def fill_offline_dict(self, key: str, entries: list[dict], replace: bool = False):
        sec = self.sections.get(key)
        if not sec:
            return
        if replace:
            sec.clear_body()
        if not entries:
            if not replace:
                sec.fail(_tr("Нет статьи в этом словаре."))
                QTimer.singleShot(0, self._fit_to_content)
            return

        for idx, entry in enumerate(entries, 1):
            w = YomitanSenseWidget(idx, entry, on_toggle=self._fit_to_content)
            sec.add(w)

        QTimer.singleShot(0, self._fit_to_content)

    def fail_source(self, key: str, msg: str):
        if key in self.sections:
            self.sections[key].fail(msg)
        QTimer.singleShot(0, self._fit_to_content)

    # ------------------------------------------------------------------
    def set_anki_visible(self, visible: bool):
        """Показывает или скрывает кнопку Anki (скрыта, если нет подключения к AnkiConnect)."""
        self.btn_anki.setVisible(visible)

    def set_bookmark_saved(self, saved: bool):
        """Обновляет состояние кнопки закладки личного словаря."""
        self._saved = saved
        if saved:
            self.btn_bookmark.setText("✅")
            self.btn_bookmark.setToolTip(_tr("Сохранено в личный словарь (нажмите, чтобы удалить)"))
        else:
            self.btn_bookmark.setText("🔖")
            self.btn_bookmark.setToolTip(_tr("Сохранить слово в личный словарь"))

    def set_anki_state(self, state: str, message: str = ""):
        """Обновляет статус кнопки Anki:
        idle -> '＋' (зеленый плюсик в стиле Yomitan)
        busy -> '⏳' (добавляется)
        added -> '✓' (добавлено в Anki)
        exists -> '✓' (уже есть в Anki)
        error -> '⚠' (ошибка)
        """
        self._anki_state = state
        if state == "idle":
            self.btn_anki.setText("＋")
            self.btn_anki.setEnabled(True)
            self.btn_anki.setToolTip(_tr("Добавить слово в Anki"))
            self.btn_anki.setStyleSheet(
                "QPushButton { color: #22c55e; font-size: 17px; font-weight: bold; background: transparent; border: none; border-radius: 4px; padding: 0 4px; } "
                "QPushButton:hover { background: rgba(34, 197, 94, 0.18); color: #4ade80; }"
            )
        elif state == "busy":
            self.btn_anki.setText("⏳")
            self.btn_anki.setEnabled(False)
            self.btn_anki.setToolTip(_tr("Добавление в Anki..."))
            self.btn_anki.setStyleSheet(
                "QPushButton { color: #f59e0b; font-size: 14px; background: transparent; border: none; padding: 0 4px; }"
            )
        elif state == "added":
            self.btn_anki.setText("✓")
            self.btn_anki.setEnabled(False)
            self.btn_anki.setToolTip(message or _tr("Добавлено в Anki"))
            self.btn_anki.setStyleSheet(
                "QPushButton { color: #22c55e; font-size: 16px; font-weight: bold; background: transparent; border: none; border-radius: 4px; padding: 0 4px; } "
                "QPushButton:hover { background: rgba(34, 197, 94, 0.18); }"
            )
        elif state == "exists":
            self.btn_anki.setText("✓")
            self.btn_anki.setEnabled(True)
            self.btn_anki.setToolTip(message or _tr("Слово уже есть в Anki (нажмите для повторного добавления)"))
            self.btn_anki.setStyleSheet(
                "QPushButton { color: #3b82f6; font-size: 16px; font-weight: bold; background: transparent; border: none; border-radius: 4px; padding: 0 4px; } "
                "QPushButton:hover { background: rgba(59, 130, 246, 0.18); }"
            )
        elif state == "disconnected":
            self.btn_anki.setText("＋")
            self.btn_anki.setEnabled(True)
            self.btn_anki.setToolTip(message or _tr("Anki: нет подключения к AnkiConnect (нажмите для проверки)"))
            self.btn_anki.setStyleSheet(
                "QPushButton { color: #888888; font-size: 17px; font-weight: bold; background: transparent; border: none; border-radius: 4px; padding: 0 4px; } "
                "QPushButton:hover { background: rgba(255, 255, 255, 0.12); color: #bbbbbb; }"
            )
        elif state == "error":
            self.btn_anki.setText("⚠")
            self.btn_anki.setEnabled(True)
            self.btn_anki.setToolTip(f"{_tr('Ошибка Anki')}: {message}" if message else _tr("Ошибка Anki"))
            self.btn_anki.setStyleSheet(
                "QPushButton { color: #ef4444; font-size: 15px; font-weight: bold; background: transparent; border: none; border-radius: 4px; padding: 0 4px; } "
                "QPushButton:hover { background: rgba(239, 68, 68, 0.18); }"
            )

    def _on_anki_click(self):
        self.set_anki_state("busy")
        self.anki_clicked.emit()

    def _on_bookmark(self):
        self.bookmark_clicked.emit()

    def hideEvent(self, e):
        self.closed.emit()
        super().hideEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_animated()
        super().keyPressEvent(e)