"""Переиспользуемые виджеты: тумблер Win11, строки настроек, сворачиваемые секции,
круглые иконки флагов (как в оригинале — эмодзи-флаги Windows не рендерит),
загрузка SVG-иконок из assets/svg/ с перекраской под цвет интерфейса."""
import os

from PySide6.QtCore import (Qt, QSize, QRectF, QPointF, Signal, QPropertyAnimation,
                            Property, QEasingCurve)
from PySide6.QtGui import QPainter, QColor, QFont, QPixmap, QPainterPath, QPen, QIcon
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QVBoxLayout,
                               QLabel, QWidget, QSizePolicy, QPushButton, QRadioButton)

from ..config import app_dir
from .theme import ACCENT, BG_CARD, BORDER, TEXT_DIM, TEXT, ICON
from .i18n import t

SVG_DIR = os.path.join(app_dir(), "assets", "svg")
_svg_cache: dict[tuple, QIcon] = {}

def svg_icon(name: str, color: str = ICON, size: int = 16) -> QIcon:
    """SVG из assets/svg/, перекрашенный в нужный цвет (по умолчанию — цвет иконок
    текущей темы: белый в тёмной, чёрный в светлой)."""
    key = (name, color, size)
    if key in _svg_cache:
        return _svg_cache[key]
    renderer = QSvgRenderer(os.path.join(SVG_DIR, name))
    if not renderer.isValid():
        return QIcon()
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); renderer.render(p); p.end()
    # перекрашиваем силуэт иконки в нужный цвет
    tinted = QPixmap(size, size); tinted.fill(Qt.transparent)
    p = QPainter(tinted)
    p.drawPixmap(0, 0, pm)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(tinted.rect(), QColor(color))
    p.end()
    icon = QIcon(tinted)
    _svg_cache[key] = icon
    return icon

def svg_png(name: str, color: str = ICON, size: int = 16) -> str:
    """Рендерит SVG в PNG-файл (для использования в QSS image: url(...)) и кэширует.
    Возвращает абсолютный путь с прямыми слешами (как любит Qt-stylesheet)."""
    cache_dir = os.path.join(SVG_DIR, "_png")
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{os.path.splitext(name)[0]}_{color.lstrip('#')}_{size}.png")
    if not os.path.exists(path):
        pm = svg_icon(name, color, size).pixmap(size, size)
        pm.save(path, "PNG")
    return path.replace("\\", "/")

# Цвета флагов: ("h"=горизонтальные/"v"=вертикальные полосы, [цвета сверху-вниз/слева-направо])
_FLAG_BANDS = {
    "ru": ("h", ["#ffffff", "#0039a6", "#d52b1e"]),
    "de": ("h", ["#1a1a1a", "#dd0000", "#ffce00"]),
    "fr": ("v", ["#0055a4", "#ffffff", "#ef4135"]),
    "es": ("h", ["#aa151b", "#f1bf00", "#aa151b"]),
    "uk": ("h", ["#0057b7", "#ffd700"]),
}
_flag_cache: dict[tuple, QPixmap] = {}

def flag_pixmap(lang: str, d: int = 18) -> QPixmap:
    """Круглая иконка флага языка нужного диаметра (рисуется, не эмодзи)."""
    key = (lang, d)
    if key in _flag_cache:
        return _flag_cache[key]
    pm = QPixmap(d, d); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath(); clip.addEllipse(0.5, 0.5, d - 1, d - 1)
    p.setClipPath(clip)

    if lang in _FLAG_BANDS:
        orient, colors = _FLAG_BANDS[lang]
        n = len(colors)
        for i, c in enumerate(colors):
            if orient == "h":
                p.fillRect(QRectF(0, d * i / n, d, d / n + 1), QColor(c))
            else:
                p.fillRect(QRectF(d * i / n, 0, d / n + 1, d), QColor(c))
    elif lang == "ja":
        p.fillRect(QRectF(0, 0, d, d), QColor("#ffffff"))
        p.setBrush(QColor("#bc002d")); p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(d * 0.28, d * 0.28, d * 0.44, d * 0.44))
    elif lang == "ko":
        p.fillRect(QRectF(0, 0, d, d), QColor("#ffffff"))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#cd2e3a")); p.drawPie(QRectF(d*0.3, d*0.3, d*0.4, d*0.4), 0, 180*16)
        p.setBrush(QColor("#0047a0")); p.drawPie(QRectF(d*0.3, d*0.3, d*0.4, d*0.4), 180*16, 180*16)
    elif lang == "zh":
        p.fillRect(QRectF(0, 0, d, d), QColor("#de2910"))
        p.setPen(Qt.NoPen); p.setBrush(QColor("#ffde00"))
        f = QFont("Segoe UI"); f.setPixelSize(max(6, int(d * 0.55))); f.setBold(True); p.setFont(f)
        p.setPen(QColor("#ffde00"))
        p.drawText(QRectF(0, 0, d, d), Qt.AlignCenter, "★")
    else:  # en/us и прочее — звёздно-полосатый (упрощённо)
        for i in range(7):
            p.fillRect(QRectF(0, d * i / 7, d, d / 7 + 1),
                       QColor("#b22234" if i % 2 == 0 else "#ffffff"))
        p.fillRect(QRectF(0, 0, d * 0.42, d * 0.46), QColor("#3c3b6e"))

    # тонкая рамка по кругу
    p.setClipping(False)
    p.setPen(QPen(QColor(0, 0, 0, 90), 1)); p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(0.5, 0.5, d - 1, d - 1))
    p.end()
    _flag_cache[key] = pm
    return pm

def flag_label(lang: str, d: int = 18) -> QLabel:
    lbl = QLabel(); lbl.setPixmap(flag_pixmap(lang, d))
    lbl.setFixedSize(d, d)
    return lbl

def flag_icon(lang: str, d: int = 16) -> QIcon:
    return QIcon(flag_pixmap(lang, d))

class ToggleSwitch(QAbstractButton):
    """Тумблер в стиле Windows 11 с подписью Вкл./Откл."""
    def __init__(self, checked=False, with_label=True, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.with_label = with_label
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knobPos", self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def getKnobPos(self): return self._pos
    def setKnobPos(self, v): self._pos = v; self.update()
    knobPos = Property(float, getKnobPos, setKnobPos)

    def sizeHint(self):
        return QSize(96 if self.with_label else 44, 22)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = 40, 20
        x0 = self.width() - w - 2
        y0 = (self.height() - h) // 2
        if self.with_label:
            p.setPen(QColor("#ffffff"))
            f = QFont(self.font()); f.setPixelSize(12)  # пиксели, чтобы не ловить point-size <= 0
            p.setFont(f)
            p.drawText(0, 0, x0 - 10, self.height(), Qt.AlignRight | Qt.AlignVCenter,
                       t("Вкл.") if self.isChecked() else t("Откл."))
        on = QColor(ACCENT)
        track = QColor(on) if self._pos > 0.5 else QColor("transparent")
        p.setPen(QColor(BORDER) if self._pos <= 0.5 else on)
        p.setBrush(track if self._pos > 0.5 else QColor("transparent"))
        p.drawRoundedRect(x0, y0, w, h, h / 2, h / 2)
        # ручка
        kx = x0 + 4 + self._pos * (w - 12 - 8)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#000000") if self._pos > 0.5 else QColor("#cfcfcf"))
        p.drawEllipse(int(kx), y0 + 4, 12, 12)

class FluentRadio(QRadioButton):
    """Аккуратный радио-индикатор в стиле Windows 11: тонкое кольцо, а при выборе —
    акцентное кольцо с растущей точкой по центру (с лёгкой анимацией-«пружинкой»).
    Заменяет уродливый стандартный кружок QRadioButton."""
    _D = 20        # диаметр индикатора
    _GAP = 12      # отступ от индикатора до текста

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False
        self._dot = 1.0 if self.isChecked() else 0.0
        self._anim = QPropertyAnimation(self, b"dotPos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutBack)
        self.toggled.connect(self._animate)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def getDot(self): return self._dot
    def setDot(self, v): self._dot = v; self.update()
    dotPos = Property(float, getDot, setDot)

    def enterEvent(self, e): self._hover = True; self.update(); super().enterEvent(e)
    def leaveEvent(self, e): self._hover = False; self.update(); super().leaveEvent(e)

    def hitButton(self, pos):
        return self.rect().contains(pos)          # клик по всей строке переключает

    def sizeHint(self):
        s = super().sizeHint()
        return QSize(s.width() + self._D, max(s.height(), self._D + 6))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        d = self._D
        cx, cy = 1 + d / 2, self.height() / 2
        outer = d / 2 - 1
        # кольцо: акцент при выборе/наведении, иначе серое
        ring = QColor(ACCENT) if (self.isChecked() or self._hover) else QColor("#8a8a8a")
        pen = QPen(ring); pen.setWidthF(2.0)
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), outer, outer)
        # центральная точка — «дырка» из фона между ней и кольцом, как в Win11
        if self._dot > 0.01:
            r = (d * 0.21 + (d * 0.05 if self._hover else 0)) * self._dot
            p.setPen(Qt.NoPen); p.setBrush(QColor(ACCENT))
            p.drawEllipse(QPointF(cx, cy), r, r)
        # текст рядом с индикатором
        p.setPen(QColor(TEXT))
        tx = d + self._GAP
        p.drawText(QRectF(tx, 0, self.width() - tx, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()


class SettingRow(QFrame):
    """Строка настройки: иконка, заголовок, подзаголовок, виджет справа."""
    def __init__(self, icon: str, title: str, subtitle: str = "", right: QWidget | None = None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("SettingRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(14)
        ic = QLabel()
        ic.setAlignment(Qt.AlignCenter)    # иконка по центру своей колонки
        if icon.endswith(".svg"):          # имя SVG-файла из assets/svg/
            ic.setPixmap(svg_icon(icon, ICON, 18).pixmap(18, 18))
        else:                              # эмодзи / символ
            ic.setText(icon); ic.setStyleSheet("font-size: 17px;")
        ic.setFixedSize(26, 26)
        lay.addWidget(ic, 0, Qt.AlignVCenter)   # всегда по центру блока (а не у заголовка)
        col = QVBoxLayout(); col.setSpacing(2)
        t = QLabel(title); t.setWordWrap(True)
        col.addWidget(t)
        if subtitle:
            s = QLabel(subtitle); s.setObjectName("Dim"); s.setWordWrap(True)
            col.addWidget(s)
        lay.addLayout(col, 1)
        if right is not None:
            lay.addWidget(right, 0, Qt.AlignVCenter)

class Collapsible(QFrame):
    """Сворачиваемая секция («Лингвистическая информация», «Детали источника»)."""
    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingRow")
        self._content = content
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        self.btn = QPushButton()
        self.btn.setObjectName("Flat")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setStyleSheet("text-align: left; padding: 13px 16px; font-size: 13px;")
        self._title = title
        lay.addWidget(self.btn)
        content.setVisible(False)
        content.setContentsMargins(16, 0, 16, 12)
        lay.addWidget(content)
        self.btn.clicked.connect(self.toggle)
        self._sync()

    def toggle(self):
        self._content.setVisible(not self._content.isVisible())
        self._sync()

    def _sync(self):
        arrow = "⌃" if self._content.isVisible() else "⌄"
        self.btn.setText(f"{self._title}")
        # стрелка справа через layout-трюк не нужна — добавим в текст
        self.btn.setText(self._title + "   " + arrow)

class Badge(QLabel):
    """Бейдж уровня CEFR с цветом по уровню: A — серый, B1 — зелёный,
    B2 — синий, C1 — оранжевый, C2 — красный."""
    LEVEL_COLORS = {
        "A0": "#8a8f98", "A1": "#8a8f98", "A2": "#8a8f98",   # серый
        "B1": "#4caf50",                                      # зелёный
        "B2": "#3a8eff",                                      # синий
        "C1": "#f0954e",                                      # оранжевый
        "C2": "#e0564b",                                      # красный
    }
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        color = self.LEVEL_COLORS.get((text or "").strip().upper(), "#8a8f98")
        self.setStyleSheet(f"""
            background: {color}; border: none; border-radius: 3px;
            color: #ffffff; font-size: 10px; font-weight: 700; padding: 1px 6px;
        """)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

class Hairline(QFrame):
    def __init__(self, parent=None, color: str = BORDER):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background: {color};")

class InfoBanner(QFrame):
    """Баннер «Некоторые данные отсутствуют или неполные»."""
    action = Signal()
    def __init__(self, text: str, button_text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        lay = QHBoxLayout(self); lay.setContentsMargins(14, 12, 14, 12); lay.setSpacing(12)
        ic = QLabel("ⓘ"); ic.setStyleSheet(f"color: {ACCENT}; font-size: 16px;")
        lay.addWidget(ic, 0, Qt.AlignTop)
        col = QVBoxLayout(); col.setSpacing(8)
        col.addWidget(QLabel(text))
        btn = QPushButton(button_text)
        btn.clicked.connect(self.action.emit)
        col.addWidget(btn, 0, Qt.AlignLeft)
        lay.addLayout(col, 1)
