"""Главное окно: кастомный заголовок с вкладками (Слова / Переводчик и словари /
Настройки) и системными кнопками."""
import os
import sys

from PySide6.QtCore import Qt, QPoint, QSize, QRect, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QCursor, QPen
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QStackedWidget, QFrame, QMessageBox, QSizeGrip)

from ..config import app_dir
from .theme import QSS, ACCENT, ICON, BG, is_windows_11, save_window_size, restore_window_size
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
        self.btn_close = None
        for kind, slot in (("min", window.showMinimized),
                           ("max", self._toggle_max),
                           ("close", window.close)):
            b = QPushButton(); b.setObjectName("WinBtn")
            b.setIcon(_winctrl_icon(kind)); b.setIconSize(QSize(10, 10))
            if kind == "close":
                b.setObjectName("CloseBtn")
                self.btn_close = b
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
        if self.win.isMaximized():
            self.win.showNormal()
        else:
            self.win.showMaximized()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if sys.platform == "win32":
                hwnd = int(self.win.winId())
                ctypes.windll.user32.ReleaseCapture()
                ctypes.windll.user32.SendMessageW(hwnd, 0x0112, 0xF012, 0)
                return
            self._drag = e.globalPosition().toPoint() - self.win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if sys.platform != "win32" and self._drag and not self.win.isMaximized():
            self.win.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._toggle_max()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WordSnap")
        self.setWindowIcon(make_app_icon())
        if sys.platform != "win32":
            self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(900, 560)  # чтобы при уменьшении не ломалась вёрстка
        # стрелка выпадающих списков — из angle-small-down.svg
        arrow = svg_png("angle-small-down.svg", "#b0b0b0", 12)
        self.setStyleSheet(QSS + f"\nQComboBox::down-arrow {{ image: url('{arrow}'); }}")

        root = QWidget(); root.setObjectName("Root")
        self.setCentralWidget(root)
        self._root = root
        v = QVBoxLayout(root); v.setContentsMargins(1, 1, 1, 1); v.setSpacing(0)
        self._root_layout = v
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

        # «уголки» внизу — запасной способ ресайза (только на не-Windows)
        if sys.platform != "win32":
            self._grips = [QSizeGrip(root) for _ in range(2)]
            for g in self._grips:
                g.setFixedSize(16, 16)
                g.setStyleSheet("background: transparent;")
                g.raise_()
        else:
            self._grips = []

        # на Windows — нативный ресайз за ЛЮБОЙ край и угол + скругление углов и Snap
        if sys.platform == "win32":
            self._enable_native_resize()

        self._update_border_style()
        self._last_normal_pos = self.pos()
        self._last_normal_size = self.size()
        restore_window_size("main_window", self, 1280, 760, can_maximize=True, restore_pos=True)
        if not self.isMaximized():
            self._last_normal_pos = self.pos()
            self._last_normal_size = self.size()

    _BORDER = 8  # ширина зоны захвата у краёв окна (8px — стандарт Windows)

    def _enable_native_resize(self):
        """Добавляет окну стиль WS_THICKFRAME — Windows разрешает тянуть за края,
        а WM_NCCALCSIZE убирает рамку, чтобы окно осталось безрамочным с нативным Aero Snap."""
        try:
            hwnd = int(self.winId())
            GWL_STYLE = -16
            WS_THICKFRAME = 0x00040000
            WS_CAPTION = 0x00C00000
            WS_MAXIMIZEBOX = 0x00010000
            WS_MINIMIZEBOX = 0x00020000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_STYLE, style | WS_THICKFRAME | WS_CAPTION | WS_MAXIMIZEBOX | WS_MINIMIZEBOX
            )
            # Применяем изменение стилей рамки окна
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                0x0001 | 0x0002 | 0x0004 | 0x0020  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
            )

            # Windows 10 (билд 18985+) и Windows 11: DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            # Windows 10 (билд 17763-18984): DWMWA_USE_IMMERSIVE_DARK_MODE = 19
            for attr in (20, 19):
                try:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
                    )
                except Exception:
                    pass

            # Windows 11 (билд 22000+): нативное скругление углов и цвет обводки
            if is_windows_11():
                try:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, 33, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int)
                    )
                except Exception:
                    pass
                try:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, 34, ctypes.byref(ctypes.c_int(0xFFFFFFFE)), ctypes.sizeof(ctypes.c_int)
                    )
                except Exception:
                    pass

            # Нативная тень и обводка DWM (поддерживается на Win10 и Win11)
            try:
                margins = (ctypes.c_int * 4)(1, 1, 1, 1)
                ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
            except Exception:
                pass

            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)  # FRAMECHANGED|NOMOVE|NOSIZE|NOZORDER
        except Exception as e:
            print("native resize error:", e)

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == e.Type.WindowStateChange:
            is_max = self.isMaximized()
            if hasattr(self, "titlebar") and self.titlebar and self.titlebar.btn_max:
                self.titlebar.btn_max.setIcon(_winctrl_icon("restore" if is_max else "max"))
            self._update_border_style()

    def _update_border_style(self):
        is_max = self.isMaximized()
        is_win11 = is_windows_11()
        from .theme import P, BORDER
        radius = "8px" if (is_win11 and not is_max) else "0px"
        border_col = "none" if is_max else f"1px solid {BORDER}"
        self._root.setStyleSheet(f"""
            #Root {{
                background-color: {P['BG']};
                border-radius: {radius};
                border: {border_col};
            }}
        """)
        if hasattr(self, "titlebar") and self.titlebar:
            self.titlebar.setStyleSheet("""
                #TitleBar {
                    background-color: transparent;
                }
            """)
            if hasattr(self.titlebar, "btn_close") and self.titlebar.btn_close:
                close_radius = "7px" if (is_win11 and not is_max) else "0px"
                self.titlebar.btn_close.setStyleSheet(f"""
                    #CloseBtn {{
                        background: transparent;
                        border: none;
                        padding: 0;
                        min-width: 46px;
                        min-height: 32px;
                    }}
                    #CloseBtn:hover {{
                        background: #c42b1c;
                        border-top-right-radius: {close_radius};
                    }}
                """)
        if hasattr(self, "_root_layout"):
            if is_max and sys.platform == "win32":
                self._root_layout.setContentsMargins(8, 8, 8, 8)
            elif not is_max:
                self._root_layout.setContentsMargins(1, 1, 1, 1)
            else:
                self._root_layout.setContentsMargins(0, 0, 0, 0)

    def nativeEvent(self, eventType, message):
        if sys.platform == "win32" and eventType == "windows_generic_MSG":
            try:
                msg = wintypes.MSG.from_address(int(message))
            except Exception:
                return super().nativeEvent(eventType, message)

            if msg.message == 0x0083 and msg.wParam:      # WM_NCCALCSIZE — убираем рамку
                return True, 0

            if msg.message == 0x0084:                     # WM_NCHITTEST — какой край под курсором
                if self.isMaximized():
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
                b = self._BORDER  # 8px зона краёв
                c = 16            # 16px зона углов для надёжного диагонального ресайза

                left = px < b
                right = px >= w - b
                top = py < b
                bottom = py >= h - b

                # Угловые зоны
                if (top and left) or (top and px < c) or (left and py < c):
                    return True, 13  # HTTOPLEFT
                if (top and right) or (top and px >= w - c) or (right and py < c):
                    return True, 14  # HTTOPRIGHT
                if (bottom and left) or (bottom and px < c) or (left and py >= h - c):
                    return True, 16  # HTBOTTOMLEFT
                if (bottom and right) or (bottom and px >= w - c) or (right and py >= h - c):
                    return True, 17  # HTBOTTOMRIGHT

                # Стороны окна
                if left:
                    return True, 10  # HTLEFT
                if right:
                    return True, 11  # HTRIGHT
                if top:
                    return True, 12  # HTTOP
                if bottom:
                    return True, 15  # HTBOTTOM
        return super().nativeEvent(eventType, message)

    def moveEvent(self, e):
        super().moveEvent(e)
        if not self.isMaximized():
            self._last_normal_pos = self.pos()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not self.isMaximized():
            self._last_normal_pos = self.pos()
            self._last_normal_size = self.size()
        if getattr(self, "_grips", None) and len(self._grips) >= 2:
            r = self._root.rect()
            self._grips[0].move(0, r.height() - 16)               # нижний-левый
            self._grips[1].move(r.width() - 16, r.height() - 16)  # нижний-правый
            for g in self._grips:
                g.raise_()

    def closeEvent(self, e):
        save_window_size("main_window", self, save_maximized=True, save_pos=True)
        if getattr(self, "_force_close", False):
            super().closeEvent(e)
            return
        e.ignore()
        self.hide()

    def hideEvent(self, e):
        save_window_size("main_window", self, save_maximized=True, save_pos=True)
        super().hideEvent(e)

    def set_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self.titlebar.set_active(idx)
        if idx == 0:
            self.words_page.reload()
