"""Темы оформления интерфейса (тёмная / светлая / системная).

Палитра выбирается из настроек (`ui_theme`) ОДИН раз при загрузке модуля, поэтому
все виджеты, которые берут цвета через `from .theme import ACCENT, ...`, получают
значения уже выбранной темы. Смена темы применяется после перезапуска приложения.

ВАЖНО: всплывающее окно перевода (popup.py) сюда не завязано — оно само выбирает
"""
import sys
from ..config import CONFIG


def is_windows_11() -> bool:
    """Проверяет, работает ли приложение на Windows 11 (билд 22000+)."""
    if sys.platform != "win32":
        return False
    try:
        return sys.getwindowsversion().build >= 22000
    except Exception:
        return False


def is_windows_10_or_newer() -> bool:
    """Проверяет, работает ли приложение на Windows 10 или более новой версии."""
    if sys.platform != "win32":
        return False
    try:
        return sys.getwindowsversion().major >= 10
    except Exception:
        return False


def apply_native_window_theme(hwnd: int):
    """Настраивает тёмный заголовок и системные эффекты DWM для Windows 10 и 11."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # DWMWA_USE_IMMERSIVE_DARK_MODE: 20 (Win10 18985+ и Win11), 19 (Win10 17763-18984)
        for attr in (20, 19):
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
                )
            except Exception:
                pass

        # Windows 11 (билд 22000+): нативное скругление углов диалогов и окон
        if is_windows_11():
            try:
                # DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 33, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int)
                )
            except Exception:
                pass
    except Exception:
        pass


def save_window_size(name: str, widget, save_maximized: bool = False, save_pos: bool = False):
    """Сохраняет текущий размер (и состояние разворачивания/позицию) окна в конфигурацию."""
    try:
        from ..config import CONFIG
        sizes = dict(CONFIG.get("window_sizes") or {})

        is_max = save_maximized and hasattr(widget, "isMaximized") and bool(widget.isMaximized())

        # Если окно развернуто, сохраняем геометрию до разворачивания, чтобы при сбросе не получить 1920x1080
        if is_max:
            normal_size = getattr(widget, "_last_normal_size", None)
            if normal_size is not None and normal_size.width() >= 300 and normal_size.height() >= 150:
                w = normal_size.width()
                h = normal_size.height()
            elif hasattr(widget, "normalGeometry"):
                norm = widget.normalGeometry()
                if norm.isValid() and not norm.isEmpty() and (norm.width() < widget.width() or norm.height() < widget.height()):
                    w = norm.width()
                    h = norm.height()
                else:
                    w = widget.width()
                    h = widget.height()
            else:
                w = widget.width()
                h = widget.height()

            normal_pos = getattr(widget, "_last_normal_pos", None)
            if normal_pos is not None:
                x = normal_pos.x()
                y = normal_pos.y()
            elif hasattr(widget, "normalGeometry"):
                norm = widget.normalGeometry()
                x = norm.x()
                y = norm.y()
            else:
                x = widget.x()
                y = widget.y()
        else:
            w = widget.width()
            h = widget.height()
            x = widget.x()
            y = widget.y()

        info = {"w": w, "h": h}
        if save_pos and x is not None and y is not None:
            info["x"] = x
            info["y"] = y
        if save_maximized and hasattr(widget, "isMaximized"):
            info["maximized"] = is_max
        sizes[name] = info
        CONFIG.set("window_sizes", sizes, save=True)
    except Exception:
        pass


def restore_window_size(name: str, widget, default_w: int, default_h: int, can_maximize: bool = False, restore_pos: bool = False):
    """Восстанавливает сохранённый размер и позицию окна из конфигурации."""
    try:
        from ..config import CONFIG
        from PySide6.QtCore import QTimer, QRect
        from PySide6.QtGui import QGuiApplication
        sizes = CONFIG.get("window_sizes") or {}
        info = sizes.get(name)
        if isinstance(info, dict):
            w = info.get("w", default_w)
            h = info.get("h", default_h)
            if isinstance(w, int) and isinstance(h, int) and w >= 300 and h >= 150:
                widget.resize(w, h)
            else:
                w, h = default_w, default_h
                widget.resize(default_w, default_h)

            if restore_pos and "x" in info and "y" in info:
                x = info.get("x")
                y = info.get("y")
                if isinstance(x, int) and isinstance(y, int):
                    rect = QRect(x, y, w, h)
                    visible = False
                    for screen in QGuiApplication.screens():
                        avail = screen.availableGeometry()
                        if avail.intersects(rect):
                            inter = avail.intersected(rect)
                            if inter.width() >= 100 and inter.height() >= 100:
                                visible = True
                                break
                    if visible:
                        widget.move(x, y)

            if can_maximize and info.get("maximized"):
                QTimer.singleShot(0, widget.showMaximized)
        else:
            widget.resize(default_w, default_h)
    except Exception:
        widget.resize(default_w, default_h)

# ---------------------------------------------------------------- палитры
DARK = dict(
    ACCENT="#60cdff", ACCENT_HOVER="#79d6ff",
    BG="#1f1f1f", BG_PANEL="#272727", BG_CARD="#2d2d2d", BG_HOVER="#333333",
    BORDER="#3a3a3a", TEXT="#ffffff", TEXT_DIM="#9d9d9d",
    PRESSED="#242424", SCROLL="#4d4d4d", SCROLL_HOVER="#5d5d5d", INPUT_LINE="#8a8a8a",
    ROW_HOVER="#303030", ROW_SEL="#383838",
)
LIGHT = dict(
    ACCENT="#0067c0", ACCENT_HOVER="#1975c5",
    BG="#f3f3f3", BG_PANEL="#ffffff", BG_CARD="#ffffff", BG_HOVER="#ececec",
    BORDER="#d6d6d6", TEXT="#1b1b1b", TEXT_DIM="#5f5f5f",
    PRESSED="#e2e2e2", SCROLL="#c4c4c4", SCROLL_HOVER="#a8a8a8", INPUT_LINE="#8a8a8a",
    ROW_HOVER="#ededed", ROW_SEL="#e1e1e1",
)


def _windows_prefers_light() -> bool:
    """Системная тема Windows: AppsUseLightTheme (1 - светлая, 0 - тёмная)."""
    try:
        import winreg
        key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            val, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return bool(val)
    except Exception:
        return False


def resolve(name: str) -> dict:
    if name == "light":
        return LIGHT
    if name == "system":
        return LIGHT if _windows_prefers_light() else DARK
    return DARK


# текущая палитра — выбирается по настройке при загрузке модуля
P = resolve(CONFIG.get("ui_theme", "dark"))
IS_LIGHT = P is LIGHT

ACCENT = P["ACCENT"]
BG = P["BG"]
BG_PANEL = P["BG_PANEL"]
BG_CARD = P["BG_CARD"]
BG_HOVER = P["BG_HOVER"]
BORDER = P["BORDER"]
TEXT = P["TEXT"]
TEXT_DIM = P["TEXT_DIM"]
ROW_HOVER = P["ROW_HOVER"]
ROW_SEL = P["ROW_SEL"]
# цвет иконок (SVG/кнопки окна): белый на тёмной теме, чёрный на светлой —
# исходные SVG чёрные, поэтому в светлой теме их и красим в тёмный
ICON = P["TEXT"]


def apply_palette(app):
    """Задаёт палитру всему приложению — чтобы фон областей прокрутки, вьюпортов
    и прочих неименованных виджетов соответствовал теме (иначе в светлой теме они
    остаются тёмными из дефолтной палитры Qt)."""
    from PySide6.QtGui import QPalette, QColor
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(P["BG"]))
    pal.setColor(QPalette.Base, QColor(P["BG"]))
    pal.setColor(QPalette.AlternateBase, QColor(P["BG_PANEL"]))
    pal.setColor(QPalette.Text, QColor(P["TEXT"]))
    pal.setColor(QPalette.WindowText, QColor(P["TEXT"]))
    pal.setColor(QPalette.Button, QColor(P["BG_CARD"]))
    pal.setColor(QPalette.ButtonText, QColor(P["TEXT"]))
    pal.setColor(QPalette.ToolTipBase, QColor(P["BG_CARD"]))
    pal.setColor(QPalette.ToolTipText, QColor(P["TEXT"]))
    pal.setColor(QPalette.Highlight, QColor(P["ACCENT"]))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff" if IS_LIGHT else "#000000"))
    pal.setColor(QPalette.PlaceholderText, QColor(P["TEXT_DIM"]))
    app.setPalette(pal)


def build_qss(p: dict) -> str:
    return f"""
* {{
    font-family: "Segoe UI", "Segoe UI Variable", sans-serif;
    font-size: 13px;
    color: {p['TEXT']};
    outline: none;
}}
QMainWindow, QDialog, #Root {{ background: {p['BG']}; color: {p['TEXT']}; }}

/* ---------- кастомный заголовок ---------- */
#TitleBar {{ background: {p['BG']}; }}
#TabButton {{
    background: transparent; border: none; padding: 10px 10px;
    color: {p['TEXT']}; font-size: 13px; border-radius: 4px;
}}
#TabButton:hover {{ background: {p['BG_HOVER']}; }}
#TabUnderline {{ background: {p['ACCENT']}; border-radius: 1px; }}
#WinBtn {{ background: transparent; border: none; color: {p['TEXT']}; font-size: 12px;
           padding: 0; min-width: 46px; min-height: 32px; }}
#WinBtn:hover {{ background: {p['BG_HOVER']}; }}
#CloseBtn:hover {{ background: #c42b1c; }}
#ProButton {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #9be8ff, stop:1 {p['ACCENT']});
    color: #003a57; border: none; border-radius: 4px; padding: 7px 14px; font-weight: 600;
}}
#ProButton:hover {{ background: {p['ACCENT']}; }}

/* ---------- общие панели ---------- */
#Panel {{ background: {p['BG_PANEL']}; border-radius: 8px; }}
#Card {{ background: {p['BG_CARD']}; border-radius: 6px; }}
#SettingRow {{ background: {p['BG_CARD']}; border-radius: 4px; }}
#SettingRow:hover {{ background: {p['BG_HOVER']}; }}
QLabel#H1 {{ font-size: 28px; font-weight: 700; }}
QLabel#H2 {{ font-size: 20px; font-weight: 600; }}
QLabel#SectionTitle {{ font-size: 14px; font-weight: 600; padding: 14px 2px 6px 2px; }}
QLabel#Dim {{ color: {p['TEXT_DIM']}; font-size: 12px; }}
QLabel#Quote {{ font-size: 14px; }}

/* ---------- инпуты ---------- */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {p['BG_CARD']}; border: 1px solid {p['BORDER']}; border-bottom: 1px solid {p['INPUT_LINE']};
    border-radius: 4px; padding: 6px 8px; selection-background-color: {p['ACCENT']};
    selection-color: #000;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-bottom: 2px solid {p['ACCENT']}; }}
QComboBox {{
    background: {p['BG_CARD']}; border: 1px solid {p['BORDER']}; border-radius: 4px; padding: 6px 34px 6px 10px;
}}
QComboBox:hover {{ background: {p['BG_HOVER']}; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; border: none; width: 22px; }}
QComboBox::down-arrow {{ width: 12px; height: 12px; margin-right: 6px; }}
QComboBox QAbstractItemView {{
    background: {p['BG_CARD']}; border: 1px solid {p['BORDER']}; selection-background-color: {p['BG_HOVER']};
    selection-color: {p['TEXT']}; outline: none; padding: 2px;
}}
QComboBox QAbstractItemView::item {{
    min-height: 34px; padding: 4px 10px; color: {p['TEXT']}; border-radius: 4px;
}}

/* ---------- кнопки ---------- */
QPushButton {{
    background: {p['BG_CARD']}; border: 1px solid {p['BORDER']}; border-radius: 4px; padding: 7px 14px;
}}
QPushButton:hover {{ background: {p['BG_HOVER']}; }}
QPushButton:pressed {{ background: {p['PRESSED']}; }}
QPushButton#Flat {{ background: transparent; border: none; padding: 6px 10px; }}
QPushButton#Flat:hover {{ background: {p['BG_HOVER']}; border-radius: 4px; }}
QPushButton#Accent {{
    background: {p['ACCENT']}; color: #003a57; border: none; font-weight: 600;
}}
QPushButton#Accent:hover {{ background: {p['ACCENT_HOVER']}; }}
QPushButton#IconBtn {{ background: transparent; border: 1px solid transparent;
    border-radius: 4px; padding: 5px 8px; font-size: 14px; }}
QPushButton#IconBtn:hover {{ background: {p['BG_HOVER']}; }}
QPushButton#IconBtn:checked {{ background: {p['BG_HOVER']}; border: 1px solid {p['BORDER']}; }}

/* ---------- списки ---------- */
QListWidget {{ background: transparent; border: none; }}
QListWidget::item {{ border-radius: 4px; }}
QListWidget::item:selected, QListWidget::item:hover {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['SCROLL']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p['SCROLL_HOVER']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {p['SCROLL']}; border-radius: 4px; }}

/* радио-кнопки рисуются вручную (FluentRadio в widgets.py) */

QToolTip {{ background: {p['BG_CARD']}; color: {p['TEXT']}; border: 1px solid {p['BORDER']}; padding: 4px; }}
QMenu {{ background: {p['BG_CARD']}; border: 1px solid {p['BORDER']}; }}
QMenu::item {{ padding: 6px 18px; }}
QMenu::item:selected {{ background: {p['BG_HOVER']}; }}
"""


QSS = build_qss(P)


def apply_theme_live(app, theme_name: str):
    """Применяет выбранную тему ко всему приложению на лету."""
    global P, IS_LIGHT, ACCENT, ACCENT_HOVER, BG, BG_PANEL, BG_CARD, BG_HOVER, BORDER, TEXT, TEXT_DIM, PRESSED, SCROLL, SCROLL_HOVER, INPUT_LINE, ROW_HOVER, ROW_SEL, ICON, QSS
    P = resolve(theme_name)
    IS_LIGHT = P is LIGHT
    ACCENT = P["ACCENT"]
    ACCENT_HOVER = P["ACCENT_HOVER"]
    BG = P["BG"]
    BG_PANEL = P["BG_PANEL"]
    BG_CARD = P["BG_CARD"]
    BG_HOVER = P["BG_HOVER"]
    BORDER = P["BORDER"]
    TEXT = P["TEXT"]
    TEXT_DIM = P["TEXT_DIM"]
    PRESSED = P["PRESSED"]
    SCROLL = P["SCROLL"]
    SCROLL_HOVER = P["SCROLL_HOVER"]
    INPUT_LINE = P["INPUT_LINE"]
    ROW_HOVER = P["ROW_HOVER"]
    ROW_SEL = P["ROW_SEL"]
    ICON = P["TEXT"]
    QSS = build_qss(P)
    if app:
        apply_palette(app)
        app.setStyleSheet(QSS)

