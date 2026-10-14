<p align="center">
  <img src="assets/icon.png" width="100" alt="WordSnap">
</p>

<h1 align="center">WordSnap v1.3.0</h1>

<p align="center">
  <b>Instant on-screen OCR translator, offline Yomitan dictionary & Anki study cards for Windows.</b><br>
  Hover and look up words anywhere in 3D games, visual novels, videos, PDFs, manga, and desktop apps.
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> • <a href="README_RU.md"><b>Русский</b></a> • <a href="https://www.donationalerts.com/r/wefdzen"><b>Support Developer ❤️</b></a>
</p>

<p align="center">
  <img src="assets/app.jpg" width="820" alt="WordSnap">
</p>

---

## ⚡ Key Features

- **Instant On-Screen Lookup** — Fast native Windows OCR (or Tesseract). Press `Alt+Q` or mouse button, and an adaptive translation popup appears next to the word.
- **Freeze Screen Mode for Games** — Tailor-made for 3D/FPS shooters and controller gameplay: freezes the frame pixel-perfect, unlocks the mouse cursor, interactively highlights words on hover, and auto-pauses the game process.
- **Offline Yomitan (.zip) Dictionaries** — 100% offline, morphological de-inflection (lemmatization), frequency tags, phonetic readings, and built-in dictionary manager.
- **Dual AI Translation (Groq & Google Gemini)** — Context-aware sentence translation tailored to game lore, plus Looktionary cards with CEFR level (A1–C2), synonyms, and definitions.
- **1-Click Anki Integration** — Direct connection via AnkiConnect: create flashcards with cropped scene screenshots, sentence context, audio TTS, and duplicate detection.
- **Personal Vocabulary ("Words" tab)** — Review saved words with original scene screenshots, TTS pronunciation, date/CEFR/tag filters, and export to CSV, JSON, and Anki TSV.
- **Fluent UI for Windows 10/11** — Modern dark/light themes, native rounded corners, and system tray minimization with zero-drift window position persistence.

---

## 📥 Downloads (Windows 10 / 11)

Pre-built binaries are available in **[Releases](../../releases)**:

| Distribution | Description | Download |
|---|---|---|
| **Installer (Setup)** | Standard Windows installer with shortcuts and uninstaller | [`WordSnap-1.3.0-Setup.exe`](../../releases) |
| **Portable (ZIP)** | Zero-installation, extract and run anywhere (e.g. USB drive) | [`WordSnap-1.3.0-Portable.zip`](../../releases) |

---

## ⌨️ Default Keyboard Shortcuts

| Shortcut | Scope | Action |
|---|---|---|
| `Alt+Q` | Global | Recognize text under cursor / open lookup |
| `Esc` / `✕` | Overlay / Popup | Dismiss translation / unfreeze screen |
| `Ctrl+F` | Words tab | Focus search bar |
| `Space` | Words tab | Speak selected word (TTS) |
| `Ctrl+D` | Words tab | Toggle favorite (★) |
| `Delete` | Words tab | Delete selected word |
| `↑` / `↓` | Words tab | Previous / next word |

---

## 🚀 Running from Source

### Prerequisites
- Windows 10 / 11
- Python 3.11+

```bash
git clone https://github.com/Wefdzen/WordSnap.git
cd WordSnap
pip install -r requirements.txt
python main.py
```

### Build Executable & Installer:
```bash
python build_dist.py
```
Output files (`.zip` and `.exe`) are saved to the `release/` folder.

---

## 💖 Support the Project

If WordSnap helps you learn languages and enjoy foreign games:
👉 **[DonationAlerts](https://www.donationalerts.com/r/wefdzen)**

---

## License

[PolyForm Noncommercial License 1.0.0](LICENSE) — Free for personal and non-commercial use.
