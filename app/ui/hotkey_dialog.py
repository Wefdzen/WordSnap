"""Диалог назначения горячих клавиш с захватом нажатия комбинации."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)

from .theme import BG, BG_CARD, BG_HOVER, BORDER, ACCENT, TEXT, TEXT_DIM, apply_native_window_theme, save_window_size, restore_window_size
from .i18n import t

class HotkeyRecordDialog(QDialog):
    """Модальное всплывающее окно для назначения новой комбинации клавиш."""
    def __init__(self, current_hotkey: str = "alt+q", parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Назначение горячей клавиши"))
        self.setMinimumSize(400, 220)
        restore_window_size("hotkey_dialog", self, 440, 240)
        self.setWindowFlags((self.windowFlags() | Qt.Dialog) & ~Qt.WindowContextHelpButtonHint)
        self.setWindowModality(Qt.WindowModal)
        apply_native_window_theme(int(self.winId()))

        self._recorded_hotkey = current_hotkey.lower()
        self._temp_hotkey = self._recorded_hotkey

        self.setStyleSheet(f"""
            QDialog {{ background: {BG}; color: {TEXT}; }}
            QLabel {{ color: {TEXT}; font-family: 'Segoe UI', sans-serif; }}
            #KeyBadge {{
                background: {BG_CARD};
                border: 2px solid {ACCENT};
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 20px;
                font-weight: 700;
                color: {TEXT};
            }}
            #HintLbl {{
                color: {TEXT_DIM};
                font-size: 12px;
            }}
            QPushButton#PrimaryBtn {{
                background: {ACCENT};
                color: #ffffff;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
            }}
            QPushButton#PrimaryBtn:hover {{
                background: #50bcf0;
            }}
            QPushButton#SecondaryBtn {{
                background: {BG_CARD};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 8px 18px;
            }}
            QPushButton#SecondaryBtn:hover {{
                background: {BG_HOVER};
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(14)

        lbl_title = QLabel(t("Нажмите комбинацию клавиш на клавиатуре"))
        lbl_title.setStyleSheet("font-size: 14.5px; font-weight: 600;")
        lbl_title.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl_title)

        # Бейдж текущей комбинации
        self.badge_box = QLabel(self._format_display(self._temp_hotkey))
        self.badge_box.setObjectName("KeyBadge")
        self.badge_box.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.badge_box)

        lbl_hint = QLabel(t("Нажмите желаемую комбинацию (например Alt+Q или Ctrl+Shift+A). Esc — отмена."))
        lbl_hint.setObjectName("HintLbl")
        lbl_hint.setAlignment(Qt.AlignCenter)
        lbl_hint.setWordWrap(True)
        lay.addWidget(lbl_hint)

        lay.addStretch(1)

        # Кнопки
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)
        btn_bar.addStretch(1)

        self.btn_cancel = QPushButton(t("Отмена"))
        self.btn_cancel.setObjectName("SecondaryBtn")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(t("Сохранить"))
        self.btn_save.setObjectName("PrimaryBtn")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._save_and_accept)
        btn_bar.addWidget(self.btn_save)

        lay.addLayout(btn_bar)

    def _format_display(self, hk: str) -> str:
        if not hk:
            return t("Нажмите клавиши...")
        parts = [p.strip().title() for p in hk.split("+") if p.strip()]
        return " ＋ ".join(parts)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        # Esc закрывает окно без сохранения
        if key == Qt.Key_Escape:
            self.reject()
            return

        # Игнорируем отдельные нажатия модификаторов как самостоятельную комбинацию,
        # но обновляем текст индикатора
        mod_keys = {
            Qt.Key_Control: "Ctrl",
            Qt.Key_Alt: "Alt",
            Qt.Key_Shift: "Shift",
            Qt.Key_Meta: "Win"
        }

        mods = []
        if event.modifiers() & Qt.ControlModifier:
            mods.append("ctrl")
        if event.modifiers() & Qt.AltModifier:
            mods.append("alt")
        if event.modifiers() & Qt.ShiftModifier:
            mods.append("shift")

        if key in mod_keys:
            # Пользователь пока зажал только модификатор
            display_parts = [m.title() for m in mods] or [mod_keys[key]]
            self.badge_box.setText(" ＋ ".join(display_parts) + " ＋ …")
            return

        # Получаем имя основной клавиши
        key_seq = QKeySequence(key).toString()
        if not key_seq:
            return

        combo_parts = mods + [key_seq.lower()]
        self._temp_hotkey = "+".join(combo_parts)
        self.badge_box.setText(self._format_display(self._temp_hotkey))

    def _save_and_accept(self):
        if self._temp_hotkey:
            self._recorded_hotkey = self._temp_hotkey
            self.accept()

    def get_hotkey(self) -> str:
        return self._recorded_hotkey

    def closeEvent(self, e):
        save_window_size("hotkey_dialog", self)
        super().closeEvent(e)
