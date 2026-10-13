"""Асинхронная установка словарей Yomitan (.zip) в фоновом потоке.
Полностью исключает зависания GUI и лаги курсора мыши.
"""
import os
import sys
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar
)
from ..dictionaries import DICTIONARIES
from .theme import BG, BG_CARD, TEXT, TEXT_DIM, ACCENT, BORDER, apply_native_window_theme, save_window_size, restore_window_size
from .i18n import t

import json
import subprocess
from ..config import app_dir

class DictionaryInstallWorker(QThread):
    progress_updated = Signal(int, int, str)  # current, total, bank_name
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, zip_path: str):
        super().__init__()
        self.zip_path = zip_path

    def run(self):
        try:
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--import-dict", self.zip_path]
            else:
                cmd = [sys.executable, "-m", "app.dictionaries", self.zip_path]

            creationflags = 0x08000000 if sys.platform == "win32" else 0
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=app_dir(),
                creationflags=creationflags
            )

            result = None
            error_msg = None

            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    t_type = data.get("type")
                    if t_type == "progress":
                        self.progress_updated.emit(data["current"], data["total"], data["name"])
                    elif t_type == "done":
                        result = data.get("result")
                    elif t_type == "error":
                        error_msg = data.get("error")
                except Exception:
                    pass

            proc.wait()
            if proc.returncode == 0 and result:
                self.completed.emit(result)
            else:
                if not error_msg:
                    err_out = proc.stderr.read()
                    error_msg = err_out.strip() or f"Process exited with code {proc.returncode}"
                self.failed.emit(error_msg)
        except Exception as e:
            # Запасной вариант на случай сбоя запуска процесса
            try:
                def cb(cur, tot, name):
                    self.progress_updated.emit(cur, tot, name)
                res = DICTIONARIES.import_zip(self.zip_path, progress_callback=cb)
                self.completed.emit(res)
            except Exception as ex2:
                self.failed.emit(str(ex2))


class DictionaryInstallDialog(QDialog):
    """Модальный диалог с прогресс-баром для распаковки и индексации словаря."""
    def __init__(self, parent, zip_path: str):
        super().__init__(parent)
        self.zip_path = zip_path
        self.result = None
        self.error = None

        self.setWindowTitle(t("Установка словаря"))
        self.setMinimumSize(420, 140)
        restore_window_size("dict_installer", self, 460, 150)
        self.setWindowFlags((self.windowFlags() | Qt.Dialog) & ~Qt.WindowContextHelpButtonHint)
        self.setWindowModality(Qt.WindowModal)

        self.setStyleSheet(f"""
            QDialog {{ background: {BG}; color: {TEXT}; }}
            QLabel {{ color: {TEXT}; font-family: 'Segoe UI', sans-serif; }}
            QProgressBar {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 6px;
                text-align: center;
                color: {TEXT};
                font-size: 11.5px;
                font-weight: 600;
                height: 18px;
            }}
            QProgressBar::chunk {{
                background: {ACCENT};
                border-radius: 5px;
            }}
        """)

        apply_native_window_theme(int(self.winId()))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        file_name = os.path.basename(zip_path)
        self.lbl_title = QLabel(f"<b>{t('Установка словаря')}</b>: {file_name}")
        self.lbl_title.setStyleSheet("font-size: 13.5px;")
        lay.addWidget(self.lbl_title)

        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        lay.addWidget(self.pbar)

        self.lbl_status = QLabel(t("Распаковка и обработка базы терминов..."))
        self.lbl_status.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11.5px;")
        lay.addWidget(self.lbl_status)

        self.worker = DictionaryInstallWorker(zip_path)
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.completed.connect(self._on_completed)
        self.worker.failed.connect(self._on_failed)

    def exec(self):
        self.worker.start()
        return super().exec()

    def _on_progress(self, cur: int, tot: int, name: str):
        if tot > 0:
            pct = int((cur / tot) * 100)
            self.pbar.setValue(pct)
            self.lbl_status.setText(f"{t('Индексация базы')}: {cur} / {tot} ({name})")

    def _on_completed(self, res: dict):
        self.result = res
        self.accept()

    def _on_failed(self, err: str):
        self.error = err
        self.reject()

    def closeEvent(self, e):
        save_window_size("dict_installer", self)
        super().closeEvent(e)
