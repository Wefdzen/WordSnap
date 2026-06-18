"""Режим переводчика: полноэкранный оверлей, рисующий перевод поверх
распознанных строк текста (как в Translumo)."""
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPixmap
from PySide6.QtWidgets import QWidget


class TranslationOverlay(QWidget):
    """items: список (QRect, текст_перевода). Esc или повторная горячая клавиша закрывает."""
    def __init__(self, geometry: dict, items: list, frozen_pixmap: QPixmap | None = None,
                 interactive: bool = True, parent=None):
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        super().__init__(parent, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        if not interactive:
            # клики проходят сквозь оверлей («Делать оверлей активным окном» выключено)
            self.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.setWindowFlag(Qt.WindowTransparentForInput, True)
        self.items = items
        self.frozen = frozen_pixmap
        self.setGeometry(geometry["left"], geometry["top"],
                         geometry["width"], geometry["height"])

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        if self.frozen is not None:
            p.drawPixmap(self.rect(), self.frozen)
        for rect, text in self.items:
            if not text:
                continue
            pad = 4
            # подбираем размер шрифта под высоту исходной строки
            size = max(9, min(26, int(rect.height() * 0.62)))
            font = QFont("Segoe UI"); font.setPixelSize(size)
            fm = QFontMetrics(font)
            w = max(rect.width(), fm.horizontalAdvance(text) + pad * 2)
            box = QRect(rect.x() - pad, rect.y() - pad,
                        min(w, self.width() - rect.x()) + pad, rect.height() + pad * 2)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(20, 20, 20, 235))
            p.drawRoundedRect(box, 4, 4)
            p.setPen(QColor("#ffffff"))
            p.setFont(font)
            p.drawText(box.adjusted(pad, 0, -pad, 0),
                       Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap, text)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        super().keyPressEvent(e)

    def mousePressEvent(self, e):
        self.close()


class WordHighlight(QWidget):
    """Подсветка распознанного слова прямо на экране (как в оригинале Lookupper).
    Прозрачная, не перехватывает клики — работает поверх игр и приложений."""
    def __init__(self, x, y, w, h):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)
        pad = 2
        self.setGeometry(int(x - pad), int(y - pad), int(w + pad * 2), int(h + pad * 2))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(210, 205, 80, 110))   # полупрозрачный жёлто-оливковый
        p.drawRoundedRect(self.rect(), 3, 3)