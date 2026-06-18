"""Офлайн-словарь Oxford-слота.
Oxford — проприетарные данные, поэтому слот заполняется свободным словарём
(dictionaryapi.dev) либо пользовательскими офлайн-словарями."""
import requests

def oxford_slot_lookup(word: str) -> dict | None:
    """Свободный англоязычный словарь для слота 'Oxford (Английский → Русский)'."""
    try:
        r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=12)
        if r.status_code != 200:
            return None
        data = r.json()[0]
        phon = ""
        for p in data.get("phonetics", []):
            if p.get("text"):
                phon = p["text"]
                break
        senses = []
        for m in data.get("meanings", [])[:2]:
            pos = m.get("partOfSpeech", "")
            for d in m.get("definitions", [])[:2]:
                senses.append({"pos": pos, "def": d.get("definition", ""),
                               "example": d.get("example", "")})
        return {"word": data.get("word", word), "phonetic": phon, "senses": senses}
    except Exception:
        return None
