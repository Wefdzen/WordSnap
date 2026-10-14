/**
 * WordSnap Web Landing Page Script
 * - Live GitHub Stars Fetcher
 * - Dual Theme Switcher (Charcoal Dark / Warm Stone Light)
 * - 1:1 WordSnap Desktop Popup Simulator with Anki Plus ＋ & Bookmark 🔖
 * - Dynamic Translator Section with Olive Highlight (#7f801e)
 * - Dual-Speed Audio Pronunciation (Normal 🔊 / Slow 🔉) via Web Speech API
 * - Collapsible Context Sentence Box
 * - FAQ Accordion & Clipboard Utilities
 */

document.addEventListener('DOMContentLoaded', () => {
  // -------------------------------------------------------------------------
  // 1. Dual Theme Switcher (Charcoal Dark / Warm Stone Light)
  // -------------------------------------------------------------------------
  const themeToggleSwitch = document.getElementById('themeToggleSwitch');
  
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('wordsnap-theme', theme);
    
    if (themeToggleSwitch) {
      themeToggleSwitch.setAttribute('aria-checked', theme === 'dark' ? 'true' : 'false');
      themeToggleSwitch.title = theme === 'dark' 
        ? 'Switch to Warm Stone Light theme' 
        : 'Switch to Matte Charcoal Dark theme';
    }
  }

  const initialTheme = document.documentElement.getAttribute('data-theme') || 'dark';
  applyTheme(initialTheme);

  if (themeToggleSwitch) {
    themeToggleSwitch.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      const msg = (window.WordSnapI18n && window.WordSnapI18n.t)
        ? window.WordSnapI18n.t(next === 'light' ? 'toastThemeLight' : 'toastThemeDark')
        : (next === 'light' ? 'Warm Stone Light theme enabled' : 'Matte Charcoal Dark theme enabled');
      showToast(msg);
    });
  }

  // -------------------------------------------------------------------------
  // 3. WordSnap Authentic Dictionary Database (Exact from Screenshots & App)
  // -------------------------------------------------------------------------
  const DICT_DATABASE = {
    know: {
      word: 'know',
      reading: '/nəʊ/',
      cefr: 'A1',
      cefrColor: 'var(--cefr-a1)',
      pos: 'Глагол, непереходный, инфинитив',
      definition: 'Сообщать кому-либо информацию или уведомлять о чём-либо. В данном контексте используется в устойчивом выражении \'let me know\', означающем \'сообщите мне\' или \'дайте мне знать\'.',
      targetFlag: '🇷🇺',
      targetText: 'знать, сообщать, давать знать',
      synonyms: 'Synonyms: inform, notify, tell',
      dimParenthesis: '(Если тебе понадобится помощь, просто дай мне знать.)',
      translatorLine: 'Если тебе нужна помощь, просто дай мне <span class="context-hilite">знать</span>.',
      context: 'If you need any help, just let me <span class="context-hilite">know</span>.',
      lang: 'en-US'
    },
    Anki: {
      word: 'Anki',
      reading: '/ ˈæŋki/',
      cefr: 'B1',
      cefrColor: 'var(--cefr-b1)',
      pos: 'Существительное, Собственное имя, Программное обеспечение',
      definition: 'Популярное программное обеспечение для создания и использования карточек для запоминания (spaced repetition). В данном контексте упоминается как формат или инструмент, в который можно экспортировать данные.',
      targetFlag: '🇷🇺',
      targetText: 'Anki (программа для запоминания)',
      synonyms: 'Synonyms: flashcard app, spaced repetition software, SRS',
      dimParenthesis: '(Сохраняйте новые слова прямо в Anki.)',
      translatorLine: 'Экспортируйте словарный запас напрямую в <span class="context-hilite">Anki</span>.',
      context: 'Export saved vocabulary directly to <span class="context-hilite">Anki</span> study decks.',
      lang: 'en-US'
    },
    Artifact: {
      word: 'Artifact',
      reading: '/ ˈɑːtɪfækt/',
      cefr: 'B2',
      cefrColor: 'var(--cefr-b2)',
      pos: 'Существительное',
      definition: 'Предмет или реликвия, созданная человеком в прошлом, часто несущая археологическую или магическую ценность в фэнтези-играх.',
      targetFlag: '🇷🇺',
      targetText: 'Артефакт (реликвия)',
      synonyms: 'Synonyms: relic, heirloom, ancient treasure',
      dimParenthesis: '(Древний артефакт сиял таинственным светом.)',
      translatorLine: 'Древний <span class="context-hilite">артефакт</span> излучал небесную энергию.',
      context: 'The ancient <span class="context-hilite">artifact</span> radiated intense celestial magic.',
      lang: 'en-US'
    },
    Immersion: {
      word: 'Immersion',
      reading: '/ ɪˈmɜːʃn/',
      cefr: 'C1',
      cefrColor: 'var(--cefr-c1)',
      pos: 'Существительное',
      definition: 'Глубокое погружение в языковую среду через прохождение оригинальных видеоигр, чтение визуальных новелл и манги без переключения контекста.',
      targetFlag: '🇷🇺',
      targetText: 'Языковое погружение (иммерсия)',
      synonyms: 'Synonyms: language immersion, deep dive, absorption',
      dimParenthesis: '(Игры на иностранном языке дают лучший результат.)',
      translatorLine: 'WordSnap превращает геймплей в эффективную <span class="context-hilite">иммерсию</span>.',
      context: 'WordSnap turns your daily gameplay into an effortless <span class="context-hilite">immersion</span> session.',
      lang: 'en-US'
    },
    '冒険': {
      word: '冒険',
      reading: '/ ぼうけん (bouken)/',
      cefr: 'N3',
      cefrColor: 'var(--cefr-b1)',
      pos: 'Существительное, Сурю-глагол',
      definition: 'Приключение, рискованное предприятие или поход героя в неизведанные земли в японских RPG.',
      targetFlag: '🇷🇺',
      targetText: 'Приключение, квест',
      synonyms: 'Synonyms: quest, venture, expedition',
      dimParenthesis: '(В этом мире начинается великое приключение.)',
      translatorLine: 'В этом бескрайнем мире начинается новое <span class="context-hilite">приключение</span>.',
      context: '広大なファンタジー世界で新たな<span class="context-hilite">冒険</span>が始まる。',
      lang: 'ja-JP'
    }
  };

  // -------------------------------------------------------------------------
  // 4. Popup Card Controller
  // -------------------------------------------------------------------------
  const popupWordText = document.getElementById('popupWordText');
  const popupTranscription = document.getElementById('popupTranscription');
  const popupCefrBadge = document.getElementById('popupCefrBadge');
  const popupPosText = document.getElementById('popupPosText');
  const popupDefinitionText = document.getElementById('popupDefinitionText');
  const popupTargetTransText = document.getElementById('popupTargetTransText');
  const popupSynonymsText = document.getElementById('popupSynonymsText');
  const translatorDimSentence = document.getElementById('translatorDimSentence');
  const translatorResultLine = document.getElementById('translatorResultLine');
  const contextInnerContent = document.getElementById('contextInnerContent');
  const popupContextBox = document.getElementById('popupContextBox');
  const btnToggleContext = document.getElementById('btnToggleContext');
  const btnPopupAudio1 = document.getElementById('btnPopupAudio1');
  const btnPopupAudio2 = document.getElementById('btnPopupAudio2');
  const popupAnkiPlusBtn = document.getElementById('popupAnkiPlusBtn');
  const popupBookmarkBtn = document.getElementById('popupBookmarkBtn');
  const toastNotice = document.getElementById('toastNotice');
  const toastMessage = document.getElementById('toastMessage');
  const wordChips = document.querySelectorAll('.word-chip');

  let currentEntry = DICT_DATABASE['know'];
  let isBookmarked = false;
  let isAnkiAdded = false;

  function renderCard(data) {
    currentEntry = data;
    popupWordText.textContent = data.word;
    popupTranscription.textContent = data.reading;
    popupCefrBadge.textContent = data.cefr;
    popupCefrBadge.style.backgroundColor = data.cefrColor || '#8a8f98';
    popupPosText.textContent = data.pos;
    popupDefinitionText.textContent = data.definition;
    popupTargetTransText.textContent = data.targetText;
    popupSynonymsText.textContent = data.synonyms;
    translatorDimSentence.textContent = data.dimParenthesis;
    translatorResultLine.innerHTML = data.translatorLine;
    contextInnerContent.innerHTML = data.context;

    // Reset Anki Plus button
    isAnkiAdded = false;
    if (popupAnkiPlusBtn) {
      popupAnkiPlusBtn.textContent = '＋';
      popupAnkiPlusBtn.classList.remove('added');
      popupAnkiPlusBtn.title = 'Добавить слово в Anki (AnkiConnect)';
    }

    // Reset Bookmark
    isBookmarked = false;
    if (popupBookmarkBtn) {
      popupBookmarkBtn.textContent = '🔖';
      popupBookmarkBtn.title = 'Сохранить слово в личный словарь';
    }
  }

  // Word Chip Switcher
  wordChips.forEach(chip => {
    chip.addEventListener('click', () => {
      wordChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');

      const key = chip.dataset.word;
      if (DICT_DATABASE[key]) {
        renderCard(DICT_DATABASE[key]);
      }
    });
  });

  // -------------------------------------------------------------------------
  // 5. Dual Audio Pronunciation (Normal 🔊 & Slow 🔉)
  // -------------------------------------------------------------------------
  function speakWord(speed = 1.0) {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const textToSpeak = currentEntry.word.replace(/\(.*\)/, '').trim();
      const utterance = new SpeechSynthesisUtterance(textToSpeak);
      utterance.lang = currentEntry.lang || 'en-US';
      utterance.rate = speed;
      window.speechSynthesis.speak(utterance);
    }
  }

  if (btnPopupAudio1) {
    btnPopupAudio1.addEventListener('click', () => speakWord(1.0));
  }
  if (btnPopupAudio2) {
    btnPopupAudio2.addEventListener('click', () => speakWord(0.7));
  }

  // -------------------------------------------------------------------------
  // 6. Anki Plus ＋ Topbar Action (From popup.py set_anki_state)
  // -------------------------------------------------------------------------
  if (popupAnkiPlusBtn) {
    popupAnkiPlusBtn.addEventListener('click', () => {
      if (isAnkiAdded) {
        const tmpl = (window.WordSnapI18n && window.WordSnapI18n.t)
          ? window.WordSnapI18n.t('toastCardExists')
          : '"{word}" is already in your Anki deck!';
        showToast(tmpl.replace('{word}', currentEntry.word));
        return;
      }

      popupAnkiPlusBtn.textContent = '⏳';
      setTimeout(() => {
        isAnkiAdded = true;
        popupAnkiPlusBtn.textContent = '✓';
        popupAnkiPlusBtn.classList.add('added');
        popupAnkiPlusBtn.title = '✓';
        const tmpl = (window.WordSnapI18n && window.WordSnapI18n.t)
          ? window.WordSnapI18n.t('toastCardAdded')
          : 'Added "{word}" to Anki deck with scene screenshot crop!';
        showToast(tmpl.replace('{word}', currentEntry.word));
      }, 250);
    });
  }

  // -------------------------------------------------------------------------
  // 7. Bookmark 🔖 Topbar Action
  // -------------------------------------------------------------------------
  if (popupBookmarkBtn) {
    popupBookmarkBtn.addEventListener('click', () => {
      isBookmarked = !isBookmarked;
      popupBookmarkBtn.textContent = isBookmarked ? '✅' : '🔖';
      const key = isBookmarked ? 'toastSavedWord' : 'toastRemovedWord';
      const tmpl = (window.WordSnapI18n && window.WordSnapI18n.t)
        ? window.WordSnapI18n.t(key)
        : (isBookmarked ? 'Saved "{word}" to Words library!' : 'Removed "{word}" from favorites.');
      showToast(tmpl.replace('{word}', currentEntry.word));
    });
  }

  // -------------------------------------------------------------------------
  // 8. Collapsible Context Box (Context used ⌄)
  // -------------------------------------------------------------------------
  if (btnToggleContext && popupContextBox) {
    btnToggleContext.addEventListener('click', () => {
      popupContextBox.classList.toggle('open');
    });
  }

  // -------------------------------------------------------------------------
  // 9. Toast Notification Helper
  // -------------------------------------------------------------------------
  let toastTimer = null;
  function showToast(msg) {
    if (!toastNotice || !toastMessage) return;
    toastMessage.textContent = msg;
    toastNotice.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastNotice.classList.remove('show');
    }, 3200);
  }
  window.WordSnapToast = showToast;

  // -------------------------------------------------------------------------
  // 10. Global Shortcut Alt+Q (cycles word presets)
  // -------------------------------------------------------------------------
  window.addEventListener('keydown', (e) => {
    if (e.altKey && (e.key === 'q' || e.key === 'Q' || e.code === 'KeyQ')) {
      e.preventDefault();
      const keys = Object.keys(DICT_DATABASE);
      const currIdx = keys.indexOf(currentEntry.word);
      const nextKey = keys[(currIdx + 1) % keys.length];

      wordChips.forEach(chip => {
        if (chip.dataset.word === nextKey) chip.classList.add('active');
        else chip.classList.remove('active');
      });

      renderCard(DICT_DATABASE[nextKey]);
      showToast(`Alt+Q lookup: "${nextKey}"`);
    }
  });

  // -------------------------------------------------------------------------
  // 11. FAQ Accordion
  // -------------------------------------------------------------------------
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const questionBtn = item.querySelector('.faq-question');
    if (questionBtn) {
      questionBtn.addEventListener('click', () => {
        const isActive = item.classList.contains('active');
        faqItems.forEach(i => i.classList.remove('active'));
        if (!isActive) item.classList.add('active');
      });
    }
  });

  // -------------------------------------------------------------------------
  // 12. Copy to Clipboard (Git command)
  // -------------------------------------------------------------------------
  const copyBtn = document.getElementById('copyGitBtn');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const codeText = "git clone https://github.com/Wefdzen/WordSnap.git";
      navigator.clipboard.writeText(codeText).then(() => {
        copyBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#60cdff" stroke-width="2.5">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        `;
        showToast("Git clone command copied to clipboard!");
        setTimeout(() => {
          copyBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
          `;
        }, 2200);
      });
    });
  }

  // -------------------------------------------------------------------------
  // 13. Mobile Nav Toggle
  // -------------------------------------------------------------------------
  const mobileToggle = document.getElementById('mobileToggle');
  const navMenu = document.querySelector('.nav-menu');
  if (mobileToggle && navMenu) {
    mobileToggle.addEventListener('click', () => {
      const isVisible = navMenu.style.display === 'flex';
      navMenu.style.display = isVisible ? 'none' : 'flex';
      if (!isVisible) {
        navMenu.style.flexDirection = 'column';
        navMenu.style.position = 'absolute';
        navMenu.style.top = '64px';
        navMenu.style.left = '0';
        navMenu.style.width = '100%';
        navMenu.style.background = 'var(--bg-surface)';
        navMenu.style.padding = '18px';
        navMenu.style.borderBottom = '1px solid var(--border-subtle)';
      }
    });
  }
});
