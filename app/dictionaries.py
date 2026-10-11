"""Менеджер офлайн-словарей в формате Yomitan (.zip архивы).

Поддерживает:
- Импорт словарей Yomitan (index.json + term_bank_*.json)
- Хранение и сверхбыстрый поиск в SQLite (data/dictionaries/dictionaries.db)
- Рендеринг Yomitan structured-content в HTML (для попапа и карточек Anki)
- Экспорт словарных статей в Anki ({glossary}, {single-glossary-...}, {dictionary})
- Управление словарями: включение/выключение, удаление, просмотр инфо
"""
import html
import json
import os
import re
import sqlite3
import threading
import time
import zipfile

from .config import data_dir

_DB_LOCK = threading.Lock()

def dicts_dir() -> str:
    d = os.path.join(data_dir(), "dictionaries")
    os.makedirs(d, exist_ok=True)
    return d

def db_path() -> str:
    return os.path.join(dicts_dir(), "dictionaries.db")


def render_yomitan_node(node) -> str:
    """Рекурсивный рендеринг узлов structured-content из Yomitan в чистый HTML."""
    if node is None:
        return ""
    if isinstance(node, str):
        return html.escape(node)
    if isinstance(node, (int, float)):
        return str(node)
    if isinstance(node, list):
        # Если список состоит из списков/строк без структурированных HTML-тегов (например, [["satisfy", ["gerund"]]])
        if node and not any(isinstance(x, dict) and ("tag" in x or x.get("type") == "structured-content") for x in node):
            parts = []
            for item in node:
                if isinstance(item, list):
                    if len(item) >= 2 and isinstance(item[1], list):
                        tag_str = ", ".join(str(t) for t in item[1] if t)
                        parts.append(f"{html.escape(str(item[0]))} ({html.escape(tag_str)})" if tag_str else html.escape(str(item[0])))
                    elif len(item) >= 2 and isinstance(item[1], str):
                        parts.append(f"{html.escape(str(item[0]))} ({html.escape(str(item[1]))})")
                    else:
                        parts.append(" ".join(html.escape(str(sub)) for sub in item if sub))
                elif isinstance(item, str):
                    parts.append(html.escape(item))
                else:
                    parts.append(str(item))
            return "; ".join(p for p in parts if p)
        return "".join(render_yomitan_node(x) for x in node)
    if isinstance(node, dict):
        if node.get("type") == "structured-content":
            return render_yomitan_node(node.get("content", []))

        tag = node.get("tag", "div")
        content = render_yomitan_node(node.get("content", ""))
        data = node.get("data", {})
        href = node.get("href", "")

        if tag == "details":
            return f"<details style='margin:3px 0;'>{content}</details>"
        elif tag == "summary":
            return f"<summary style='cursor:pointer; color:#60cdff; font-weight:600;'>{content}</summary>"
        elif tag == "a":
            safe_href = html.escape(href)
            return f"<a href='{safe_href}' style='color:#60cdff; text-decoration:none;'>{content}</a>"
        elif tag == "ol":
            return f"<ol style='margin:4px 0 4px 20px; padding:0;'>{content}</ol>"
        elif tag == "ul":
            return f"<ul style='margin:4px 0 4px 20px; padding:0;'>{content}</ul>"
        elif tag == "li":
            return f"<li style='margin-bottom:2px;'>{content}</li>"
        elif tag == "span":
            is_bold = data.get("content") == "bold-text" or data.get("content") == "bold"
            bold_style = "font-weight:600;" if is_bold else ""
            return f"<span style='{bold_style}'>{content}</span>"
        elif tag in ("b", "strong"):
            return f"<b>{content}</b>"
        elif tag in ("i", "em"):
            return f"<i>{content}</i>"
        elif tag == "ruby":
            return f"<ruby>{content}</ruby>"
        elif tag in ("rt", "rp"):
            return f"<{tag}>{content}</{tag}>"
        else:
            style = ""
            if data.get("content") == "backlink":
                style = "text-align:right; color:#888888; font-size:11px; margin-top:4px;"
            elif data.get("content") == "preamble":
                style = "margin-bottom:4px;"
            return f"<div style='{style}'>{content}</div>" if style else f"<div>{content}</div>"

    return ""


def extract_text_node(node) -> str:
    """Извлекает текст с сохранением тегов жирности/курсива."""
    if node is None:
        return ""
    if isinstance(node, str):
        return html.escape(node)
    if isinstance(node, (int, float)):
        return str(node)
    if isinstance(node, list):
        return "".join(extract_text_node(x) for x in node)
    if isinstance(node, dict):
        if node.get("tag") in ("b", "strong") or node.get("data", {}).get("content") in ("bold", "bold-text"):
            return f"<b>{extract_text_node(node.get('content', ''))}</b>"
        if node.get("tag") in ("i", "em"):
            return f"<i>{extract_text_node(node.get('content', ''))}</i>"
        return extract_text_node(node.get("content", ""))
    return ""


def parse_yomitan_sense(raw_sc) -> dict:
    """Разбирает structured-content узел на этимологию, определения с примерами и ссылки."""
    etymologies = []
    glosses = []
    backlinks = []

    content = raw_sc.get("content", []) if isinstance(raw_sc, dict) else (raw_sc if isinstance(raw_sc, list) else [])
    for block in content:
        if not isinstance(block, dict):
            continue
        tag = block.get("tag")
        data_c = block.get("data", {}).get("content", "")

        # 1. Этимология
        if "Etymology" in str(block) or data_c == "preamble" or (tag == "div" and data_c is None):
            def find_details(n):
                if isinstance(n, dict):
                    if n.get("tag") == "details":
                        summ = "Этимология"
                        body = ""
                        for c in n.get("content", []):
                            if isinstance(c, dict) and c.get("tag") == "summary":
                                summ = extract_text_node(c.get("content", "Этимология"))
                            else:
                                body += extract_text_node(c)
                        if body.strip():
                            etymologies.append({"summary": summ.strip(), "body": body.strip()})
                    else:
                        find_details(n.get("content", []))
                elif isinstance(n, list):
                    for x in n:
                        find_details(x)
            find_details(block)

        # 2. Определения (glosses)
        if tag == "ol" or data_c == "glosses":
            for li in block.get("content", []):
                if not isinstance(li, dict):
                    continue
                li_content = li.get("content", [])
                if isinstance(li_content, list) and len(li_content) > 0 and isinstance(li_content[0], dict) and li_content[0].get("tag") == "div":
                    div_items = li_content[0].get("content", [])
                else:
                    div_items = li_content if isinstance(li_content, list) else [li_content]

                gloss_text = ""
                examples = []
                for item in div_items:
                    if isinstance(item, dict) and item.get("tag") == "details":
                        ex_summary = "Примеры"
                        ex_a = ""
                        ex_b = ""
                        for ec in item.get("content", []):
                            if isinstance(ec, dict) and ec.get("tag") == "summary":
                                ex_summary = extract_text_node(ec.get("content", ""))
                            else:
                                def find_sentences(sn):
                                    nonlocal ex_a, ex_b
                                    if isinstance(sn, dict):
                                        c_type = sn.get("data", {}).get("content")
                                        if c_type == "example-sentence-a":
                                            ex_a = extract_text_node(sn.get("content", ""))
                                        elif c_type == "example-sentence-b":
                                            ex_b = extract_text_node(sn.get("content", ""))
                                        else:
                                            find_sentences(sn.get("content", []))
                                    elif isinstance(sn, list):
                                        for x in sn:
                                            find_sentences(x)
                                find_sentences(ec)
                        if ex_a or ex_b:
                            examples.append({"summary": ex_summary, "a": ex_a, "b": ex_b})
                    else:
                        gloss_text += extract_text_node(item)

                if gloss_text.strip():
                    glosses.append({"text": gloss_text.strip(), "examples": examples})

        # 3. Ссылки (Wiktionary / Kaikki)
        if data_c == "backlink":
            def find_links(bn):
                if isinstance(bn, dict):
                    if bn.get("tag") == "a":
                        backlinks.append({
                            "title": extract_text_node(bn.get("content", "")),
                            "href": bn.get("href", "")
                        })
                    else:
                        find_links(bn.get("content", []))
                elif isinstance(bn, list):
                    for x in bn:
                        find_links(x)
            find_links(block)

    return {"etymologies": etymologies, "glosses": glosses, "backlinks": backlinks}


IRREGULAR_ENGLISH = {
    "better": ["good", "well"],
    "best": ["good", "well"],
    "worse": ["bad", "ill"],
    "worst": ["bad", "ill"],
    "more": ["much", "many"],
    "most": ["much", "many"],
    "less": ["little"],
    "least": ["little"],
    "further": ["far"],
    "furthest": ["far"],
    "farther": ["far"],
    "farthest": ["far"],
    "elder": ["old"],
    "eldest": ["old"],
    "men": ["man"],
    "women": ["woman"],
    "children": ["child"],
    "teeth": ["tooth"],
    "feet": ["foot"],
    "mice": ["mouse"],
    "geese": ["goose"],
    "oxen": ["ox"],
    "people": ["person"],
    "was": ["be"],
    "were": ["be"],
    "been": ["be"],
    "being": ["be"],
    "am": ["be"],
    "is": ["be"],
    "are": ["be"],
    "has": ["have"],
    "had": ["have"],
    "having": ["have"],
    "does": ["do"],
    "did": ["do"],
    "done": ["do"],
    "doing": ["do"],
    "said": ["say"],
    "says": ["say"],
    "made": ["make"],
    "makes": ["make"],
    "went": ["go"],
    "gone": ["go"],
    "goes": ["go"],
    "took": ["take"],
    "taken": ["take"],
    "takes": ["take"],
    "came": ["come"],
    "comes": ["come"],
    "saw": ["see"],
    "seen": ["see"],
    "sees": ["see"],
    "knew": ["know"],
    "known": ["know"],
    "knows": ["know"],
    "got": ["get"],
    "gotten": ["get"],
    "gets": ["get"],
    "gave": ["give"],
    "given": ["give"],
    "gives": ["give"],
    "found": ["find"],
    "finds": ["find"],
    "thought": ["think"],
    "thinks": ["think"],
    "told": ["tell"],
    "tells": ["tell"],
    "became": ["become"],
    "becomes": ["become"],
    "left": ["leave"],
    "leaves": ["leave", "leaf"],
    "felt": ["feel"],
    "feels": ["feel"],
    "brought": ["bring"],
    "brings": ["bring"],
    "began": ["begin"],
    "begun": ["begin"],
    "begins": ["begin"],
    "kept": ["keep"],
    "keeps": ["keep"],
    "held": ["hold"],
    "holds": ["hold"],
    "wrote": ["write"],
    "written": ["write"],
    "writes": ["write"],
    "stood": ["stand"],
    "stands": ["stand"],
    "heard": ["hear"],
    "hears": ["hear"],
    "meant": ["mean"],
    "means": ["mean"],
    "met": ["meet"],
    "meets": ["meet"],
    "ran": ["run"],
    "runs": ["run"],
    "paid": ["pay"],
    "pays": ["pay"],
    "sat": ["sit"],
    "sits": ["sit"],
    "spoke": ["speak"],
    "spoken": ["speak"],
    "speaks": ["speak"],
    "lay": ["lie"],
    "lain": ["lie"],
    "led": ["lead"],
    "leads": ["lead"],
    "grew": ["grow"],
    "grown": ["grow"],
    "grows": ["grow"],
    "lost": ["lose"],
    "loses": ["lose"],
    "fell": ["fall"],
    "fallen": ["fall"],
    "falls": ["fall"],
    "sent": ["send"],
    "sends": ["send"],
    "built": ["build"],
    "builds": ["build"],
    "understood": ["understand"],
    "understands": ["understand"],
    "drew": ["draw"],
    "drawn": ["draw"],
    "draws": ["draw"],
    "broke": ["break"],
    "broken": ["break"],
    "breaks": ["break"],
    "spent": ["spend"],
    "spends": ["spend"],
    "rose": ["rise"],
    "risen": ["rise"],
    "rises": ["rise"],
    "drove": ["drive"],
    "driven": ["drive"],
    "drives": ["drive"],
    "bought": ["buy"],
    "buys": ["buy"],
    "wore": ["wear"],
    "worn": ["wear"],
    "wears": ["wear"],
    "chose": ["choose"],
    "chosen": ["choose"],
    "chooses": ["choose"],
    "threw": ["throw"],
    "thrown": ["throw"],
    "throws": ["throw"],
    "caught": ["catch"],
    "catches": ["catch"],
    "won": ["win"],
    "wins": ["win"],
    "forgot": ["forget"],
    "forgotten": ["forget"],
    "forgets": ["forget"],
    "sold": ["sell"],
    "sells": ["sell"],
    "fought": ["fight"],
    "fights": ["fight"],
    "flew": ["fly"],
    "flown": ["fly"],
    "flies": ["fly"],
    "ate": ["eat"],
    "eaten": ["eat"],
    "eats": ["eat"],
    "sang": ["sing"],
    "sung": ["sing"],
    "sings": ["sing"],
    "swam": ["swim"],
    "swum": ["swim"],
    "swims": ["swim"],
    "drank": ["drink"],
    "drunk": ["drink"],
    "drinks": ["drink"],
    "slept": ["sleep"],
    "sleeps": ["sleep"],
    "rode": ["ride"],
    "ridden": ["ride"],
    "rides": ["ride"],
    "hid": ["hide"],
    "hidden": ["hide"],
    "hides": ["hide"],
    "shook": ["shake"],
    "shaken": ["shake"],
    "shakes": ["shake"],
    "bit": ["bite"],
    "bitten": ["bite"],
    "bites": ["bite"],
    "blew": ["blow"],
    "blown": ["blow"],
    "blows": ["blow"],
    "froze": ["freeze"],
    "frozen": ["freeze"],
    "freezes": ["freeze"],
    "woke": ["wake"],
    "woken": ["wake"],
    "wakes": ["wake"],
}

TAG_MAP = {
    "gerund": "ing",
    "present participle": "ing",
    "participle": "ed",
    "past participle": "ed",
    "past tense": "ed",
    "past": "ed",
    "plural": "s",
    "third-person singular": "s",
    "comparative": "er",
    "superlative": "est",
}

def normalize_inflection_tag(tag: str) -> str:
    if not tag:
        return ""
    t_clean = tag.strip().lower()
    return TAG_MAP.get(t_clean, t_clean)

def parse_non_lemma_references(gloss_data) -> list[tuple[str, str]]:
    """Извлекает [(target_lemma, tag), ...] из записи non-lemma Yomitan.
    Например, [["satisfy", ["gerund"]]] -> [("satisfy", "ing")]."""
    refs = []
    if isinstance(gloss_data, str):
        try:
            gloss_data = json.loads(gloss_data)
        except Exception:
            return []
    if isinstance(gloss_data, list):
        for item in gloss_data:
            if isinstance(item, list) and len(item) >= 1:
                target = str(item[0]).strip()
                tag = ""
                if len(item) > 1:
                    if isinstance(item[1], list) and item[1]:
                        tag = str(item[1][0]).strip()
                    elif isinstance(item[1], str):
                        tag = item[1].strip()
                if target:
                    refs.append((target, normalize_inflection_tag(tag)))
    return refs

def deinflect_english_with_tags(w: str) -> list[tuple[str, str]]:
    """Генерация базовых словарных форм (лемм) вместе с грамматическими тегами инфлекции (ing, ed, s, er...).
    По аналогии с алгоритмом деинфлекции в Yomitan:
    satisfying -> [('satisfie', 'ing'), ('satisfy', 'ing')], greater -> [('great', 'er')]."""
    w = w.strip().lower()
    if not w or len(w) < 3:
        return []

    candidates: list[tuple[str, str]] = []
    def add(c: str, tag: str):
        if c and len(c) >= 2 and c != w and not any(x[0] == c for x in candidates):
            candidates.append((c, tag))

    # 1. Нерегулярные формы
    if w in IRREGULAR_ENGLISH:
        for c in IRREGULAR_ENGLISH[w]:
            add(c, "irregular")

    # 2. Степени сравнения (-est, -er)
    if w.endswith("iest") and len(w) > 4:
        add(w[:-4] + "y", "est")
    elif w.endswith("ier") and len(w) > 3:
        add(w[:-3] + "y", "er")

    if w.endswith("est") and len(w) > 3:
        stem = w[:-3]
        if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in "aeiouy":
            add(stem[:-1], "est") # biggest -> big
        add(stem, "est")          # greatest -> great
        add(stem + "e", "est")    # finest -> fine

    if w.endswith("er") and len(w) > 3:
        stem = w[:-2]
        if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in "aeiouy":
            add(stem[:-1], "er") # bigger -> big
        add(stem, "er")          # greater -> great
        add(stem + "e", "er")    # nicer -> nice

    # 3. Причастия и прошедшее время (-ed)
    if w.endswith("ied") and len(w) > 3:
        add(w[:-3] + "y", "ed")
        add(w[:-1], "ed")
    elif w.endswith("ed") and len(w) > 3:
        stem = w[:-2]
        if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in "aeiouy":
            add(stem[:-1], "ed") # stopped -> stop
        add(stem, "ed")          # walked -> walk
        add(stem + "e", "ed")    # loved -> love

    # 4. Герундий и длительная форма (-ing)
    # ВАЖНО: для глаголов на -ying нужно генерировать И -ie (satisfying -> satisfie, lying -> lie),
    # И прямое удаление -ing (satisfying -> satisfy, studying -> study, carrying -> carry)!
    if w.endswith("ying") and len(w) > 4:
        add(w[:-4] + "ie", "ing") # satisfying -> satisfie, lying -> lie
        add(w[:-3], "ing")        # satisfying -> satisfy, study -> studying
    elif w.endswith("ing") and len(w) > 4:
        stem = w[:-3]
        if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in "aeiouy":
            add(stem[:-1], "ing") # running -> run
        add(stem, "ing")          # walking -> walk
        add(stem + "e", "ing")    # making -> make

    # 5. Множественное число и 3-е лицо глаголов (-s, -es, -ies, -ves)
    if w.endswith("ves") and len(w) > 4:
        add(w[:-3] + "f", "s")  # leaves -> leaf
        add(w[:-3] + "fe", "s") # knives -> knife
        add(w[:-1], "s")        # lives -> live
    elif w.endswith("ies") and len(w) > 3:
        add(w[:-3] + "y", "s")  # cities -> city
        add(w[:-1], "s")        # ties -> tie
    elif w.endswith("es") and len(w) > 3:
        if any(w.endswith(s + "es") for s in ("ch", "sh", "ss", "zz", "x")):
            add(w[:-2], "s")    # boxes -> box, watches -> watch
        else:
            add(w[:-2], "s")    # tomatoes -> tomato
            add(w[:-1], "s")    # houses -> house
    elif w.endswith("s") and not w.endswith("ss") and len(w) > 2:
        add(w[:-1], "s")        # books -> book

    # 6. Наречия (-ly, -ily) и существительные (-ness, -iness)
    if w.endswith("ily") and len(w) > 4:
        add(w[:-3] + "y", "ly")  # happily -> happy
    elif w.endswith("ally") and len(w) > 5:
        add(w[:-4] + "ic", "ly") # basically -> basic
    elif w.endswith("ly") and len(w) > 3:
        add(w[:-2], "ly")        # greatly -> great

    if w.endswith("iness") and len(w) > 5:
        add(w[:-5] + "y", "ness")  # happiness -> happy
    elif w.endswith("ness") and len(w) > 4:
        add(w[:-4], "ness")        # greatness -> great

    return candidates

def deinflect_english(w: str) -> list[str]:
    """Обратная совместимость: возвращает только список лемм без тегов."""
    return [c for c, _ in deinflect_english_with_tags(w)]


class DictionaryManager:
    def __init__(self):
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path())
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with _DB_LOCK:
            with self._get_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS dictionaries (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        revision TEXT,
                        author TEXT,
                        description TEXT,
                        source_lang TEXT,
                        target_lang TEXT,
                        term_count INTEGER DEFAULT 0,
                        enabled INTEGER DEFAULT 1,
                        created_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS terms (
                        dict_id TEXT,
                        term TEXT COLLATE NOCASE,
                        reading TEXT,
                        pos TEXT,
                        score INTEGER DEFAULT 0,
                        glossary_json TEXT,
                        seq INTEGER DEFAULT 0
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_term ON terms(term)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_dict_term ON terms(dict_id, term)")

    def list_dictionaries(self) -> list[dict]:
        with _DB_LOCK:
            with self._get_conn() as conn:
                rows = conn.execute("SELECT * FROM dictionaries ORDER BY title ASC").fetchall()
                return [dict(r) for r in rows]

    def get_dictionary(self, dict_id: str) -> dict | None:
        with _DB_LOCK:
            with self._get_conn() as conn:
                r = conn.execute("SELECT * FROM dictionaries WHERE id = ?", (dict_id,)).fetchone()
                return dict(r) if r else None

    def toggle_dictionary(self, dict_id: str, enabled: bool):
        with _DB_LOCK:
            with self._get_conn() as conn:
                conn.execute("UPDATE dictionaries SET enabled = ? WHERE id = ?",
                             (1 if enabled else 0, dict_id))

    def delete_dictionary(self, dict_id: str):
        with _DB_LOCK:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM terms WHERE dict_id = ?", (dict_id,))
                conn.execute("DELETE FROM dictionaries WHERE id = ?", (dict_id,))

    def import_zip(self, zip_path: str, progress_callback=None) -> dict:
        """Импортирует Yomitan-словарь из .zip архива."""
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"Файл не найден: {zip_path}")

        with zipfile.ZipFile(zip_path) as z:
            namelist = z.namelist()
            if "index.json" not in namelist:
                raise ValueError("Архив не содержит index.json (не является словарём Yomitan).")

            meta = json.loads(z.read("index.json").decode("utf-8"))
            title = meta.get("title", os.path.splitext(os.path.basename(zip_path))[0])
            dict_id = re.sub(r"[^\w\-]", "_", title.strip().lower())
            revision = str(meta.get("revision", ""))
            author = meta.get("author", "")
            description = meta.get("description", "")
            source_lang = meta.get("sourceLanguage", "en")
            target_lang = meta.get("targetLanguage", "ru")

            term_banks = [n for n in namelist if re.match(r"^term_bank_\d+\.json$", os.path.basename(n))]
            if not term_banks:
                raise ValueError("В архиве не найдено файлов статей (term_bank_*.json).")

            with _DB_LOCK:
                with self._get_conn() as conn:
                    # Удаляем старую версию этого словаря, если была
                    conn.execute("DELETE FROM terms WHERE dict_id = ?", (dict_id,))
                    conn.execute("DELETE FROM dictionaries WHERE id = ?", (dict_id,))

                    total_terms = 0
                    for idx, bank_name in enumerate(term_banks):
                        if progress_callback:
                            progress_callback(idx + 1, len(term_banks), bank_name)

                        bank_data = json.loads(z.read(bank_name).decode("utf-8"))
                        batch = []
                        for row in bank_data:
                            # Yomitan term format:
                            # [expression, reading, definition_tags, rules, score, [glossary...], seq, term_tags]
                            if not row or not isinstance(row, list):
                                continue
                            term = str(row[0]).strip()
                            reading = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                            pos = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                            score = int(row[4]) if len(row) > 4 and isinstance(row[4], (int, float)) else 0
                            glosses = json.dumps(row[5], ensure_ascii=False) if len(row) > 5 else "[]"
                            seq = int(row[6]) if len(row) > 6 and isinstance(row[6], int) else 0

                            batch.append((dict_id, term, reading, pos, score, glosses, seq))

                        if batch:
                            conn.executemany("""
                                INSERT INTO terms (dict_id, term, reading, pos, score, glossary_json, seq)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, batch)
                            total_terms += len(batch)

                    # Записываем словарь в реестр
                    conn.execute("""
                        INSERT INTO dictionaries (id, title, revision, author, description,
                                                  source_lang, target_lang, term_count, enabled, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """, (dict_id, title, revision, author, description,
                          source_lang, target_lang, total_terms, time.time()))

            return {
                "id": dict_id,
                "title": title,
                "term_count": total_terms,
                "revision": revision,
                "author": author,
                "description": description,
            }

    def _fetch_term_rows(self, conn, term: str, dict_id: str | None = None):
        query = """
            SELECT t.dict_id, d.title AS dict_title, t.term, t.reading, t.pos, t.score, t.glossary_json, t.seq
            FROM terms t
            JOIN dictionaries d ON t.dict_id = d.id
            WHERE d.enabled = 1 AND t.term = ?
        """
        params = [term]
        if dict_id:
            query += " AND t.dict_id = ?"
            params.append(dict_id)
        query += " ORDER BY t.score DESC, t.seq ASC"
        return conn.execute(query, params).fetchall()

    def lookup(self, word: str, dict_id: str | None = None) -> list[dict]:
        """Поиск слова во всех включённых офлайн-словарях (или в конкретном dict_id).
        Поддерживает деинфлекцию/лемматизацию в точности как в Yomitan:
        - удовлетворяет запросы по непрямым формам (satisfying -> satisfie, satisfy)
        - находит степени сравнения (greater -> great)
        - разрешает non-lemma ссылки словарей на базовые словарные статьи
        - возвращает полноценные статьи с грамматическими тегами инфлекции (ing, s, er...)."""
        w = word.strip().lower()
        if not w:
            return []

        with _DB_LOCK:
            with self._get_conn() as conn:
                # 1. Поиск точного совпадения
                exact_rows = self._fetch_term_rows(conn, w, dict_id)
                if not exact_rows and word != w:
                    exact_rows = self._fetch_term_rows(conn, word, dict_id)

                lemma_rows = [r for r in exact_rows if (r["pos"] or "").strip().lower() != "non-lemma"]
                non_lemma_rows = [r for r in exact_rows if (r["pos"] or "").strip().lower() == "non-lemma"]

                # 2. Сбор кандидатов-лемм (target_lemma, tag)
                candidates: list[tuple[str, str]] = []
                seen_candidates = set()

                # 2a. Деинфлекция по правилам английского языка (Yomitan deinflector)
                # Например: satisfying -> [('satisfie', 'ing'), ('satisfy', 'ing')], greater -> [('great', 'er')]
                for cand, tag in deinflect_english_with_tags(w):
                    c_norm = cand.strip().lower()
                    if c_norm and c_norm not in seen_candidates and c_norm != w:
                        seen_candidates.add(c_norm)
                        candidates.append((cand.strip(), tag))

                # 2b. Ссылки из non-lemma записей словаря (например, satisfying -> satisfy [gerund])
                for r in non_lemma_rows:
                    for target, tag in parse_non_lemma_references(r["glossary_json"]):
                        t_norm = target.strip().lower()
                        if t_norm and t_norm not in seen_candidates and t_norm != w:
                            seen_candidates.add(t_norm)
                            candidates.append((target.strip(), tag or "inflection"))

                # 3. Формируем список пар (строка БД, deinflected_from, inflection_tag)
                final_pairs: list[tuple[sqlite3.Row, str | None, str | None]] = []

                # Если есть прямые леммы исходного слова — показываем их первыми
                for r in lemma_rows:
                    final_pairs.append((r, None, None))

                # Запрашиваем статьи для каждого кандидата
                for cand, tag in candidates:
                    cand_rows = self._fetch_term_rows(conn, cand, dict_id)
                    if not cand_rows and cand.lower() != cand:
                        cand_rows = self._fetch_term_rows(conn, cand.lower(), dict_id)
                    for cr in cand_rows:
                        # Пропускаем ссылки non-lemma от кандидатов — берем только реальные статьи
                        if (cr["pos"] or "").strip().lower() == "non-lemma":
                            continue
                        final_pairs.append((cr, word, tag))

                # Крайний fallback: если ничего не найдено, но были non-lemma строки
                if not final_pairs and non_lemma_rows:
                    for r in non_lemma_rows:
                        final_pairs.append((r, None, None))

                # Устраняем дубликаты строк БД (по dict_id, term, pos, seq)
                seen_entries = set()
                unique_pairs = []
                for r, deinf_from, inf_tag in final_pairs:
                    key = (r["dict_id"], r["term"].lower(), (r["pos"] or "").lower(), r["seq"])
                    if key not in seen_entries:
                        seen_entries.add(key)
                        unique_pairs.append((r, deinf_from, inf_tag))

                results = []
                for r, deinflected_from, inflection_tag in unique_pairs:
                    try:
                        raw_gloss = json.loads(r["glossary_json"])
                    except Exception:
                        raw_gloss = []

                    pos = r["pos"] or ""
                    d_title = r["dict_title"] or r["dict_id"]
                    rendered = render_yomitan_node(raw_gloss)

                    # Структурный разбор узлов
                    parsed = None
                    if isinstance(raw_gloss, list):
                        for sc in raw_gloss:
                            if isinstance(sc, dict) and sc.get("type") == "structured-content":
                                p = parse_yomitan_sense(sc)
                                if p["glosses"] or p["etymologies"]:
                                    parsed = p
                                    break

                    plain = ""
                    if parsed and parsed.get("glosses"):
                        plain = "; ".join(g["text"] for g in parsed["glosses"])

                    results.append({
                        "dict_id": r["dict_id"],
                        "dict_title": d_title,
                        "term": r["term"],
                        "reading": r["reading"] or "",
                        "pos": pos,
                        "glossary_raw": raw_gloss,
                        "parsed": parsed,
                        "html": rendered,
                        "text": plain,
                        "deinflected_from": deinflected_from,
                        "inflection_tag": inflection_tag,
                    })

                return results

    def format_glossary_html(self, results: list[dict], target_dict_id: str | None = None) -> str:
        """Форматирует найденные статьи в красивый HTML для Anki (в точности как в Yomitan)."""
        filtered = [r for r in results if not target_dict_id or r["dict_id"] == target_dict_id]
        if not filtered:
            return ""

        parts = []
        for i, entry in enumerate(filtered, 1):
            pos = entry.get("pos", "").strip()
            d_title = entry.get("dict_title", entry.get("dict_id", "")).strip()
            deinf = entry.get("deinflected_from")
            inf_tag = entry.get("inflection_tag")

            badges = []
            if inf_tag:
                badges.append(
                    f"<span style='background:#193822; color:#4ade80; border:1px solid #275635; "
                    f"border-radius:4px; padding:1px 6px; font-size:11px; font-weight:600; margin-right:4px;'>"
                    f"🧩 {html.escape(inf_tag)}</span>"
                )
            if deinf:
                badges.append(
                    f"<span style='background:#1a3a5c; color:#60cdff; border:1px solid #2a5a8c; "
                    f"border-radius:4px; padding:1px 6px; font-size:11.5px; font-weight:600; margin-right:4px;'>"
                    f"{html.escape(entry['term'])} ← {html.escape(deinf)}</span>"
                )
            if pos:
                badges.append(
                    f"<span style='background:#383838; color:#cccccc; border:1px solid #484848; "
                    f"border-radius:10px; padding:1px 8px; font-size:11px; font-weight:600; margin-right:4px;'>({html.escape(pos)})</span>"
                )
            if d_title:
                badges.append(
                    f"<span style='background:#7042a6; color:#ffffff; border-radius:4px; "
                    f"padding:1px 6px; font-size:11px; font-weight:600;'>{html.escape(d_title)}</span>"
                )
            badge_html = " ".join(badges)
            term_title = f"<b style='color:#ffffff; font-size:15px; margin-right:6px;'>{html.escape(entry['term'])}</b>"
            header = f"<div style='margin-top:10px; margin-bottom:4px; font-size:13.5px;'>{term_title}{badge_html}</div>"

            parsed = entry.get("parsed")
            if not parsed and entry.get("glossary_raw") and isinstance(entry["glossary_raw"], list):
                for sc in entry["glossary_raw"]:
                    if isinstance(sc, dict) and sc.get("type") == "structured-content":
                        p = parse_yomitan_sense(sc)
                        if p["glosses"] or p["etymologies"]:
                            parsed = p
                            break

            body_parts = []
            if parsed and (parsed.get("etymologies") or parsed.get("glosses")):
                # Этимология (свёрнута по умолчанию)
                for etym in parsed.get("etymologies", []):
                    body_parts.append(
                        f"<details style='margin:3px 0 6px 12px; font-size:13px;'>"
                        f"<summary style='color:#4ea8de; cursor:pointer; font-weight:500; outline:none;'>{html.escape(etym['summary'])}</summary>"
                        f"<div style='margin:4px 0; padding-left:8px; border-left:2px solid #484848; color:#cccccc; font-size:12.5px; line-height:1.45;'>{etym['body']}</div>"
                        f"</details>"
                    )

                # Определения
                if parsed.get("glosses"):
                    body_parts.append("<ol style='margin:4px 0 6px 18px; padding:0; font-size:13.5px; line-height:1.4;'>")
                    for g in parsed["glosses"]:
                        ex_html = ""
                        if g.get("examples"):
                            ex_items = []
                            for ex in g["examples"]:
                                if ex.get("a"):
                                    ex_items.append(f"<div style='color:#dcdcdc;'>{ex['a']}</div>")
                                if ex.get("b"):
                                    ex_items.append(f"<div style='color:#999999;'>{ex['b']}</div>")
                            ex_html = (
                                f" <details style='display:inline-block; margin-left:6px;'>"
                                f"<summary style='color:#4ea8de; cursor:pointer; list-style:none; display:inline;' title='Примеры'>▸</summary>"
                                f"<div style='padding-left:12px; margin:4px 0; color:#aaa; font-size:12px; line-height:1.35;'>{''.join(ex_items)}</div>"
                                f"</details>"
                            )
                        body_parts.append(f"<li style='margin-bottom:3px;'><span>{g['text']}</span>{ex_html}</li>")
                    body_parts.append("</ol>")

                # Ссылки (Wiktionary | Kaikki)
                if parsed.get("backlinks"):
                    links = [
                        f"<a href='{html.escape(b['href'])}' style='color:#4ea8de; text-decoration:none;'>{html.escape(b['title'])} ↗</a>"
                        for b in parsed["backlinks"]
                    ]
                    body_parts.append(f"<div style='text-align:right; font-size:11px; color:#888888; margin-top:4px;'>{' | '.join(links)}</div>")
            else:
                body_parts.append(f"<div style='margin-left:12px;'>{entry.get('html', '')}</div>")

            parts.append(f"{header}\n<div style='margin-left:4px; margin-bottom:10px;'>{''.join(body_parts)}</div>")

        return "\n".join(parts)

    def format_glossary_brief(self, results: list[dict]) -> str:
        """Возвращает краткие значения первого значения слова."""
        if not results:
            return ""
        first = results[0]
        parsed = first.get("parsed")
        if parsed and parsed.get("glosses"):
            return parsed["glosses"][0]["text"]
        text = first.get("text", "")
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return ", ".join(lines[:3]) if lines else text[:100]


def dict_key(dict_id: str) -> str:
    return f"dict:{dict_id}"

def normalize_key(key: str) -> str:
    return key[5:] if key.startswith("dict:") else key

DICTIONARIES = DictionaryManager()
