"""Главное окно: кастомный заголовок с вкладками (Слова / Переводчик и словари /
Настройки) и системными кнопками."""
import os
import sys

from PySide6.QtCore import Qt, QPoint, QSize, QRect, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QCursor, QPen
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QStackedWidget, QFrame, QMessageBox, QSizeGrip)

from ..config import app_dir
from .theme import QSS, ACCENT, ICON, BG
from .i18n import t
from .words_page import WordsPage
from .dicts_page import DictsPage
from .settings_page import SettingsPage
from .widgets import svg_png

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

ASSETS_DIR = os.path.join(app_dir(), "assets")

def make_app_icon() -> QIcon:
    # пользовательская иконка из assets/, если положена
    for name in ("icon.png", "icon.ico", "logo.png"):
        p = os.path.join(ASSETS_DIR, name)
        if os.path.exists(p):
            ic = QIcon(p)
            if not ic.isNull():
                return ic
    # иначе — стандартная нарисованная иконка
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#f5d061")); p.setPen(Qt.NoPen)
    p.drawRoundedRect(6, 10, 52, 44, 8, 8)
    p.setBrush(QColor(ACCENT))
    p.drawRoundedRect(14, 4, 28, 20, 6, 6)
    p.setPen(QColor("#003a57"))
    f = QFont("Segoe UI", 11, QFont.Bold); p.setFont(f)
    p.drawText(pm.rect().adjusted(0, 8, 0, 0), Qt.AlignCenter, "L")
    p.end()
    return QIcon(pm)

def _winctrl_icon(kind: str, color: str = ICON) -> QIcon:
    """Стандартные иконки управления окном (минимизация/восстановление/
    максимизация/закрытие), как в заголовке окон Windows 11."""
    size = 10
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing, False)
    pen = QPen(QColor(color)); pen.setWidth(1)
    p.setPen(pen)
    if kind == "min":
        p.drawLine(0, size - 1, size - 1, size - 1)
    elif kind == "max":
        p.drawRect(0, 0, size - 1, size - 1)
    elif kind == "restore":
        p.drawRect(2, 0, size - 3, size - 3)
        p.fillRect(0, 2, size - 3, size - 3, QColor(BG))
        p.drawRect(0, 2, size - 3, size - 3)
    elif kind == "close":
        p.drawLine(0, 0, size - 1, size - 1)
        p.drawLine(0, size - 1, size - 1, 0)
    p.end()
    return QIcon(pm)


class TitleBar(QFrame):
    def __init__(self, window: "MainWindow"):
        super().__init__(window)
        self.win = window
        self.setObjectName("TitleBar")
        self.setFixedHeight(44)
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 0, 0, 0); lay.setSpacing(4)

        logo = QLabel(); logo.setPixmap(make_app_icon().pixmap(22, 22))
        lay.addWidget(logo); lay.addSpacing(14)

        self.tabs = []
        for i, name in enumerate((t("Слова"), t("Переводчик и словари"), t("Настройки"))):
            host = QWidget(); hv = QVBoxLayout(host)
            hv.setContentsMargins(8, 0, 8, 5); hv.setSpacing(0)
            b = QPushButton(name); b.setObjectName("TabButton")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, idx=i: self.win.set_page(idx))
            hv.addWidget(b)
            lay.addWidget(host)
            self.tabs.append(b)
        lay.addStretch(1)
        lay.addSpacing(16)

        # «бегущая» полоска-индикатор активной вкладки — едет под выбранную
        self.underline = QFrame(self)
        self.underline.setObjectName("TabUnderline")
        self.underline.setFixedHeight(3)
        self.underline.setFixedWidth(26)
        self._underline_anim = QPropertyAnimation(self.underline, b"geometry", self)
        self._underline_anim.setDuration(220)
        self._underline_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.underline.hide()

        self.btn_max = None
        for kind, slot in (("min", window.showMinimized),
                           ("max", self._toggle_max),
                           ("close", window.close)):
            b = QPushButton(); b.setObjectName("WinBtn")
            b.setIcon(_winctrl_icon(kind)); b.setIconSize(QSize(10, 10))
            if kind == "close":
                b.setStyleSheet("#WinBtn:hover { background: #c42b1c; }")
            if kind == "max":
                self.btn_max = b
            b.clicked.connect(slot)
            lay.addWidget(b)
        self._drag: QPoint | None = None

    def set_active(self, idx: int):
        for i, b in enumerate(self.tabs):
            b.setProperty("active", "true" if i == idx else "false")
            b.style().unpolish(b); b.style().polish(b)
        self._move_underline(idx, animate=self.underline.isVisible())

    def _move_underline(self, idx: int, animate: bool):
        b = self.tabs[idx]
        cx = b.mapTo(self, QPoint(0, 0)).x() + b.width() // 2
        y = self.height() - self.underline.height() - 2
        target = QRect(cx - self.underline.width() // 2, y,
                        self.underline.width(), self.underline.height())
        self.underline.show()
        self._underline_anim.stop()
        if animate:
            self._underline_anim.setStartValue(self.underline.geometry())
            self._underline_anim.setEndValue(target)
            self._underline_anim.start()
        else:
            self.underline.setGeometry(target)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        for i, b in enumerate(self.tabs):
            if b.property("active") == "true":
                self._move_underline(i, animate=False)
                break

    def _toggle_max(self):
        # isMaximized() не сразу обновляется при WS_THICKFRAME без рамки —
        # храним состояние сами, чтобы не требовалось 2 клика для восстановления
        if self.win._is_max:
            self.win.showNormal()
            self.win._is_max = False
            self.btn_max.setIcon(_winctrl_icon("max"))
        else:
            self.win.showMaximized()
            self.win._is_max = True
            self.btn_max.setIcon(_winctrl_icon("restore"))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag and not self.win.isMaximized():
            self.win.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._toggle_max()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lookupper")
        self._is_max = False
        self.setWindowIcon(make_app_icon())
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.resize(1280, 760)
        self.setMinimumSize(900, 560)  # чтобы при уменьшении не ломалась вёрстка
        # стрелка выпадающих списков — из angle-small-down.svg
        arrow = svg_png("angle-small-down.svg", "#b0b0b0", 12)
        self.setStyleSheet(QSS + f"\nQComboBox::down-arrow {{ image: url('{arrow}'); }}")

        root = QWidget(); root.setObjectName("Root")
        self.setCentralWidget(root)
        self._root = root
        v = QVBoxLayout(root); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        self.titlebar = TitleBar(self)
        v.addWidget(self.titlebar)

        self.stack = QStackedWidget()
        self.words_page = WordsPage()
        self.dicts_page = DictsPage()
        self.settings_page = SettingsPage()
        for p in (self.words_page, self.dicts_page, self.settings_page):
            self.stack.addWidget(p)
        v.addWidget(self.stack, 1)
        self.set_page(0)
        QTimer.singleShot(0, lambda: self.titlebar._move_underline(0, animate=False))

        # «уголки» внизу — запасной способ ресайза (на не-Windows)
        self._grips = [QSizeGrip(root) for _ in range(2)]
        for g in self._grips:
            g.setFixedSize(16, 16)
            g.setStyleSheet("background: transparent;")
            g.raise_()

        # на Windows — нативный ресайз за ЛЮБОЙ край и угол (в т.ч. сверху-слева/справа)
        if sys.platform == "win32":
            self._enable_native_resize()

    _BORDER = 6  # ширина зоны захвата у краёв окна

    def _enable_native_resize(self):
        """Добавляет окну стиль WS_THICKFRAME — Windows разрешает тянуть за края,
        а WM_NCCALCSIZE убирает рамку, чтобы окно осталось безрамочным."""
        try:
            hwnd = int(self.winId())
            GWL_STYLE, WS_THICKFRAME = -16, 0x00040000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_THICKFRAME)
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)  # FRAMECHANGED|NOMOVE|NOSIZE|NOZORDER
        except Exception as e:
            print("native resize error:", e)

    def nativeEvent(self, eventType, message):
        if sys.platform == "win32" and eventType == "windows_generic_MSG":
            try:
                msg = wintypes.MSG.from_address(int(message))
            except Exception:
                return super().nativeEvent(eventType, message)
            if msg.message == 0x0083 and msg.wParam:      # WM_NCCALCSIZE — убираем рамку
                return True, 0
            if msg.message == 0x0084:                     # WM_NCHITTEST — какой край под курсором
                p = self.mapFromGlobal(QCursor.pos())
                b, w, h = self._BORDER, self.width(), self.height()
                left, right = p.x() < b, p.x() >= w - b
                top, bottom = p.y() < b, p.y() >= h - b
                code = (13 if top and left else 14 if top and right else
                        16 if bottom and left else 17 if bottom and right else
                        10 if left else 11 if right else 12 if top else 15 if bottom else 0)
                if code:
                    return True, code                     # HTTOPLEFT..HTBOTTOM
        return super().nativeEvent(eventType, message)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_grips"):
            r = self._root.rect()
            self._grips[0].move(0, r.height() - 16)               # нижний-левый
            self._grips[1].move(r.width() - 16, r.height() - 16)  # нижний-правый
            for g in self._grips:
                g.raise_()

    def set_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self.titlebar.set_active(idx)
        if idx == 0:
            self.words_page.reload()
