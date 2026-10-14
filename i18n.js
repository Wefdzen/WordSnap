/**
 * WordSnap Website i18n System (EN / RU)
 * Instant bilingual switching with persistent localStorage preference
 */

(function () {
  'use strict';

  const TRANSLATIONS = {
    en: {
      // Document Metadata
      metaTitle: "WordSnap — Instant On-Screen OCR Translator & Offline Yomitan for Windows",
      metaDesc: "Instant on-screen OCR translator, offline Yomitan dictionary & Anki study cards for Windows 10/11. Hover and look up words anywhere in 3D games, visual novels, manga, videos, and desktop apps.",

      // Navigation
      navFeatures: "Features",
      navFreeze: "Freeze Mode",
      navAnki: "Anki Sync",
      navShortcuts: "Shortcuts",
      navDownloads: "Downloads",
      navFaq: "FAQ",

      // Hero Section
      heroVersion: "For Windows 10 & 11",
      heroTitle: 'Instant on-screen OCR<br><span class="title-accent">& offline dictionaries.</span>',
      heroDesc: "Look up words anywhere in 3D games, visual novels, manga, videos, and desktop apps. Freeze screen mode, offline Yomitan engine, and 1-click Anki study flashcards.",
      heroBtnExe: "Download for Windows (.exe)",
      heroBtnZip: "Portable (.zip)",
      heroBtnGh: "GitHub",
      heroPickerLabel: "Try lookup:",

      // Popup Simulator Card
      popupBtnAnkiTitle: "Add word to Anki (AnkiConnect)",
      popupBtnFavTitle: "Save word to vocabulary library",
      popupLblTranslator: 'Translator <span class="source-sparkle">✦</span>',
      popupLblDict: 'AI Dictionary <span class="source-sparkle">✦</span>',
      popupAudioNormalTitle: "Pronounce word (Normal speed)",
      popupAudioSlowTitle: "Pronounce word (Slow speed)",
      popupContextBtn: "Context used",
      popupOcrActive: "Windows Media OCR • 100% confidence",
      popupAnkiHint: "<span>＋</span> AnkiConnect ready",

      // Ticker Ribbon
      tickerOcr: "Direct Windows OCR",
      tickerFreeze: "Freeze Screen Gaming Mode",
      tickerYomitan: "100% Offline Yomitan (.zip)",
      tickerAi: "Dual AI (Groq & Gemini)",
      tickerAnki: "1-Click AnkiConnect Sync",
      tickerCrop: "Scene Screenshot Crops",

      // Bento Grid Features
      featBadge: "Core Architecture",
      featTitle: "Engineered for seamless gaming & study.",
      featDesc: "No more pausing your flow, Alt-Tabbing to web browsers, or copying Kanji manually.",

      featC1Title: "Native Windows OCR",
      featC1Desc: "Direct WinRT Media OCR engine delivers sub-frame recognition with zero cloud dependency and low CPU footprint.",

      featC2Title: "Freeze Screen Mode",
      featC2Desc: "Freezes fast 3D camera frames, unlocks mouse cursor, and auto-pauses background game processes so you never miss dialogue.",

      featC3Title: "Offline Yomitan (.zip)",
      featC3Desc: "Import any Yomitan dictionary archive. Complete offline morphological de-inflection, pitch accents, and frequency tags.",

      featC4Title: "Dual AI Lore Translation",
      featC4Desc: "Integrate Groq (Llama 3) and Gemini 2.5 Flash for contextual lore explanations, CEFR levels, and nuanced sentence translations.",

      featC5Title: "1-Click Anki Sync",
      featC5Desc: "Direct connection via AnkiConnect: automatically captures scene screenshot crop, context line, audio TTS, and checks duplicates.",

      featC6Title: "Words Library & Export",
      featC6Desc: "Review saved words with original scene screenshots, TTS voice replay, and export to CSV, JSON, or Anki TSV format.",

      // Freeze Mode Deep Dive
      freezeBadge: "Gaming Breakthrough",
      freezeTitle: "No more dying while reading dialogue.",
      freezeP1: "In fast-paced 3D games (Elden Ring, Genshin Impact, Cyberpunk), mouse movement is locked to the camera and subtitles disappear in 2 seconds.",
      freezeP2: "WordSnap solves this with <strong>Freeze Screen Mode</strong>:",
      freezeLi1: "<strong>Instant Frame Freeze:</strong> Captures the exact frame at native resolution without lag.",
      freezeLi2: "<strong>Cursor Unlock:</strong> Unbinds the mouse from 3D camera controls so you can hover freely.",
      freezeLi3: "<strong>Process Auto-Pause:</strong> Optionally halts the game process so enemies and cutscene timers freeze.",
      freezeLi4: "<strong>Instant Resume:</strong> Press Esc to unfreeze seamlessly and jump back into the action.",
      freezeBtn: "Download WordSnap",

      // Anki Flashcard Sync Showcase
      ankiBadge: "Study Workflow",
      ankiTitle: "Turn every game scene into an Anki flashcard.",
      ankiDesc: "Direct integration via AnkiConnect. Never copy-paste text or take manual screenshots again.",
      ankiPreviewTitle: "Anki Card Preview",
      ankiDeckChip: "Deck: Gaming Vocab",
      ankiCropTag: "Auto Cropped Scene",
      ankiMeaning: "<strong>Meaning:</strong> inform, notify, let know.",
      ankiAudioAttached: "[Audio: TTS Pronunciation Attached]",

      ankiColTitle: "Automate your immersion deck.",
      ankiColDesc: "With traditional tools, making a gaming flashcard takes 2 minutes per word. With WordSnap, it takes 0.5 seconds:",
      ankiLi1: "<strong>Context Sentence Extraction:</strong> WordSnap captures the full line around the word.",
      ankiLi2: "<strong>Automatic Screen Crop:</strong> Preserves the visual context in your Anki deck.",
      ankiLi3: "<strong>TTS Audio Generation:</strong> Attaches audio pronunciation directly to the card.",
      ankiLi4: "<strong>Duplicate Protection:</strong> Prevents clutter by detecting previously saved words.",
      ankiDocBtn: "View Documentation →",

      // Shortcuts Matrix
      scBadge: "Keyboard Reference",
      scTitle: "Intuitive shortcuts for high-speed lookup.",
      scDesc: "Designed to never interrupt your gameplay. Fully customizable in Settings.",
      scThShortcut: "Shortcut",
      scThScope: "Scope",
      scThAction: "Action",

      scR1Scope: "Global (Any App / Game)",
      scR1Action: "Recognize text under cursor & open lookup popup",
      scR2Scope: "Overlay / Popup",
      scR2Action: "Dismiss translation & unfreeze screen immediately",
      scR3Scope: "Words Tab",
      scR3Action: "Speak selected word (Audio TTS pronunciation)",
      scR4Scope: "Words Tab",
      scR4Action: "Focus search bar to filter saved vocabulary",
      scR5Scope: "Words Tab",
      scR5Action: "Toggle favorite (★) status for word",
      scR6Scope: "Words Tab",
      scR6Action: "Delete selected word from history",
      scR7Scope: "Words Tab",
      scR7Action: "Navigate between previous and next words",

      // Downloads Hub
      dlBadge: "Downloads",
      dlTitle: "Get WordSnap for Windows 10 & 11.",
      dlDesc: "Free for personal use. Choose between standard installer or portable archive.",
      dlRecommended: "Recommended",
      dlC1Title: "Standard Installer",
      dlC1Meta: "Windows Setup executable (.exe)<br>Automatic Start Menu & Desktop shortcuts, clean uninstaller.",
      dlC1Btn: "Download Setup (.exe)",
      dlC2Title: "Portable Edition",
      dlC2Meta: "Zero-install standalone archive (.zip)<br>Extract and run anywhere, including USB thumb drives.",
      dlC2Btn: "Download Portable (.zip)",

      dlSrcStrong: "Prefer running from Python source?",
      dlSrcSpan: "Requires Python 3.11+ on Windows 10/11",
      dlSrcCopyTitle: "Copy git clone command",

      // FAQ Section
      faqBadge: "Questions & Answers",
      faqTitle: "Frequently Asked Questions",
      faqDesc: "Everything you need to know about setting up and using WordSnap.",

      faqQ1: "Does WordSnap work inside fullscreen 3D games?",
      faqA1: "Yes! For borderless windowed and windowed fullscreen games, WordSnap works natively. In games that capture the mouse cursor, WordSnap's <strong>Freeze Screen Mode</strong> temporarily pauses the frame, releases the hardware cursor, and lets you hover and look up any word effortlessly without breaking your game session.",

      faqQ2: "Do I need an internet connection for dictionary lookups?",
      faqA2: "No! WordSnap's core Yomitan dictionary engine is 100% offline. Morphological de-inflection, definitions, frequency numbers, and pitch accents operate locally on your machine. An internet connection is only needed if you choose to enable the optional Groq or Google Gemini AI lore translation modules.",

      faqQ3: "How does the Anki integration work?",
      faqA3: "WordSnap connects to your local desktop Anki via the popular AnkiConnect plugin (code: 2055492159). With a single click (or hotkey), WordSnap crops the in-game scene, extracts the dialogue sentence, generates audio pronunciation, and creates a ready-to-study flashcard in your chosen Anki deck.",

      faqQ4: "Is WordSnap free and safe to use?",
      faqA4: "Yes! WordSnap is released under the PolyForm Noncommercial License 1.0.0 and is completely free for personal use. It has no advertisements, no tracking analytics, and does not transmit your screen content to remote servers. All OCR is executed on your local Windows system.",

      faqQ5: "What languages and dictionaries are supported?",
      faqA5: "WordSnap supports any standard Yomitan (.zip) dictionary. It comes with built-in presets for Japanese (JMDict, KireiCake, Daijirin, JMnedict), English, and English-Russian dictionaries. You can also import any custom community Yomitan dictionary with a single click.",

      // Footer
      footerDesc: "The instant on-screen OCR translator & offline Yomitan dictionary engineered for gaming and immersion learning on Windows.",
      footerHNav: "Navigation",
      footerHComm: "Community",
      footerLnkFeatures: "Features",
      footerLnkFreeze: "Freeze Screen",
      footerLnkAnki: "Anki Sync",
      footerLnkShortcuts: "Shortcuts",
      footerLnkDownloads: "Downloads",
      footerLnkGh: "GitHub Repository",
      footerLnkReleases: "Releases & Changelog",
      footerLnkIssues: "Report an Issue",
      footerLnkLicense: "PolyForm License",
      footerCopy: '© 2026 WordSnap. Created by <a href="https://github.com/Wefdzen" target="_blank" rel="noopener noreferrer" style="color: var(--text-primary); text-decoration: none;">Wefdzen</a>. Free for personal use.',
      footerOs: "Windows 10 & 11 • 64-bit",
      footerSupport: "Support Developer ❤️",

      // Interactive UI notifications
      toastLangSwitched: "Language switched to English",
      toastCardAdded: 'Added "{word}" to Anki deck with scene screenshot crop!',
      toastCardExists: '"{word}" is already in your Anki deck!',
      toastSavedWord: 'Saved "{word}" to Words library!',
      toastRemovedWord: 'Removed "{word}" from favorites.',
      toastGitCopied: "Git clone command copied to clipboard!",
      toastThemeLight: "Warm Stone Light theme enabled",
      toastThemeDark: "Matte Charcoal Dark theme enabled"
    },

    ru: {
      // Document Metadata
      metaTitle: "WordSnap — Мгновенный экранный OCR-переводчик и оффлайн-словари для Windows",
      metaDesc: "Мгновенный экранный OCR-переводчик, оффлайн-словарь Yomitan и карточки Anki для Windows 10/11. Переводите слова в 3D-играх, визуальных новеллах, манге и любых программах.",

      // Navigation
      navFeatures: "Возможности",
      navFreeze: "Режим заморозки",
      navAnki: "Синхронизация Anki",
      navShortcuts: "Горячие клавиши",
      navDownloads: "Скачать",
      navFaq: "Вопросы",

      // Hero Section
      heroVersion: "Для Windows 10 и 11",
      heroTitle: 'Мгновенный экранный OCR<br><span class="title-accent">& оффлайн-словари.</span>',
      heroDesc: "Переводите слова в 3D-играх, визуальных новеллах, манге, видео и любых программах. Режим заморозки экрана, оффлайн-движок Yomitan и карточки Anki в 1 клик.",
      heroBtnExe: "Скачать для Windows (.exe)",
      heroBtnZip: "Портативная (.zip)",
      heroBtnGh: "GitHub",
      heroPickerLabel: "Попробуйте поиск:",

      // Popup Simulator Card
      popupBtnAnkiTitle: "Добавить слово в Anki (AnkiConnect)",
      popupBtnFavTitle: "Сохранить слово в личный словарь",
      popupLblTranslator: 'Переводчик <span class="source-sparkle">✦</span>',
      popupLblDict: 'AI-словарь <span class="source-sparkle">✦</span>',
      popupAudioNormalTitle: "Озвучить слово (обычная скорость)",
      popupAudioSlowTitle: "Озвучить слово (медленно)",
      popupContextBtn: "Использованный контекст",
      popupOcrActive: "Windows Media OCR • 100% точность",
      popupAnkiHint: "<span>＋</span> AnkiConnect готов",

      // Ticker Ribbon
      tickerOcr: "Нативный Windows OCR",
      tickerFreeze: "Режим заморозки для игр",
      tickerYomitan: "100% оффлайн Yomitan (.zip)",
      tickerAi: "Двойной ИИ (Groq и Gemini)",
      tickerAnki: "Синхронизация с Anki в 1 клик",
      tickerCrop: "Авто-скриншоты сцен",

      // Bento Grid Features
      featBadge: "Архитектура",
      featTitle: "Создано для игр без пауз и глубокого погружения.",
      featDesc: "Больше не нужно отвлекаться от сюжета, жать Alt-Tab в браузер или вручную перепечатывать иероглифы.",

      featC1Title: "Нативный Windows OCR",
      featC1Desc: "Встроенный движок WinRT Media OCR обеспечивает распознавание за миллисекунды без облака и с минимальной нагрузкой на процессор.",

      featC2Title: "Режим заморозки экрана",
      featC2Desc: "Останавливает 3D-камеру, освобождает курсор мыши и при необходимости ставит игру на паузу, чтобы диалог не пропал.",

      featC3Title: "Оффлайн Yomitan (.zip)",
      featC3Desc: "Поддержка любых архивов Yomitan. Полное оффлайн-склонение грамматики, ударения (pitch accent) и частотные словари.",

      featC4Title: "Двойной ИИ-переводчик",
      featC4Desc: "Интеграция Groq (Llama 3) и Gemini 2.5 Flash для объяснения лора, уровней CEFR и точных контекстных переводов.",

      featC5Title: "Синхронизация с Anki в 1 клик",
      featC5Desc: "Прямая связь через AnkiConnect: автоматический захват скриншота сцены, контекстное предложение, TTS-озвучка и проверка дубликатов.",

      featC6Title: "Личный словарь и экспорт",
      featC6Desc: "Повторяйте сохранённые слова со снимками исходных сцен, воспроизводите озвучку и экспортируйте в CSV, JSON или Anki TSV.",

      // Freeze Mode Deep Dive
      freezeBadge: "Прорыв в гейминге",
      freezeTitle: "Больше не нужно погибать, читая диалоги.",
      freezeP1: "В динамичных 3D-играх (Elden Ring, Genshin Impact, Cyberpunk) мышь привязана к камере, а субтитры исчезают за пару секунд.",
      freezeP2: "WordSnap решает это с помощью <strong>Режима заморозки экрана</strong>:",
      freezeLi1: "<strong>Мгновенный стоп-кадр:</strong> Захватывает точный кадр в нативном разрешении без задержек.",
      freezeLi2: "<strong>Освобождение курсора:</strong> Отвязывает мышь от 3D-камеры для свободного наведения на текст.",
      freezeLi3: "<strong>Авто-пауза процесса:</strong> Опционально останавливает процесс игры, замораживая врагов и таймеры сцен.",
      freezeLi4: "<strong>Мгновенный возврат:</strong> Нажмите Esc для мгновенного снятия паузы и возвращения в игру.",
      freezeBtn: "Скачать WordSnap",

      // Anki Flashcard Sync Showcase
      ankiBadge: "Процесс обучения",
      ankiTitle: "Превращайте игровые сцены в карточки Anki.",
      ankiDesc: "Прямая интеграция через AnkiConnect. Больше не нужно копировать текст и делать скриншоты вручную.",
      ankiPreviewTitle: "Предпросмотр карточки Anki",
      ankiDeckChip: "Колода: Gaming Vocab",
      ankiCropTag: "Автоматический снимок сцены",
      ankiMeaning: "<strong>Значение:</strong> inform, notify, let know.",
      ankiAudioAttached: "[Аудио: Прикреплена TTS-озвучка]",

      ankiColTitle: "Автоматизируйте колоду погружения.",
      ankiColDesc: "С обычными инструментами создание карточки по игре занимает 2 минуты. С WordSnap — всего 0.5 секунды:",
      ankiLi1: "<strong>Извлечение предложения:</strong> WordSnap захватывает полную строчку диалога вокруг слова.",
      ankiLi2: "<strong>Авто-снимок экрана:</strong> Сохраняет визуальный контекст игры прямо в колоде Anki.",
      ankiLi3: "<strong>Генерация TTS:</strong> Озвучка слова автоматически прикрепляется к карточке.",
      ankiLi4: "<strong>Защита от дубликатов:</strong> Предотвращает захламление колоды повторно встреченными словами.",
      ankiDocBtn: "Документация на GitHub →",

      // Shortcuts Matrix
      scBadge: "Справка по клавишам",
      scTitle: "Удобные горячие клавиши для быстрого поиска.",
      scDesc: "Созданы, чтобы не отвлекать от игрового процесса. Полностью настраиваются в Настройках.",
      scThShortcut: "Клавиша",
      scThScope: "Область действия",
      scThAction: "Действие",

      scR1Scope: "Глобально (любая игра / окно)",
      scR1Action: "Распознать текст под курсором и открыть окно перевода",
      scR2Scope: "Оверлей / Окно перевода",
      scR2Action: "Закрыть перевод и мгновенно снять заморозку экрана",
      scR3Scope: "Вкладка «Слова»",
      scR3Action: "Озвучить выбранное слово (TTS-произношение)",
      scR4Scope: "Вкладка «Слова»",
      scR4Action: "Сфокусировать строку поиска для фильтрации слов",
      scR5Scope: "Вкладка «Слова»",
      scR5Action: "Добавить или убрать слово из избранного (★)",
      scR6Scope: "Вкладка «Слова»",
      scR6Action: "Удалить выбранное слово из истории",
      scR7Scope: "Вкладка «Слова»",
      scR7Action: "Переход к предыдущему и следующему слову",

      // Downloads Hub
      dlBadge: "Загрузка",
      dlTitle: "Скачать WordSnap для Windows 10 и 11.",
      dlDesc: "Бесплатно для личного использования. Выберите установщик или портативную версию.",
      dlRecommended: "Рекомендуется",
      dlC1Title: "Стандартный установщик",
      dlC1Meta: "Установочный файл для Windows (.exe)<br>Ярлыки в меню Пуск и на Рабочем столе, чистое удаление.",
      dlC1Btn: "Скачать установщик (.exe)",
      dlC2Title: "Портативная версия",
      dlC2Meta: "Автономный архив без установки (.zip)<br>Распакуйте и запускайте откуда угодно, даже с флешки.",
      dlC2Btn: "Скачать Portable (.zip)",

      dlSrcStrong: "Хотите запустить из исходного кода Python?",
      dlSrcSpan: "Требуется Python 3.11+ на Windows 10/11",
      dlSrcCopyTitle: "Скопировать команду git clone",

      // FAQ Section
      faqBadge: "Вопросы и ответы",
      faqTitle: "Часто задаваемые вопросы",
      faqDesc: "Всё, что нужно знать об установке и использовании WordSnap.",

      faqQ1: "Работает ли WordSnap в полноэкранных 3D-играх?",
      faqA1: "Да! Для игр в оконном режиме и в режиме окна без рамок (Borderless) WordSnap работает нативно. В играх, захватывающих курсор мыши, специальный <strong>Режим заморозки экрана</strong> приостанавливает кадр, освобождает мышь и позволяет легко навестись на любое слово, не прерывая игровую сессию.",

      faqQ2: "Нужен ли интернет для поиска в словарях?",
      faqA2: "Нет! Основной движок словарей Yomitan работает на 100% оффлайн. Раскрытие форм слов, определения, частотные списки и ударения вычисляются локально на вашем компьютере. Интернет требуется только если вы решите включить дополнительный ИИ-перевод через Groq или Google Gemini.",

      faqQ3: "Как работает интеграция с Anki?",
      faqA3: "WordSnap подключается к установленному на ПК приложению Anki через популярный плагин AnkiConnect (код: 2055492159). В один клик (или по горячей клавише) WordSnap вырезает кадр с экрана, извлекает строку диалога, генерирует аудио-озвучку и создает готовую карточку в выбранной колоде.",

      faqQ4: "Бесплатна ли программа и безопасна ли она?",
      faqA4: "Да! WordSnap распространяется по лицензии PolyForm Noncommercial License 1.0.0 и полностью бесплатен для личного использования. В нем нет рекламы, телеметрии или скрытых трекеров, а изображение вашего экрана никогда не отправляется на сторонние серверы. Все распознавание OCR выполняется локально средствами Windows.",

      faqQ5: "Какие языки и словари поддерживаются?",
      faqA5: "WordSnap поддерживает любые стандартные словари формата Yomitan (.zip). Программа включает готовые пресеты для японского (JMDict, KireiCake, Daijirin, JMnedict), английского и англо-русских словарей. Вы также можете импортировать любые сторонние словари сообщества в один клик.",

      // Footer
      footerDesc: "Мгновенный экранный OCR-переводчик и оффлайн-словарь Yomitan для комфортных игр и погружения в языковую среду на Windows.",
      footerHNav: "Навигация",
      footerHComm: "Сообщество",
      footerLnkFeatures: "Возможности",
      footerLnkFreeze: "Заморозка экрана",
      footerLnkAnki: "Синхронизация Anki",
      footerLnkShortcuts: "Горячие клавиши",
      footerLnkDownloads: "Скачать",
      footerLnkGh: "Репозиторий GitHub",
      footerLnkReleases: "Релизы и список изменений",
      footerLnkIssues: "Сообщить об ошибке",
      footerLnkLicense: "Лицензия PolyForm",
      footerCopy: '© 2026 WordSnap. Автор — <a href="https://github.com/Wefdzen" target="_blank" rel="noopener noreferrer" style="color: var(--text-primary); text-decoration: none;">Wefdzen</a>. Бесплатно для личного использования.',
      footerOs: "Windows 10 & 11 • 64-bit",
      footerSupport: "Поддержать автора ❤️",

      // Interactive UI notifications
      toastLangSwitched: "Язык переключён на Русский",
      toastCardAdded: 'Карточка "{word}" добавлена в колоду Anki со скриншотом сцены!',
      toastCardExists: 'Слово "{word}" уже есть в вашей колоде Anki!',
      toastSavedWord: 'Слово "{word}" сохранено в личный словарь!',
      toastRemovedWord: 'Слово "{word}" удалено из избранного.',
      toastGitCopied: "Команда git clone скопирована в буфер!",
      toastThemeLight: "Включена светлая тема (Теплый камень)",
      toastThemeDark: "Включена матовая тёмная тема"
    }
  };

  let currentLang = 'en';

  function getTranslation(key, lang = currentLang) {
    const dict = TRANSLATIONS[lang] || TRANSLATIONS.en;
    return dict[key] || TRANSLATIONS.en[key] || '';
  }

  function applyLanguage(lang, notify = false) {
    if (lang !== 'en' && lang !== 'ru') lang = 'en';
    currentLang = lang;

    // Persist & update HTML lang attribute
    localStorage.setItem('wordsnap-lang', lang);
    document.documentElement.setAttribute('lang', lang);
    document.documentElement.setAttribute('data-lang', lang);

    // Update document title and description
    document.title = getTranslation('metaTitle', lang);
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) metaDesc.setAttribute('content', getTranslation('metaDesc', lang));

    // Update textContent elements: [data-i18n]
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      const val = getTranslation(key, lang);
      if (val) el.textContent = val;
    });

    // Update innerHTML elements: [data-i18n-html]
    document.querySelectorAll('[data-i18n-html]').forEach((el) => {
      const key = el.getAttribute('data-i18n-html');
      const val = getTranslation(key, lang);
      if (val) el.innerHTML = val;
    });

    // Update title attributes: [data-i18n-title]
    document.querySelectorAll('[data-i18n-title]').forEach((el) => {
      const key = el.getAttribute('data-i18n-title');
      const val = getTranslation(key, lang);
      if (val) el.setAttribute('title', val);
    });

    // Update trigger label and active states in dropdown
    const currentLabel = document.getElementById('currentLangLabel');
    if (currentLabel) {
      currentLabel.textContent = lang === 'ru' ? 'RU' : 'ENG';
    }

    const langMenuItems = document.querySelectorAll('.lang-menu-item');
    langMenuItems.forEach((item) => {
      const itemLang = item.getAttribute('data-lang');
      if (itemLang === lang) {
        item.classList.add('active');
        item.setAttribute('aria-selected', 'true');
      } else {
        item.classList.remove('active');
        item.setAttribute('aria-selected', 'false');
      }
    });

    // Notify user via toast if requested
    if (notify && window.WordSnapToast) {
      window.WordSnapToast(getTranslation('toastLangSwitched', lang));
    }
  }

  function initI18n() {
    // Default to 'en' (English) as requested, or load user's saved choice
    const saved = localStorage.getItem('wordsnap-lang');
    const initialLang = (saved === 'ru' || saved === 'en') ? saved : 'en';

    applyLanguage(initialLang, false);

    const dropdown = document.getElementById('langDropdown');
    const trigger = document.getElementById('langDropdownTrigger');

    if (trigger && dropdown) {
      trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = dropdown.classList.toggle('open');
        trigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      });

      // Close dropdown when clicking anywhere outside
      document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target)) {
          dropdown.classList.remove('open');
          trigger.setAttribute('aria-expanded', 'false');
        }
      });

      // Close dropdown on Escape key
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && dropdown.classList.contains('open')) {
          dropdown.classList.remove('open');
          trigger.setAttribute('aria-expanded', 'false');
          trigger.focus();
        }
      });
    }

    // Bind click events on dropdown menu items
    document.querySelectorAll('.lang-menu-item').forEach((item) => {
      item.addEventListener('click', (e) => {
        const targetLang = e.currentTarget.getAttribute('data-lang');
        if (targetLang && targetLang !== currentLang) {
          applyLanguage(targetLang, true);
        }
        if (dropdown) {
          dropdown.classList.remove('open');
          if (trigger) trigger.setAttribute('aria-expanded', 'false');
        }
      });
    });
  }

  // Expose to window for app.js interaction
  window.WordSnapI18n = {
    t: getTranslation,
    setLanguage: applyLanguage,
    getLanguage: () => currentLang,
    init: initI18n
  };

  // Run on DOMContentLoaded or immediately if already loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initI18n);
  } else {
    initI18n();
  }
})();
