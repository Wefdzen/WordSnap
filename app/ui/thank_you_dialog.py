import os
import sys
import webbrowser
from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFrame, QApplication)
from PySide6.QtGui import QMovie, QDesktopServices, QIcon

from ..config import app_dir
from .theme import P, ACCENT, TEXT, TEXT_DIM, BG_CARD, BORDER, apply_native_window_theme
from .i18n import t

DONATION_URL = "https://www.donationalerts.com/r/wefdzen"
APP_VERSION = "1.3.0"

_active_dialog = None


class ThankYouDialog(QDialog):
    """Мини-окно благодарности с анимированным GIF anime-thank-you-man.gif."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Спасибо за поддержку! ❤️"))
        self.setFixedSize(420, 530)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        # Системная тёмная тема окна и скругления Windows 11
        if sys.platform == "win32":
            apply_native_window_theme(int(self.winId()))

        # Иконка окна
        try:
            from .main_window import make_app_icon
            self.setWindowIcon(make_app_icon())
        except Exception:
            pass

        # Основной фон и стили окна
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {P['BG']};
                color: {P['TEXT']};
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }}
            #TitleLbl {{
                font-size: 17px;
                font-weight: 700;
                color: {P['TEXT']};
            }}
            #SubLbl {{
                font-size: 13px;
                color: {P['TEXT_DIM']};
                line-height: 1.4;
            }}
            #GifFrame {{
                background-color: {P['BG_CARD']};
                border: 1px solid {P['BORDER']};
                border-radius: 12px;
            }}
            #DonateBtn {{
                background-color: {P['ACCENT']};
                color: #ffffff;
                font-size: 13px;
                font-weight: 600;
                padding: 9px 18px;
                border-radius: 6px;
                border: none;
            }}
            #DonateBtn:hover {{
                background-color: {P['ACCENT_HOVER']};
            }}
            #CloseBtn {{
                background-color: {P['BG_CARD']};
                color: {P['TEXT']};
                font-size: 13px;
                font-weight: 500;
                padding: 9px 18px;
                border-radius: 6px;
                border: 1px solid {P['BORDER']};
            }}
            #CloseBtn:hover {{
                background-color: {P['BG_HOVER']};
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        # Заголовок
        lbl_title = QLabel(t("Огромное спасибо за поддержку! ❤️"))
        lbl_title.setObjectName("TitleLbl")
        lbl_title.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl_title)

        # Подзаголовок
        lbl_sub = QLabel(t("Каждый донат помогает развивать WordSnap и делать его лучше."))
        lbl_sub.setObjectName("SubLbl")
        lbl_sub.setAlignment(Qt.AlignCenter)
        lbl_sub.setWordWrap(True)
        lay.addWidget(lbl_sub)

        # Рамка с GIF
        frame = QFrame()
        frame.setObjectName("GifFrame")
        flay = QVBoxLayout(frame)
        flay.setContentsMargins(8, 8, 8, 8)
        flay.setAlignment(Qt.AlignCenter)

        self.gif_lbl = QLabel()
        self.gif_lbl.setAlignment(Qt.AlignCenter)
        self.movie = None

        gif_path = os.path.join(app_dir(), "assets", "anime-thank-you-man.gif")
        if os.path.exists(gif_path):
            self.movie = QMovie(gif_path)
            self.movie.setScaledSize(QSize(320, 320))
            self.gif_lbl.setMovie(self.movie)
            self.movie.start()
        else:
            self.gif_lbl.setText("❤️ Thank You! ❤️")

        flay.addWidget(self.gif_lbl)
        lay.addWidget(frame, 1)

        # Кнопки внизу
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(10)

        btn_open = QPushButton(f"🌐  {t('Перейти к донату')}")
        btn_open.setObjectName("DonateBtn")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.clicked.connect(self._open_url)
        btn_lay.addWidget(btn_open, 1)

        btn_close = QPushButton(t("Закрыть"))
        btn_close.setObjectName("CloseBtn")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.close)
        btn_lay.addWidget(btn_close)

        lay.addLayout(btn_lay)

    def _open_url(self):
        try:
            QDesktopServices.openUrl(QUrl(DONATION_URL))
        except Exception:
            try:
                webbrowser.open(DONATION_URL)
            except Exception:
                pass

    def closeEvent(self, e):
        global _active_dialog
        if self.movie:
            self.movie.stop()
        if _active_dialog is self:
            _active_dialog = None
        super().closeEvent(e)


def open_donation_support(parent=None):
    """Открывает ссылку на DonationAlerts в браузере и отображает мини-окно благодарности."""
    global _active_dialog

    # Открываем ссылку на DonationAlerts в браузере
    try:
        QDesktopServices.openUrl(QUrl(DONATION_URL))
    except Exception:
        try:
            webbrowser.open(DONATION_URL)
        except Exception:
            pass

    # Открываем или активируем мини-окно с GIF
    if _active_dialog is not None and _active_dialog.isVisible():
        _active_dialog.raise_()
        _active_dialog.activateWindow()
        return _active_dialog

    dlg = ThankYouDialog(parent)
    _active_dialog = dlg
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return dlg
