"""Захват экрана через mss."""
import mss
from PIL import Image

def grab_region(left: int, top: int, width: int, height: int) -> Image.Image:
    with mss.mss() as sct:
        raw = sct.grab({"left": left, "top": top, "width": width, "height": height})
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

def grab_monitor_at(x: int, y: int):
    """Скриншот монитора, на котором находится точка (x, y). Возвращает (Image, geometry)."""
    with mss.mss() as sct:
        mon = sct.monitors[1]
        for m in sct.monitors[1:]:
            if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]:
                mon = m
                break
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return img, mon

def region_around(x: int, y: int, w: int = 960, h: int = 320):
    """Область вокруг курсора (для режима словаря). Возвращает (Image, left, top)."""
    left, top = x - w // 2, y - h // 2
    img = grab_region(left, top, w, h)
    return img, left, top
