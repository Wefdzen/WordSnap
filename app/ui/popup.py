"""Всплывающее окно режима словаря: появляется у курсора, показывает секции
источников в настроенном порядке (Переводчик / Looktionary / Oxford-слот)."""
import html

from PySide6.QtCore import (Qt, Signal, QPoint, QRect, QPropertyAnimation,
                            QParallelAnimationGroup, QEasingCurve, QTimer)
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QFrame, QScrollArea, QApplication)

from ..config import CONFIG
from .. import tts
from .widgets import Badge, Hairline, Collapsible, flag_label
from .theme import ACCENT, BG_PANEL, BORDER, TEXT_DIM, BG_CARD

# жёлто-оливковая подсветка слова (как в оригинале Lookupper)
HILITE = "#7f801e"
POPUP_W = 580   # ширина окна перевода (как в оригинале)
POPUP_MAX_H = 520  # максимальная высота — дальше появляется прокрутка


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
        self._loading = QLabel("…  загрузка")
        self._loading.setStyleSheet(f"color: {dim}; background: transparent;")
        self.body.addWidget(self._loading)

    def clear_loading(self):
        if self._loading:
            self._loading.deleteLater()
            self._loading = None

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
    l.setStyleSheet("font-size: 13.5px;")
    return l


class DictionaryPopup(QWidget):
    bookmark_clicked = Signal()
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        outer = QVBoxLayout(self); outer.setContentsMargins(8, 8, 8, 8)
        self.card = QFrame(); self.card.setObjectName("PopupCard")
        self._apply_theme(light=False)
        outer.addWidget(self.card)
        cv = QVBoxLayout(self.card); cv.setContentsMargins(0, 0, 0, 0); cv.setSpacing(0)

        # закладка (сохранить слово)
        topbar = QHBoxLayout(); topbar.setContentsMargins(16, 8, 10, 0)
        topbar.addStretch(1)
        self.btn_bookmark = QPushButton("🔖")
        self.btn_bookmark.setObjectName("IconBtn")
        self.btn_bookmark.setToolTip("Сохранить слово в личный словарь")
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

    # ------------------------------------------------------------------
    def open_at(self, x: int, y: int, sources: list[str], light: bool = False):
        """Создаёт пустые секции в порядке источников и показывает окно у курсора."""
        self._apply_theme(light)
        # очистка
        while self.body.count() > 1:
            it = self.body.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.sections.clear()
        self._saved = False
        self._word_rect = None          # слово ещё не найдено — привязки к нему нет
        self.btn_bookmark.setText("🔖")

        titles = {"translator_pro": ("Переводчик", True),
                  "looktionary_pro": ("Looktionary", True),
                  "oxford": ("Oxford", False)}
        for key in sources:
            t, sp = titles[key]
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
        self.setMinimumWidth(0); self.setMaximumWidth(16777215)
        self.setFixedWidth(POPUP_W)
        self.setMinimumHeight(0); self.setMaximumHeight(16777215)
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
        host = self.area.widget()
        if not host:
            return
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
        self._animate_resize(h, y)

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
            s = QLabel("Синонимы: <i>" + ", ".join(map(html.escape, data["synonyms"])) + "</i>")
            s.setTextFormat(Qt.RichText); s.setWordWrap(True)
            s.setStyleSheet(f"color: {self.c['dim']}; background: transparent; font-size: 12px;")
            sec.add(s)
        # использованный контекст (сворачиваемый)
        if data.get("context_translation"):
            inner = QWidget(); iv = QVBoxLayout(inner)
            iv.addWidget(self._highlighted(data["context_translation"]))
            coll = Collapsible("Использованный контекст", inner)
            coll.setStyleSheet(
                f"QFrame {{ background: {self.c['coll_bg']}; border-radius: 4px; }} "
                f"QPushButton {{ background: transparent; color: {self.c['text']}; "
                "text-align: left; padding: 13px 16px; font-size: 13px; }")
            sec.add(coll)
        QTimer.singleShot(0, self._fit_to_content)

    def fill_oxford(self, data: dict | None):
        sec = self.sections.get("oxford")
        if not sec:
            return
        if not data:
            sec.fail("Нет статьи в офлайн-словаре.")
            QTimer.singleShot(0, self._fit_to_content)
            return
        head = QLabel(f"<b>{html.escape(data['word'])}</b>  "
                      f"<span style='color:{self.c['dim']}'>{html.escape(data.get('phonetic',''))}</span>")
        head.setTextFormat(Qt.RichText)
        sec.add(head)
        for s in data.get("senses", []):
            l = QLabel(f"<i>{html.escape(s['pos'])}</i> — {html.escape(s['def'])}")
            l.setTextFormat(Qt.RichText); l.setWordWrap(True)
            sec.add(l)
        QTimer.singleShot(0, self._fit_to_content)

    def fail_source(self, key: str, msg: str):
        if key in self.sections:
            self.sections[key].fail(msg)
        QTimer.singleShot(0, self._fit_to_content)

    # ------------------------------------------------------------------
    def _on_bookmark(self):
        self._saved = True
        self.btn_bookmark.setText("✅")
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