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
    "Переводчик и словари": "Translator && dictionaries",
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
    "Проверить OCR": "Check OCR",
    "Проверить": "Check",
    "Установлен": "Installed",
    "Не установлен": "Not installed",
    "✓ Установлен": "✓ Installed",
    "✗ Не установлен": "✗ Not installed",
    "Проверка Windows OCR": "Windows OCR Check",
    "Открыть параметры Windows": "Open Windows Settings",
    "Windows OCR для языка «%s» установлен и готов к работе!": "Windows OCR for «%s» is installed and ready to use!",
    "Tesseract найден в системе!": "Tesseract found in system!",
    "Tesseract OCR не найден в PATH.": "Tesseract OCR not found in system PATH.",
    "✗ Не найден": "✗ Not found",

    # --- настройки: игры ---
    "Делать оверлей активным окном": "Make overlay the active window",
    "Делать оверлей активным окном  ⓘ": "Make overlay the active window  ⓘ",
    "Словарь «%s» успешно установлен!\nВсего загружено %s словарных статей.":
        "Dictionary «%s» successfully installed!\nTotal %s term entries imported.",
    "Словарь установлен": "Dictionary installed",
    "Не удалось импортировать словарь:\n%s": "Failed to import dictionary:\n%s",
    "Ошибка установки словаря": "Dictionary installation error",
    "Вы уверены, что хотите удалить словарь «%s»?\nВсе словарные статьи будут стёрты.":
        "Are you sure you want to delete dictionary «%s»?\nAll term entries will be permanently deleted.",
    "Удаление словаря": "Delete dictionary",
    "Одни игры работают лучше при включённой функции, другие — при выключенной.":
        "Some games work better with it on, others with it off.",
    "Заморозка экрана": "Freeze screen",
    "Фиксирует изображение в момент нажатия горячей клавиши. Не ставит игры и программы на паузу.":
        "Freezes the image at the moment you press the hotkey. Does not pause games or apps.",
    "Авто-пауза игр и приложений": "Auto-pause games & apps",
    "Автоматически приостанавливает игры. Так вы точно не пропустите важные диалоги в кат-сценах.":
        "Automatically pauses games so you never miss important cutscene dialogue.",
    "Развернуть игру во весь экран": "Maximize game to full screen",
    "Растягивает оконную игру на весь экран. Используйте это, если эксклюзивный полноэкранный режим игры не позволяет отобразить WordSnap.":
        "Stretches a windowed game to full screen. Use this if the game's exclusive fullscreen mode prevents WordSnap from showing.",
    "Выбрать окно": "Pick window",
    "Часть заголовка окна (пусто — отключить):": "Part of the window title (empty — disable):",

    # --- настройки: слова ---
    "Автоматически сохранять слова": "Automatically save words",
    "Сохранять каждое вызванное слово в личный словарь. Если выключено — сохранение только по кнопке 🔖 в окне перевода.":
        "Save every looked up word to personal dictionary. If disabled, words are saved only by clicking 🔖 in the popup.",
    "Автообрезка скриншотов": "Auto-crop screenshots",
    "Автоматически обрезать скриншоты, оставляя только текст вокруг слова.":
        "Automatically crop screenshots to keep only the text around the word.",
    "Помечать повторяющиеся слова": "Mark duplicate words",
    "Показывать значок у слов, которые уже есть в словаре.":
        "Show an icon next to words that are already in the dictionary.",

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
    "Это слово уже есть в словаре": "This word is already in the dictionary",
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

    "Переводчик": "Translator",
    "Looktionary": "AI Dictionary",
    "Словарь (AI)": "AI Dictionary",
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

    # --- Anki ---
    "Anki": "Anki",
    "Включить интеграцию с Anki": "Enable Anki integration",
    "Добавление слов, определений, контекста и озвучки в колоду Anki через AnkiConnect.":
        "Add words, definitions, context and audio to Anki deck via AnkiConnect.",
    "Адрес сервера AnkiConnect": "AnkiConnect server address",
    "URL-адрес сервера AnkiConnect (по умолчанию http://127.0.0.1:8765).":
        "URL of the AnkiConnect server (default http://127.0.0.1:8765).",
    "Теги карточек": "Card tags",
    "Список тегов через пробел или запятую, добавляемых к создаваемым карточкам.":
        "Space or comma separated list of tags to add to created cards.",
    "Настройка карточек Anki...": "Configure Anki flashcards...",
    "Выбор колоды (Deck), модели (Model) и сопоставление полей ({expression}, {glossary} и др.).":
        "Choose deck, model and configure field mappings ({expression}, {glossary}, etc.).",
    "Настройка карточек Anki": "Anki Cards",
    "Anki Cards": "Anki Cards",
    "Deck": "Deck",
    "Model": "Model",
    "Field": "Field",
    "Value": "Value",
    "Expression": "Expression",
    "Проверить": "Check",
    "Повторить": "Retry",
    "Не удалось связаться с AnkiConnect.": "Could not connect to AnkiConnect.",
    "Тестовая карточка": "Test card",
    "Создать проверочную карточку со словом 'test' в Anki": "Create a verification card with the word 'test' in Anki",
    "Добавить слово в Anki": "Add word to Anki",
    "Добавить в Anki": "Add to Anki",
    "Добавлено в Anki": "Added to Anki",
    "Слово уже есть в Anki": "Word is already in Anki",
    "Карточка уже в Anki": "Card already in Anki",
    "Ошибка Anki": "Anki error",
    "Статус: <span style='color:#4caf50; font-weight:600;'>Подключено (%s)</span>":
        "Status: <span style='color:#4caf50; font-weight:600;'>Connected (%s)</span>",
    "Статус: <span style='color:#e0564b; font-weight:600;'>Ошибка подключения</span> <span style='color:#999; font-size:11px;'>(%s)</span>":
        "Status: <span style='color:#e0564b; font-weight:600;'>Connection error</span> <span style='color:#999; font-size:11px;'>(%s)</span>",
    "Статус: <span style='color:#999;'>Включите функцию интеграции с Anki</span>":
        "Status: <span style='color:#999;'>Enable Anki integration</span>",
    "Статус: <span style='color:#999;'>⏳ Проверка...</span>":
        "Status: <span style='color:#999;'>⏳ Checking...</span>",
    "✨ Автоматически (Новейшая версия)": "✨ Auto (Latest version)",
    "«Авто» всегда использует самую новую и мощную модель без ручных обновлений.":
        "'Auto' always uses the newest and most powerful model without manual updates.",

    # --- брендинг & статус ---
    "WordSnap — экранный переводчик и словарь": "WordSnap — on-screen translator and dictionary",
    "WordSnap — экранный переводчик": "WordSnap — screen translator",
    "Распознавание и перевод текста на экране...": "Recognizing and translating text on screen...",
    "Текст на экране не обнаружен.": "No text detected on screen.",
    "Ошибка перевода": "Translation error",
    "Под курсором не найден текст.": "No text found under cursor.",
    "OCR-ошибка": "OCR error",
    "…  загрузка": "…  loading",
    "Нет статьи в этом словаре.": "No entry in this dictionary.",
    "Использованный контекст": "Context used",
    "Этимология": "Etymology",
    "Показать примеры": "Show examples",
    "Сохранить слово в личный словарь": "Save word to personal dictionary",
    "Сохранено в личный словарь (нажмите, чтобы удалить)": "Saved to personal dictionary (click to remove)",

    # --- Anki & статус ---
    "Добавление в Anki...": "Adding to Anki...",
    "Слово уже есть в Anki (нажмите для повторного добавления)": "Word already in Anki (click to add again)",
    "Нет данных слова": "No word data",
    "Колода": "Deck",
    "Модель": "Model",
    "AnkiConnect недоступен": "AnkiConnect unavailable",
    "Тестовая карточка успешно создана в Anki!": "Test card successfully created in Anki!",
    "Не удалось создать карточку": "Failed to create card",
    "Успех": "Success",
    "Ошибка": "Error",
    "Отмена": "Cancel",
    "Сохранить": "Save",
    "(пусто)": "(empty)",
    "💡 Маркер {glossary} автоматически форматирует статьи офлайн-словарей (как в Yomitan) или ИИ. Также можно использовать {glossary-offline}, {glossary-ai} или конкретный словарь {single-glossary-...}.":
        "💡 The {glossary} marker automatically formats offline dictionary entries (like Yomitan) or AI. You can also use {glossary-offline}, {glossary-ai} or a specific dictionary {single-glossary-...}.",

    # --- словари & Yomitan ---
    "Офлайн-словарь Yomitan.": "Offline Yomitan dictionary.",
    "Офлайн-словарь Yomitan": "Offline Yomitan dictionary",
    "Установить офлайн-словарь Yomitan": "Install offline Yomitan dictionary",
    "Словарь установлен": "Dictionary installed",
    "Словарь «%s» успешно установлен!\nВсего загружено %s словарных статей.":
        "Dictionary “%s” successfully installed!\nTotal %s entries loaded.",
    "Ошибка установки словаря": "Dictionary installation error",
    "Не удалось импортировать словарь:\n%s": "Failed to import dictionary:\n%s",
    "Удаление словаря": "Delete dictionary",
    "Вы уверены, что хотите удалить словарь «%s»?\nВсе словарные статьи будут стёрты.":
        "Are you sure you want to delete dictionary “%s”?\nAll entries will be deleted.",
    "статей": "entries",
    "Автор/Источник": "Author/Source",
    "🔍  Быстрая проверка слова в этом словаре:": "🔍  Quick word test in this dictionary:",
    "🗑  Удалить этот словарь": "🗑  Delete this dictionary",
    "Найти": "Search",
    "Например: struggle, hello, house...": "e.g.: struggle, hello, house...",
    "Настроить  ›": "Configure  ›",
    "Выделить всё": "Select all",
    "Экспорт": "Export",

    # --- целевые окна & взаимодействие ---
    "Настройка целевого окна": "Target window setup",
    "Укажите заголовок или имя процесса игры/приложения, которое нужно автоматически ставить на паузу:":
        "Specify the title or process name of the game/app to automatically pause:",
    "Укажите заголовок или имя процесса игры/приложения, которое нужно растягивать на весь экран:":
        "Specify the title or process name of the game/app to stretch to full screen:",
    "Развернуть окно сейчас (тест)": "Stretch window now (test)",
    "Проверить паузу (на 3 сек)": "Test pause (for 3 sec)",
    "Отключить": "Disable",
    "Окно": "Window",
    "Фильтр приложений...": "Filter apps...",
    "Окно успешно развёрнуто!": "Window successfully stretched!",
    "Окно/процесс не найдены. Убедитесь, что приложение запущено.":
        "Window/process not found. Make sure the application is running.",
    "Выберите окно из списка запущенных приложений или введите часть заголовка/имени вручную:":
        "Select a window from the list of running apps or enter title/process manually:",
    "Процесс приостановлен на 3 секунды...": "Process paused for 3 seconds...",
    "Процесс возобновлён!": "Process resumed!",
    "Введите слово выше и нажмите «Найти» для проверки статей...":
        "Enter a word above and click 'Search' to test entries...",
    "Введите слово для поиска.": "Enter a word to search for.",
    "Слово «%s» не найдено в этом словаре.": "Word “%s” not found in this dictionary.",
    "Например: eldenring, zen.exe, game...": "e.g.: eldenring, zen.exe, game...",
    "#диалоги, #магия, #важное": "#dialogues, #magic, #important",
    "Укажите API-ключ Gemini в Настройках → ИИ-источники.":
        "Specify the Gemini API key in Settings → AI sources.",

    # --- мастер первого запуска & проверка ключей ---
    "Быстрый старт": "Quick setup",
    "Добро пожаловать в WordSnap!": "Welcome to WordSnap!",
    "Выберите язык интерфейса и тему оформления. Изменить их можно в любой момент.":
        "Choose interface language and theme. You can change them anytime.",
    "Интерфейс на русском языке": "Interface in Russian",
    "English interface language": "English interface language",
    "Стильная тёмная тема": "Stylish dark theme",
    "Светлая аккуратная тема": "Clean light theme",
    "Как в вашей Windows": "Follow Windows system",
    "Выберите основной режим работы": "Choose primary operation mode",
    "Как вы чаще всего будете использовать приложение? Режим можно менять в один клик.":
        "How will you mostly use the application? You can switch modes anytime.",
    "Режим словаря (Looktionary & Изучение языков)": "Dictionary mode (Looktionary & Study)",
    "Кликните по любому слову на экране в игре, книге или видео — всплывёт окно с транскрипцией, определением, озвучкой и кнопкой сохранения в Anki или личный словарь.":
        "Click any on-screen word in games, books or videos to view popup definitions, phonetics, audio, and save cards to Anki or personal dictionary.",
    "Экранный переводчик (Translator)": "On-screen translator",
    "Мгновенно распознаёт и переводит все строки на экране (диалоги, субтитры, кнопки меню) прямо поверх окна в их исходных позициях.":
        "Instantly translates all text on screen (dialogues, subtitles, menu buttons) right over the window in place.",
    "💡 Подсказка: в режиме переводчика зажатие Alt переключает на выбор отдельного слова.":
        "💡 Tip: in translator mode, holding Alt switches to single-word lookup.",
    "Подключение ИИ для умного перевода": "Connect AI for smart translations",
    "Нейросеть мгновенно исправляет OCR-опечатки, понимает игровой сленг и даёт живой перевод.":
        "Neural network fixes OCR typos on the fly, grasps gaming lore, and delivers natural translations.",
    "Groq (Рекомендуется)": "Groq (Recommended)",
    "Сверхбыстрый (<1 сек), бесплатный": "Ultra-fast (<1s), free",
    "Высокое качество, бесплатный": "High quality, free",
    "API-ключ:": "API key:",
    "Проверить": "Test key",
    "⏳ Проверка...": "⏳ Checking...",
    "✓ OK": "✓ OK",
    "✓ Работает": "✓ Working",
    "✗ Ошибка": "✗ Error",
    "Ключ пуст": "Key empty",
    "Пропустить шаг": "Skip step",
    "Ключ успешно проверен!": "Key verified successfully!",
    "Ключ успешно проверен и работает!": "Key verified successfully and works!",
    "Офлайн-словари и карточки Anki": "Offline dictionaries & Anki cards",
    "Вы можете добавить свои словари формата Yomitan (.zip) и сохранять карточки в Anki.":
        "You can add Yomitan (.zip) dictionaries and save cards into Anki.",
    "Офлайн-словари (мгновенный поиск без интернета)": "Offline dictionaries (instant offline lookup)",
    "Поддерживаются любые словари Yomitan/Yomichan в ZIP-архивах (например, wty-en-ru.zip).":
        "Supports any Yomitan/Yomichan dictionaries in ZIP archives (e.g. wty-en-ru.zip).",
    "Установить словарь (.zip)": "Install dictionary (.zip)",
    "Интеграция с Anki (AnkiConnect)": "Anki integration (AnkiConnect)",
    "⏳ Проверка подключения к AnkiConnect...": "⏳ Checking AnkiConnect connection...",
    "AnkiConnect обнаружен!": "AnkiConnect connected!",
    "Зелёный плюсик в окне словаря готов создавать карточки в колоду.":
        "The green plus button in dictionary popup is ready to create cards.",
    "AnkiConnect не обнаружен": "AnkiConnect not found",
    "Если вы используете Anki, просто включите плагин AnkiConnect (порт 8765). Вы всегда можете настроить его позже.":
        "If you use Anki, enable the AnkiConnect add-on (port 8765). You can always set this up later.",
    "Всё готово к работе!": "All set and ready!",
    "Основные настройки завершены. Вот несколько быстрых советов:":
        "Initial setup is complete. Here are quick tips:",
    "или средняя кнопка мыши (СКМ):": "or middle mouse button (MMB):",
    "наведите курсор на слово или текст на экране и нажмите горячую клавишу.":
        "hover over any word or text on screen and press the hotkey.",
    "Иконка в трее:": "Tray icon:",
    "WordSnap работает в фоновом режиме и всегда доступен около часов.":
        "WordSnap runs in background and is always available near clock.",
    "Полная кастомизация:": "Full customization:",
    "все настройки (хоткеи, колоды Anki, источники, оверлей) доступны в окне Настроек.":
        "all settings (hotkeys, Anki decks, sources, overlay) are available in Settings.",
    "Пропустить настройку": "Skip setup",
    "Назад": "Back",
    "Далее": "Next",
    "Начать работу": "Get started",
    "Запустить мастер первоначальной настройки": "Run initial setup wizard",
    "Пройти пошаговую настройку языка, темы, режима и ИИ заново.":
        "Run step-by-step setup for language, theme, mode and AI again.",
    "Заморозка экрана...": "Freezing screen...",
    "сканирование слов...": "scanning words...",
    "Кликните на слово": "Click on a word",
    "выход": "exit",
    "Под курсором нет текста. Для игр без курсора включите «Заморозка экрана» в Настройках.":
        "No text under cursor. For games without a cursor, enable 'Freeze screen' in Settings.",

    # --- дополнительные элементы интерфейса & диалоги ---
    "Язык интерфейса:": "Interface language:",
    "Тема оформления:": "Theme:",
    "Все языки": "All languages",
    "Все источники": "All sources",
    "Все уровни": "All levels",
    "По дате": "By date",
    "По уровню": "By level",
    "Вкл": "On",
    "Откл": "Off",
    "Озвучить": "Speak",
    "Режим словаря (AI & Изучение языков)": "Dictionary mode (AI & Language study)",
    "«Авто» всегда использует самую новую и быструю модель Flash.":
        "'Auto' always uses the newest and fastest Flash model.",
    "Бесплатный ключ за 30 сек: <a href='https://console.groq.com/keys' style='color:#60cdff;'>console.groq.com/keys</a> (можно пропустить и ввести позже).":
        "Free key in 30 sec: <a href='https://console.groq.com/keys' style='color:#60cdff;'>console.groq.com/keys</a> (can be skipped and entered later).",
    "Бесплатный ключ: <a href='https://aistudio.google.com' style='color:#60cdff;'>aistudio.google.com</a> (можно пропустить и ввести позже).":
        "Free key: <a href='https://aistudio.google.com' style='color:#60cdff;'>aistudio.google.com</a> (can be skipped and entered later).",
    "Выберите файл словаря Yomitan": "Select Yomitan dictionary file",
    "Словарь «%s» успешно установлен и активирован!": "Dictionary “%s” successfully installed and activated!",
    "установлен": "installed",
    "Anki: нет подключения к AnkiConnect (нажмите для проверки)":
        "Anki: no connection to AnkiConnect (click to check)",
    "Groq 400 (json_validate_failed): повторяем запрос без строгого response_format...":
        "Groq 400 (json_validate_failed): retrying request without strict response_format...",
    "Скачать словари (Wiktionary)": "Download dictionaries (Wiktionary)",
    "Скачать словари (Wiktionary / Yomitan)": "Download dictionaries (Wiktionary / Yomitan)",
    "🌐  Скачать словари (Wiktionary / Yomitan)": "🌐  Download dictionaries (Wiktionary / Yomitan)",
    "Включить сохранение карточек в Anki": "Enable saving cards to Anki",
    "Подробнее": "Details",
    "Как подключить Anki к WordSnap": "How to connect Anki to WordSnap",
    "Запустите приложение <b>Anki</b> на компьютере.": "Launch the <b>Anki</b> application on your PC.",
    "В верхнем меню Anki выберите <b>Инструменты (Tools) → Дополнения (Add-ons)</b>.":
        "In the top menu of Anki select <b>Tools → Add-ons</b>.",
    "Нажмите кнопку <b>Загрузить дополнения (Get Add-ons...)</b>.":
        "Click the button <b>Get Add-ons...</b>.",
    "В поле «Код» введите <b>2055492159</b> (плагин AnkiConnect) и нажмите <b>ОК</b>.":
        "In the 'Code' field enter <b>2055492159</b> (AnkiConnect add-on) and click <b>OK</b>.",
    "<b>Перезапустите Anki</b>, чтобы плагин активировался.":
        "<b>Restart Anki</b> to activate the add-on.",
    "После этого включите галочку интеграции, и WordSnap сможет автоматически сохранять карточки слов с переводом, контекстом и скриншотом!":
        "After that, enable the integration checkbox, and WordSnap will automatically save word cards with translation, context, and screenshots!",
    "Подключение Anki": "Anki connection",
    "Проверить снова": "Check again",
    "Понятно": "Got it",
    "Распаковка и обработка базы терминов...": "Extracting and processing terms database...",
    "Индексация базы": "Indexing database",
    "Назначение горячей клавиши": "Assign Hotkey",
    "Нажмите комбинацию клавиш на клавиатуре": "Press key combination on your keyboard",
    "Нажмите желаемую комбинацию (например Alt+Q или Ctrl+Shift+A). Esc — отмена.":
        "Press desired combination (e.g. Alt+Q or Ctrl+Shift+A). Esc to cancel.",
    "Назначить": "Assign",
    "Установка словаря": "Dictionary installation",
    "Выбор и выделение слов": "Select and mark words",
    "Все слова": "All words",
    "За сегодня": "Today",
    "За последние 7 дней": "Last 7 days",
    "За последние 30 дней": "Last 30 days",
    "Выбрать диапазон дат...": "Select date range...",
    "Снять выделение": "Clear selection",
    "Выбор периода дат": "Select Date Range",
    "Начальная дата:": "Start date:",
    "Конечная дата:": "End date:",
    "Выбрать": "Select",
    "По дате (сначала новые)": "By date (newest first)",
    "По дате (сначала старые)": "By date (oldest first)",
    "По уровню (A1 → C2)": "By level (A1 → C2)",
    "По уровню (C2 → A1)": "By level (C2 → A1)",
    "Порядок сортировки (по убыванию / возрастанию)": "Sort order (descending / ascending)",
    "Сначала новые (по убыванию)": "Newest first (descending)",
    "Сначала старые (по возрастанию)": "Oldest first (ascending)",
    "От простых к сложным (A1 → C2)": "Easy to hard (A1 → C2)",
    "От сложных к простым (C2 → A1)": "Hard to easy (C2 → A1)",

    # --- поддержка проекта и благодарность ---
    "Поддержать разработчика": "Support the developer",
    "❤️ Поддержать": "❤️ Support",
    "Поддержать": "Support",
    "Поддержать разработку": "Support development",
    "Открыть страницу поддержки разработчика на DonationAlerts": "Open developer support page on DonationAlerts",
    "Спасибо за поддержку! ❤️": "Thank you for your support! ❤️",
    "Огромное спасибо за поддержку! ❤️": "Huge thanks for your support! ❤️",
    "Огромное спасибо за поддержку!": "Huge thanks for your support!",
    "Каждый донат помогает развивать WordSnap и делать его лучше.": "Every donation helps WordSnap grow and become even better.",
    "Перейти к донату": "Go to DonationAlerts",
    "Закрыть": "Close",
}


def t(s: str) -> str:
    """Перевести строку на язык интерфейса (en) или вернуть как есть (ru)."""
    if CONFIG.get("ui_lang", "ru") == "en":
        if s in _EN:
            return _EN[s]
        # Если строка заканчивается на двоеточие, пробуем перевести основу
        if s.endswith(":") and s[:-1] in _EN:
            return _EN[s[:-1]] + ":"
        # Если строка с ведущими/завершающими пробелами
        stripped = s.strip()
        if stripped in _EN:
            prefix = s[:len(s) - len(s.lstrip())]
            suffix = s[len(s.rstrip()):]
            return prefix + _EN[stripped] + suffix
        for k, v in _EN.items():
            if k.strip() == stripped:
                prefix = s[:len(s) - len(s.lstrip())]
                suffix = s[len(s.rstrip()):]
                return prefix + v.strip() + suffix
        return _EN.get(s, s)
    return s
