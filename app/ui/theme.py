"""Темы оформления интерфейса (тёмная / светлая / системная).

Палитра выбирается из настроек (`ui_theme`) ОДИН раз при загрузке модуля, поэтому
все виджеты, которые берут цвета через `from .theme import ACCENT, ...`, получают
значения уже выбранной темы. Смена темы применяется после перезапуска приложения.

ВАЖНО: всплывающее окно перевода (popup.py) сюда не завязано — оно само выбирает
светлый/тёмный вид по яркости фона под курсором.
"""
from ..config import CONFIG

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
    """Системная тема Windows: AppsUseLightTheme (1 — светлая, 0 — тёмная)."""
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
QMainWindow, #Root {{ background: {p['BG']}; }}

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
    background: {p['BG_CARD']}; border: 1px solid {p['BORDER']}; border-radius: 4px; padding: 6px 28px 6px 10px;
}}
QComboBox:hover {{ background: {p['BG_HOVER']}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ width: 12px; height: 12px; margin-right: 8px; }}
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
