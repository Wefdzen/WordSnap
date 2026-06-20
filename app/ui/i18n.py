"""Локализация интерфейса (русский / английский).

Использование:  from .i18n import t   →   t("Настройки")
Русский — язык по умолчанию: для него t() просто возвращает исходную строку.
Для английского берётся перевод из словаря _EN; если перевода нет — возвращается
русский оригинал (ничего не ломается). Язык читается из настроек (ui_lang) и
меняется после перезапуска приложения.
"""
from ..config import CONFIG

# Английские переводы по русскому оригиналу (ключ — текст в коде).
_EN = {
    # --- трей ---
    "Распознать текст": "Recognize text",
    "Выход": "Quit",
    "Lookupper — экранный переводчик": "Lookupper — screen translator",

    # --- вкладки ---
    "Слова": "Words",
    "Переводчик и словари": "Translator & dictionaries",
    "Настройки": "Settings",

    # --- настройки: секции ---
    "Общие": "General",
    "Внешний вид": "Appearance",
    "Горячие клавиши": "Hotkeys",
    "Распознавание текста на экране (OCR)": "On-screen text recognition (OCR)",
    "Взаимодействие с играми и приложениями": "Games & apps interaction",
    "ИИ-источники": "AI sources",

    # --- настройки: внешний вид ---
    "Тема оформления": "Theme",
    "Тёмная, светлая или как в системе.": "Dark, light or follow the system.",
    "Тёмная": "Dark",
    "Светлая": "Light",
    "Системная": "System",
    "Язык интерфейса": "Interface language",
    "Язык меню и настроек приложения.": "Language of the app menus and settings.",

    # --- настройки: общие ---
    "Режим переводчика": "Translator mode",
    "Помещает перевод поверх текста. Удерживайте Alt, чтобы\nсмотреть отдельные слова в режиме словаря.":
        "Places the translation over the text. Hold Alt to\nlook up single words in dictionary mode.",
    "Режим словаря (Режим изучения)": "Dictionary mode (Study mode)",
    "Определение и перевод слов во всплывающем окне.\nСохраняет слова в личный словарь.":
        "Definition and translation of words in a popup.\nSaves words to your personal dictionary.",
    "Режим приложения": "App mode",
    "Запускать при старте Windows": "Launch on Windows startup",

    # --- настройки: горячие клавиши ---
    "Горячая клавиша": "Hotkey",
    "Горячая кнопка мыши": "Mouse hotkey",
    "Без клавиши": "No key",
    "Средняя кнопка": "Middle button",
    "Боковая 1 (X1)": "Side 1 (X1)",
    "Боковая 2 (X2)": "Side 2 (X2)",
    "Отключено": "Disabled",

    # --- настройки: OCR ---
    "Движок OCR": "OCR engine",
    "Рекомендуемый (Windows OCR)\nМаксимальная точность без установки.":
        "Recommended (Windows OCR)\nBest accuracy, nothing to install.",
    "Tesseract\nТребует установленный Tesseract OCR.":
        "Tesseract\nRequires Tesseract OCR to be installed.",
    "Язык распознавания": "Recognition language",
    "Выберите язык, соответствующий тексту на экране. Иначе распознавание может быть неправильным.":
        "Pick the language matching the on-screen text, otherwise recognition may be wrong.",

    # --- настройки: игры ---
    "Делать оверлей активным окном  ⓘ": "Make overlay the active window  ⓘ",
    "Одни игры работают лучше при включённой функции, другие — при выключенной.":
        "Some games work better with it on, others with it off.",
    "Заморозка экрана": "Freeze screen",
    "Фиксирует изображение в момент нажатия горячей клавиши. Не ставит игры и программы на паузу.":
        "Freezes the image at the moment you press the hotkey. Does not pause games or apps.",
    "Авто-пауза игр и приложений": "Auto-pause games & apps",
    "Автоматически приостанавливает игры. Так вы точно не пропустите важные диалоги в кат-сценах.":
        "Automatically pauses games so you never miss important cutscene dialogue.",
    "Развернуть игру во весь экран": "Maximize game to full screen",
    "Растягивает оконную игру на весь экран. Используйте это, если эксклюзивный полноэкранный режим игры не позволяет отобразить Lookupper.":
        "Stretches a windowed game to full screen. Use this if the game's exclusive fullscreen mode prevents Lookupper from showing.",
    "Выбрать окно": "Pick window",
    "Часть заголовка окна (пусто — отключить):": "Part of the window title (empty — disable):",

    # --- настройки: слова ---
    "Автоматически сохранять слова": "Automatically save words",
    "Автообрезка скриншотов": "Auto-crop screenshots",
    "Автоматически обрезать скриншоты, оставляя только текст вокруг слова.":
        "Automatically crop screenshots to keep only the text around the word.",

    # --- настройки: ИИ ---
    "Провайдер": "Provider",
    "Groq отвечает быстрее 1 секунды. Можно выбрать Google Gemini.":
        "Groq answers in under a second. You can also choose Google Gemini.",
    "Groq — быстрый": "Groq — fast",
    "Google Gemini": "Google Gemini",
    "API-ключ Groq": "Groq API key",
    "Бесплатно: console.groq.com/keys": "Free: console.groq.com/keys",
    "Модель Groq": "Groq model",
    "70b — точнее, 8b-instant — быстрее.": "70b — more accurate, 8b-instant — faster.",
    "API-ключ Gemini": "Gemini API key",
    "aistudio.google.com → Get API key.": "aistudio.google.com → Get API key.",
    "Модель Gemini": "Gemini model",
    "Показать": "Show",
    "Скрыть": "Hide",
    "Изменения применятся после перезапуска. Перезапустить сейчас?":
        "Changes will apply after a restart. Restart now?",
    "Добавьте API-ключ в Настройках → ИИ-источники.":
        "Add an API key in Settings → AI sources.",

    # --- виджеты ---
    "Вкл.": "On",
    "Откл.": "Off",

    # --- слова: список/панель ---
    "Сегодня": "Today",
    "Вчера": "Yesterday",
    "Без источника": "No source",
    "  Все языки": "  All languages",
    "  Все источники": "  All sources",
    "Поиск": "Search",
    "  Выделить всё": "  Select all",
    "  Удалить": "  Delete",
    "  Экспорт": "  Export",
    "Некоторые данные отсутствуют или неполные.": "Some data is missing or incomplete.",
    "Получить недостающие данные": "Fetch missing data",
    "Режим просмотра": "View mode",
    "Режим редактирования": "Edit mode",
    "Здесь появятся сохранённые слова.\nНажмите горячую клавишу над словом на экране.":
        "Saved words will appear here.\nPress the hotkey over a word on the screen.",
    "Найдено в": "Found in",
    "Открыть скриншот": "Open screenshot",
    # статистика / сортировка / фильтры / теги / избранное
    "Всего": "Total",
    "Всего слов": "Total words",
    "Новые": "New",
    "Избранные": "Favorites",
    "Только избранные": "Favorites only",
    "В избранное": "Add to favorites",
    "Без уровня": "No level",
    "  По дате": "  By date",
    "  По уровню": "  By level",
    "  Все уровни": "  All levels",
    "Теги (через запятую)": "Tags (comma-separated)",

    # --- слова: карточка/редактирование ---
    "Словарная форма": "Dictionary form",
    "Слово в тексте": "Word in text",
    "Определение": "Definition",
    "Уровень (CEFR)": "Level (CEFR)",
    "Транскрипция": "Transcription",
    "Часть речи / пометы": "Part of speech / labels",
    "Синонимы": "Synonyms",
    "Лингвистическая информация": "Linguistic information",
    "Детали источника": "Source details",
    "Приложение": "Application",
    "Заголовок окна": "Window title",
    "Перевод": "Translation",
    "Контекст": "Context",
    "Перевод слова": "Word translation",
    "Перевод контекста": "Context translation",

    # --- слова: диалоги ---
    "Удалить": "Delete",
    "Удалить слово «%s»?": "Delete the word “%s”?",
    "Удалить выбранные слова (%d)?": "Delete selected words (%d)?",
    "Экспорт слов": "Export words",
    "Язык для экспорта:": "Language to export:",
    "Источник для экспорта:": "Source to export:",
    "Начиная со слова (до самого нового):": "Starting from word (up to the newest):",
    "  Все слова": "  All words",

    # --- переводчик и словари ---
    "Переводчик": "Translator",
    "Looktionary": "Looktionary",
    "Oxford (Английский → Русский)": "Oxford (English → Russian)",
    "ИИ-переводчик экранного текста. Переводит с учётом контекста, особенностей запущенного приложения и игрового лора, а также показывает точное значение отдельных слов.":
        "AI translator for on-screen text. Translates with context, the running app and game lore in mind, and shows the exact meaning of single words.",
    "ИИ-словарь для изучающих языки. Даёт точное значение слов в контексте с качественной озвучкой. Предоставляет все данные для сохранения слов: перевод, начальную форму, транскрипцию, синонимы и другие детали.":
        "AI dictionary for language learners. Gives the exact meaning of words in context with quality pronunciation. Provides all data to save words: translation, base form, transcription, synonyms and more.",
    "Офлайн-словарь. Базовые определения и переводы без подключения к интернету.":
        "Offline dictionary. Basic definitions and translations without an internet connection.",
    "✥  Перетащите, чтобы изменить порядок отображения в режиме словаря":
        "✥  Drag to change the display order in dictionary mode",
    "＋  Установить офлайн-словари": "＋  Install offline dictionaries",
    "Установить офлайн-словарь": "Install offline dictionary",
    "Язык перевода": "Translation language",
    "На какой язык переводить распознанный на экране текст.":
        "Which language to translate the on-screen text into.",
    "Скрыть перевод в режиме словаря": "Hide translation in dictionary mode",
    "Перевод будет скрыт под спойлером.": "The translation will be hidden under a spoiler.",
    "Язык определения": "Definition language",
    "На каком языке показывать определение слова.":
        "Which language to show the word's definition in.",
    "Язык перевода слова": "Word translation language",
    "На какой язык переводить само слово.":
        "Which language to translate the word itself into.",
    "Скрыть перевод слова": "Hide word translation",
    "Слот офлайн-словаря. Используется свободный словарь (dictionaryapi.dev) для английских слов; собственные офлайн-словари можно подключить кнопкой слева.":
        "Offline dictionary slot. Uses the free dictionaryapi.dev for English words; your own offline dictionaries can be added with the button on the left.",
}


def t(s: str) -> str:
    """Перевести строку на язык интерфейса (en) или вернуть как есть (ru)."""
    if CONFIG.get("ui_lang", "ru") == "en":
        return _EN.get(s, s)
    return s
