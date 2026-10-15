"""Режим переводчика: полноэкранный оверлей, рисующий перевод поверх
распознанных строк текста (как в Translumo)."""
import sys
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPixmap, QImage, QCursor, QPen, QGuiApplication
from PySide6.QtWidgets import QWidget
from .theme import IS_WIN11, IS_WIN10


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

        scr = (QGuiApplication.screenAt(QPoint(int(geometry["left"]), int(geometry["top"])))
               or QGuiApplication.screenAt(QCursor.pos())
               or QGuiApplication.primaryScreen())
        dpr = scr.devicePixelRatio() if scr else 1.0
        self.dpr = dpr if dpr > 0 else 1.0

        if not IS_WIN11 and scr:
            self.setGeometry(scr.geometry())
        else:
            self.setGeometry(geometry["left"], geometry["top"],
                             geometry["width"], geometry["height"])

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        if self.frozen is not None:
            p.drawPixmap(self.rect(), self.frozen)

        dpr = self.dpr if not IS_WIN11 else 1.0
        for rect, text in self.items:
            if not text:
                continue
            if dpr > 0 and dpr != 1.0:
                rect = QRect(int(rect.x() / dpr), int(rect.y() / dpr),
                             int(rect.width() / dpr), int(rect.height() / dpr))
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


def force_foreground_and_release_cursor(widget) -> None:
    """Принудительный перехват системного фокуса окном оверлея и сброс захвата курсора Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        overlay_hwnd = int(widget.winId())
        fg_hwnd = user32.GetForegroundWindow()

        if fg_hwnd and fg_hwnd != overlay_hwnd:
            fg_thread_id = user32.GetWindowThreadProcessId(fg_hwnd, None)
            my_thread_id = kernel32.GetCurrentThreadId()
            if fg_thread_id != my_thread_id:
                user32.AttachThreadInput(fg_thread_id, my_thread_id, True)
                try:
                    # Имитируем нажатие и отпускание Alt (VK_MENU = 0x12) для обхода ForegroundLockTimeout
                    VK_MENU = 0x12
                    KEYEVENTF_KEYUP = 0x0002
                    user32.keybd_event(VK_MENU, 0, 0, 0)
                    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
                    user32.SetForegroundWindow(overlay_hwnd)
                    user32.SetFocus(overlay_hwnd)
                finally:
                    user32.AttachThreadInput(fg_thread_id, my_thread_id, False)
            else:
                user32.SetForegroundWindow(overlay_hwnd)
                user32.SetFocus(overlay_hwnd)
        else:
            user32.SetForegroundWindow(overlay_hwnd)
            user32.SetFocus(overlay_hwnd)

        user32.ClipCursor(None)
        user32.ReleaseCapture()
    except Exception as e:
        print("force_foreground_and_release_cursor error:", e)


def restore_game_focus(game_hwnd: int) -> None:
    """Принудительный возврат фокуса окну игры и отправка WM_ACTIVATE для скрытия системного курсора движком игры."""
    if not game_hwnd or sys.platform != "win32":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        game_thread_id = user32.GetWindowThreadProcessId(game_hwnd, None)
        my_thread_id = kernel32.GetCurrentThreadId()

        if game_thread_id and my_thread_id and game_thread_id != my_thread_id:
            user32.AttachThreadInput(my_thread_id, game_thread_id, True)
            try:
                user32.SetForegroundWindow(game_hwnd)
                user32.SetFocus(game_hwnd)
                # WM_ACTIVATE = 0x0006, WA_ACTIVE = 1 — уведомление об активации окна игры для скрытия курсора
                user32.PostMessageW(game_hwnd, 0x0006, 1, 0)
            finally:
                user32.AttachThreadInput(my_thread_id, game_thread_id, False)
        else:
            user32.SetForegroundWindow(game_hwnd)
            user32.SetFocus(game_hwnd)
            user32.PostMessageW(game_hwnd, 0x0006, 1, 0)
    except Exception as e:
        print("restore_game_focus error:", e)


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
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
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

        scr = (QGuiApplication.screenAt(QPoint(int(mon["left"]), int(mon["top"])))
               or QGuiApplication.screenAt(QCursor.pos())
               or QGuiApplication.primaryScreen())
        dpr = scr.devicePixelRatio() if scr else 1.0
        self.dpr = dpr if dpr > 0 else 1.0

        if not IS_WIN11:
            if not self.pixmap.isNull() and self.dpr != 1.0:
                self.pixmap.setDevicePixelRatio(self.dpr)
            if scr:
                self.setGeometry(scr.geometry())
            else:
                self.setGeometry(int(mon["left"] / self.dpr), int(mon["top"] / self.dpr),
                                 int(mon["width"] / self.dpr), int(mon["height"] / self.dpr))
        else:
            self.setGeometry(mon["left"], mon["top"], mon["width"], mon["height"])

        self.setCursor(Qt.ArrowCursor)

        self.lines = []
        self.words = []  # list of (OcrWord, OcrLine, QRect)
        self.hovered_item = None
        self.active_word_rect = None
        self.is_scanning = True
        self._close_btn_rect = None
        self._ocr_started = False

        self._drag_start = None
        self._drag_rect = None
        self._is_dragging = False

        self.ocr_ready.connect(self._on_ocr_finished)

    def _start_ocr_thread(self):
        if self._ocr_started:
            return
        self._ocr_started = True
        def worker():
            try:
                from .. import ocr
                from ..config import CONFIG
                engine = ocr.get_engine(CONFIG)
                lines = engine.recognize(self.img)
                words = []
                dpr = self.dpr if not IS_WIN11 else 1.0
                for line in lines:
                    for w in line.words:
                        if dpr > 0 and dpr != 1.0:
                            r = QRect(int(w.x / dpr), int(w.y / dpr), int(w.w / dpr), int(w.h / dpr))
                        else:
                            r = QRect(int(w.x), int(w.y), int(w.w), int(w.h))
                        words.append((w, line, r))
                self.ocr_ready.emit(lines, words)
            except Exception as e:
                print("FreezeFrameOverlay OCR error:", e)
                try:
                    import traceback, datetime
                    with open("crash.log", "a", encoding="utf-8") as f:
                        f.write(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] FreezeFrameOverlay OCR error:\n{traceback.format_exc()}\n")
                except Exception:
                    pass
                self.ocr_ready.emit([], [])

        import threading
        t = threading.Thread(target=worker, name="OCRWorkerThread", daemon=True)
        t.start()

    def _on_ocr_finished(self, lines, words):
        self.lines = lines
        self.words = words
        self.is_scanning = False
        pos = self.mapFromGlobal(QCursor.pos())
        self._check_hover(pos)
        self.update()

    def _check_hover(self, pos):
        if self._is_dragging:
            return
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
        if (e.buttons() & Qt.LeftButton) and self._drag_start:
            dx = e.pos().x() - self._drag_start.x()
            dy = e.pos().y() - self._drag_start.y()
            if not self._is_dragging and (abs(dx) >= 5 or abs(dy) >= 5):
                self._is_dragging = True
            if self._is_dragging:
                self._drag_rect = QRect(self._drag_start, e.pos()).normalized()
                self.update()
                return

        self._check_hover(e.pos())
        super().mouseMoveEvent(e)

    def _request_close(self):
        if self.on_close:
            cb = self.on_close
            self.on_close = None
            cb()
        else:
            self.hide()
            self.close()

    def mousePressEvent(self, e):
        if self._close_btn_rect and self._close_btn_rect.contains(e.pos()):
            self._request_close()
            return
        if e.button() == Qt.LeftButton:
            self._drag_start = e.pos()
            self._is_dragging = False
            self._drag_rect = None
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            # 1. Завершение выделения рамкой (Drag-to-Select)
            if self._is_dragging and self._drag_rect and (self._drag_rect.width() >= 5 or self._drag_rect.height() >= 5):
                dragged_r = self._drag_rect
                self._is_dragging = False
                self._drag_rect = None
                self._drag_start = None

                # Находим все OCR-боксы, центры которых внутри рамки или пересекаются с ней
                selected = []
                for w, line, r in self.words:
                    c = r.center()
                    if dragged_r.contains(c) or dragged_r.intersects(r):
                        selected.append((w, line, r))

                if selected:
                    # Сортируем: строки сверху вниз, внутри строки слева направо
                    selected.sort(key=lambda it: (round(it[2].center().y() / max(1, it[2].height() * 0.7)), it[2].center().x()))

                    from .. import ocr
                    has_cjk = any(ocr.is_cjk_char(c) for it in selected for c in it[0].text)
                    words_clean = [ocr.clean_word(it[0].text) for it in selected if ocr.clean_word(it[0].text)]

                    if words_clean:
                        merged_text = "".join(words_clean) if has_cjk else " ".join(words_clean)

                        min_x = min(it[2].x() for it in selected)
                        min_y = min(it[2].y() for it in selected)
                        max_x = max(it[2].x() + it[2].width() for it in selected)
                        max_y = max(it[2].y() + it[2].height() for it in selected)
                        self.active_word_rect = QRect(min_x, min_y, max_x - min_x, max_y - min_y)
                        self.update()

                        if not IS_WIN11 and self.dpr != 1.0:
                            screen_x = self.x() + min_x
                            screen_y = self.y() + min_y
                        else:
                            screen_x = self.mon["left"] + min_x
                            screen_y = self.mon["top"] + min_y
                        if self.on_word_clicked:
                            self.on_word_clicked(merged_text, sentence, screen_x, screen_y, max_x - min_x, max_y - min_y)
                        return

            # 2. Одиночный клик по слову под курсором (сдвиг мыши < 5 px)
            self._is_dragging = False
            self._drag_rect = None
            self._drag_start = None

            if self.hovered_item:
                w, line, r = self.hovered_item
                from .. import ocr
                clean_w = ocr.clean_word(w.text)
                sentence = ocr.sentence_around(self.lines, line, w)
                if not IS_WIN11 and self.dpr != 1.0:
                    dpr = self.dpr
                    wx = int(w.x / dpr)
                    wy = int(w.y / dpr)
                    ww = int(w.w / dpr)
                    wh = int(w.h / dpr)
                    screen_x = self.x() + wx
                    screen_y = self.y() + wy
                else:
                    ww = int(w.w)
                    wh = int(w.h)
                    screen_x = self.mon["left"] + int(w.x)
                    screen_y = self.mon["top"] + int(w.y)
                self.active_word_rect = r.adjusted(-2, -2, 2, 2)
                self.update()
                if self.on_word_clicked:
                    self.on_word_clicked(clean_w, sentence, screen_x, screen_y, ww, wh)
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Escape, Qt.Key_Q):
            self._request_close()
            return
        super().keyPressEvent(e)

    def closeEvent(self, e):
        self.hide()
        if self.on_close:
            cb = self.on_close
            self.on_close = None
            cb()
        super().closeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        # 1. Стоп-кадр экрана
        if not self.pixmap.isNull():
            if not IS_WIN11 and self.dpr != 1.0:
                p.drawPixmap(self.rect(), self.pixmap)
            else:
                p.drawPixmap(0, 0, self.pixmap)

        # 2. Активное выбранное слово (золотистая рамка)
        if self.active_word_rect:
            p.setPen(QColor("#eab308"))
            p.setBrush(QColor(234, 179, 8, 70))
            p.drawRoundedRect(self.active_word_rect, 3, 3)

        # 3. Наведённое слово (голубая неоновая подсветка)
        if self.hovered_item and not self._is_dragging:
            _, _, r = self.hovered_item
            p.setPen(QColor("#38bdf8"))
            p.setBrush(QColor(56, 189, 248, 80))
            p.drawRoundedRect(r.adjusted(-3, -2, 3, 2), 3, 3)

        # 4. Рамка протягивания мыши (Drag-to-Select)
        if self._is_dragging and self._drag_rect:
            pen = QPen(QColor("#38bdf8"), 2, Qt.DashLine)
            p.setPen(pen)
            p.setBrush(QColor(56, 189, 248, 55))
            p.drawRoundedRect(self._drag_rect, 4, 4)

        # 5. Верхний стеклянный баннер управления
        from .i18n import t as _tr
        font = QFont("Segoe UI", 11)
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        fm = QFontMetrics(font)

        if self.is_scanning:
            status_text = "🧊 " + _tr("Заморозка экрана...") + " (" + _tr("сканирование слов...") + ")"
        else:
            status_text = "🧊 " + _tr("Заморозка экрана") + " • " + _tr("Кликните или выделите рамкой") + " • Esc / Alt+Q " + _tr("выход")

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