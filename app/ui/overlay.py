"""Режим переводчика: полноэкранный оверлей, рисующий перевод поверх
распознанных строк текста (как в Translumo)."""
import sys
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPixmap, QImage, QCursor
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
            pad_x, pad_y = 6, 4
            size = max(11, min(24, int(rect.height() * 0.68)))
            font = QFont("Segoe UI", size)
            font.setWeight(QFont.Medium)
            p.setFont(font)
            fm = QFontMetrics(font)

            # Вычисляем нужную ширину и высоту для текста (с учётом возможного переноса)
            single_w = fm.horizontalAdvance(text)
            max_available_w = max(rect.width(), min(single_w, self.width() - rect.x() - pad_x * 2))
            text_rect = fm.boundingRect(0, 0, max_available_w, 1000, Qt.TextWordWrap, text)

            box_w = max(rect.width(), text_rect.width()) + pad_x * 2
            box_h = max(rect.height(), text_rect.height()) + pad_y * 2
            box = QRect(rect.x() - pad_x, rect.y() - pad_y,
                        min(box_w, self.width() - rect.x() + pad_x),
                        min(box_h, self.height() - rect.y() + pad_y))

            # Подложка карточки перевода
            p.setPen(QColor(60, 60, 60, 160))
            p.setBrush(QColor(18, 18, 20, 235))
            p.drawRoundedRect(box, 5, 5)

            # Текст перевода
            p.setPen(QColor("#f3f4f6"))
            p.drawText(box.adjusted(pad_x, pad_y, -pad_x, -pad_y),
                       Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap, text)

        # Подсказка по закрытию в правом верхнем углу
        hint_font = QFont("Segoe UI", 10)
        p.setFont(hint_font)
        fm_hint = QFontMetrics(hint_font)
        hint_txt = "Esc / Alt+Q  ✕"
        hw = fm_hint.horizontalAdvance(hint_txt) + 16
        hh = 24
        hint_box = QRect(self.width() - hw - 14, 12, hw, hh)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(15, 15, 15, 180))
        p.drawRoundedRect(hint_box, 4, 4)
        p.setPen(QColor("#a1a1aa"))
        p.drawText(hint_box, Qt.AlignCenter, hint_txt)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Escape, Qt.Key_Q):
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


class FreezeFrameOverlay(QWidget):
    """Полноэкранный оверлей «Заморозка экрана + Свободный курсор»:
    1. Замораживает кадр игры пиксель-в-пиксель.
    2. Разблокирует курсор мыши Windows (освобождает из камеры игры).
    3. Выполняет OCR по застывшему экрану.
    4. При наведении интерактивно подсвечивает слова.
    5. При клике на слово открывает всплывающее окно словаря/переводчика.
    6. Закрывается по клавише Esc или Alt+Q.
    """
    ocr_ready = Signal(object, object)  # (lines, words)

    def __init__(self, img, mon: dict, on_word_clicked=None, on_close=None, parent=None):
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        super().__init__(parent, flags)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMouseTracking(True)
        self.mon = mon
        self.img = img
        self.on_word_clicked = on_word_clicked
        self.on_close = on_close

        # Преобразуем PIL Image в QPixmap
        try:
            img_rgba = img.convert("RGBA")
            raw_bytes = img_rgba.tobytes()
            qimg = QImage(raw_bytes, img.width, img.height, img.width * 4, QImage.Format_RGBA8888)
            self.pixmap = QPixmap.fromImage(qimg)
        except Exception:
            self.pixmap = QPixmap()

        self.setGeometry(mon["left"], mon["top"], mon["width"], mon["height"])
        self.setCursor(Qt.ArrowCursor)

        self.lines = []
        self.words = []  # list of (OcrWord, OcrLine, QRect)
        self.hovered_item = None
        self.active_word_rect = None
        self.is_scanning = True
        self._close_btn_rect = None

        # Разблокируем захват курсора игрой в Windows
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.ClipCursor(None)
                while ctypes.windll.user32.ShowCursor(True) < 0:
                    pass
            except Exception:
                pass

        self.ocr_ready.connect(self._on_ocr_finished)
        self._start_ocr_thread()

    def _start_ocr_thread(self):
        def worker():
            try:
                from .. import ocr
                from ..config import CONFIG
                engine = ocr.get_engine(CONFIG)
                lines = engine.recognize(self.img)
                words = []
                for line in lines:
                    for w in line.words:
                        r = QRect(int(w.x), int(w.y), int(w.w), int(w.h))
                        words.append((w, line, r))
                self.ocr_ready.emit(lines, words)
            except Exception as e:
                print("FreezeFrameOverlay OCR error:", e)
                self.ocr_ready.emit([], [])

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _on_ocr_finished(self, lines, words):
        self.lines = lines
        self.words = words
        self.is_scanning = False
        pos = self.mapFromGlobal(QCursor.pos())
        self._check_hover(pos)
        self.update()

    def _check_hover(self, pos):
        hovered = None
        for w, line, r in self.words:
            if r.adjusted(-3, -2, 3, 2).contains(pos):
                hovered = (w, line, r)
                break
        if hovered != self.hovered_item:
            self.hovered_item = hovered
            self.setCursor(Qt.PointingHandCursor if hovered else Qt.ArrowCursor)
            self.update()

    def mouseMoveEvent(self, e):
        self._check_hover(e.pos())
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        if self._close_btn_rect and self._close_btn_rect.contains(e.pos()):
            self.close()
            return

        if self.hovered_item:
            w, line, r = self.hovered_item
            from .. import ocr
            clean_w = ocr.clean_word(w.text)
            sentence = ocr.sentence_around(self.lines, line, w)
            screen_x = self.mon["left"] + int(w.x)
            screen_y = self.mon["top"] + int(w.y)
            self.active_word_rect = r.adjusted(-2, -2, 2, 2)
            self.update()
            if self.on_word_clicked:
                self.on_word_clicked(clean_w, sentence, screen_x, screen_y, int(w.w), int(w.h))
        super().mousePressEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Escape, Qt.Key_Q):
            self.close()
            return
        super().keyPressEvent(e)

    def closeEvent(self, e):
        if self.on_close:
            self.on_close()
        super().closeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        # 1. Стоп-кадр экрана
        if not self.pixmap.isNull():
            p.drawPixmap(0, 0, self.pixmap)

        # 2. Активное выбранное слово (золотистая рамка)
        if self.active_word_rect:
            p.setPen(QColor("#eab308"))
            p.setBrush(QColor(234, 179, 8, 70))
            p.drawRoundedRect(self.active_word_rect, 3, 3)

        # 3. Наведённое слово (голубая неоновая подсветка)
        if self.hovered_item:
            _, _, r = self.hovered_item
            p.setPen(QColor("#38bdf8"))
            p.setBrush(QColor(56, 189, 248, 80))
            p.drawRoundedRect(r.adjusted(-3, -2, 3, 2), 3, 3)

        # 4. Верхний стеклянный баннер управления
        from .i18n import t as _tr
        font = QFont("Segoe UI", 11)
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        fm = QFontMetrics(font)

        if self.is_scanning:
            status_text = "🧊 " + _tr("Заморозка экрана...") + " (" + _tr("сканирование слов...") + ")"
        else:
            status_text = "🧊 " + _tr("Заморозка экрана") + " • " + _tr("Кликните на слово") + " • Esc / Alt+Q " + _tr("выход")

        text_w = fm.horizontalAdvance(status_text)
        b_w = text_w + 50
        b_h = 36
        b_x = (self.width() - b_w) // 2
        b_y = 16

        banner_rect = QRect(b_x, b_y, b_w, b_h)
        p.setPen(QColor(80, 80, 95, 200))
        p.setBrush(QColor(18, 18, 24, 230))
        p.drawRoundedRect(banner_rect, 6, 6)

        p.setPen(QColor("#f4f4f5"))
        p.drawText(QRect(b_x + 16, b_y, text_w, b_h), Qt.AlignVCenter | Qt.AlignLeft, status_text)

        self._close_btn_rect = QRect(b_x + b_w - 32, b_y + 4, 26, 28)
        p.setPen(QColor("#a1a1aa"))
        p.drawText(self._close_btn_rect, Qt.AlignCenter, "✕")