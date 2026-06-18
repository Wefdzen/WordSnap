"""Глобальные горячие клавиши (клавиатура + мышь) через pynput.
Сигналы Qt пробрасываются в главный поток."""
from PySide6.QtCore import QObject, Signal
from pynput import keyboard, mouse

MODS = ("alt", "ctrl", "shift")

# pynput-клавиша модификатора -> имя
_MOD_KEYS = {}
for _name in MODS:
    for _suf in ("", "_l", "_r", "_gr"):
        _k = getattr(keyboard.Key, _name + _suf, None)
        if _k is not None:
            _MOD_KEYS[_k] = _name

def parse_hotkey(hotkey: str):
    """'alt+q' -> ({'alt'}, 'q'). Возвращает (множество модификаторов, основная клавиша)."""
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    mods = {p for p in parts if p in MODS}
    mains = [p for p in parts if p not in MODS and p not in ("win", "cmd")]
    return mods, (mains[-1] if mains else "q")

def _key_matches(k, target: str) -> bool:
    """Совпадает ли нажатая клавиша с целевой. Сверяем и по символу, и по vk —
    потому что при зажатом Alt символ приходит как None, а vk остаётся (Q -> 0x51)."""
    char = getattr(k, "char", None)
    if char and char.lower() == target:
        return True
    vk = getattr(k, "vk", None)
    if vk is not None and len(target) == 1 and target.isalnum():
        try:
            return chr(vk).lower() == target
        except ValueError:
            return False
    return False

class HotkeyManager(QObject):
    triggered = Signal(int, int)          # x, y курсора в момент нажатия
    alt_state = Signal(bool)              # для режима переводчика (удержание Alt)
    escaped = Signal()                    # глобальный Esc — закрыть попап/оверлей

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self._kb = None
        self._mouse = None
        self._alt_listener = None

    # ------------------------------------------------------------------
    def start(self):
        self.stop()
        self._req_mods, self._main_key = parse_hotkey(self.cfg.get("hotkey", "alt+q"))
        self._mods_down: set[str] = set()
        self._key_armed = True  # защита от автоповтора при удержании
        try:
            def on_press(k):
                if k == keyboard.Key.esc:
                    self.escaped.emit()
                    return
                name = _MOD_KEYS.get(k)
                if name:
                    self._mods_down.add(name)
                    return
                if (self._key_armed and self._req_mods <= self._mods_down
                        and _key_matches(k, self._main_key)):
                    self._key_armed = False
                    self._fire()

            def on_release(k):
                name = _MOD_KEYS.get(k)
                if name:
                    self._mods_down.discard(name)
                elif _key_matches(k, self._main_key):
                    self._key_armed = True

            self._kb = keyboard.Listener(on_press=on_press, on_release=on_release)
            self._kb.daemon = True
            self._kb.start()
        except Exception as e:
            print("hotkey error:", e)

        if self.cfg.get("mouse_hotkey_enabled") and self.cfg.get("mouse_hotkey_button") != "none":
            btn_name = self.cfg.get("mouse_hotkey_button", "middle")
            btn = {"middle": mouse.Button.middle,
                   "x1": getattr(mouse.Button, "x1", None),
                   "x2": getattr(mouse.Button, "x2", None)}.get(btn_name)
            mod = self.cfg.get("mouse_hotkey_modifier", "none")
            self._mod_down = {"value": mod == "none"}

            if mod != "none":
                mod_key = {"alt": keyboard.Key.alt, "ctrl": keyboard.Key.ctrl,
                           "shift": keyboard.Key.shift}[mod]
                def on_press(k):
                    if k in (mod_key, getattr(keyboard.Key, mod + "_l", None),
                             getattr(keyboard.Key, mod + "_r", None)):
                        self._mod_down["value"] = True
                def on_release(k):
                    if k in (mod_key, getattr(keyboard.Key, mod + "_l", None),
                             getattr(keyboard.Key, mod + "_r", None)):
                        self._mod_down["value"] = False
                self._alt_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
                self._alt_listener.daemon = True
                self._alt_listener.start()

            if btn is not None:
                def on_click(x, y, button, pressed):
                    if pressed and button == btn and self._mod_down["value"]:
                        self.triggered.emit(int(x), int(y))
                self._mouse = mouse.Listener(on_click=on_click)
                self._mouse.daemon = True
                self._mouse.start()

    def stop(self):
        for l in (self._kb, self._mouse, self._alt_listener):
            if l:
                try:
                    l.stop()
                except Exception:
                    pass
        self._kb = self._mouse = self._alt_listener = None

    def restart(self):
        self.start()

    def _fire(self):
        pos = mouse.Controller().position
        self.triggered.emit(int(pos[0]), int(pos[1]))
