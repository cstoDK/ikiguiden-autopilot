"""Kvalitetsport. Et opslag med fejl bliver hverken bygget eller udgivet.

Brug: python3 pipeline/lint.py            (tjekker alle opslag i queue/)
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

FORBIDDEN = {
    "—": "tankestreg (em dash)",
    "–": "tankestreg (en dash)",
    "‘": "krøllet citationstegn",
    "’": "krøllet citationstegn",
    "“": "krøllet citationstegn",
    "”": "krøllet citationstegn",
    "…": "tegnet for tre prikker",
    " ": "hårdt mellemrum",
}
HASHTAG = re.compile(r"(?<!\w)#\w+", re.UNICODE)
NUMBER = re.compile(r"\d[\d.,]*")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
URL = re.compile(r"https?://|www\.", re.I)


def texts(item):
    out = [("caption", item.get("caption", ""))]
    for i, s in enumerate(item.get("slides", []), 1):
        out.append((f"slide {i}", " ".join(s.get("h", []) + s.get("sub", []))))
    for i, c in enumerate(item.get("cards", []), 1):
        out.append((f"kort {i}", c))
    return out


def check(item):
    """Returnerer en liste af fejl. Tom liste = opslaget må udgives."""
    p = []
    for key in ("id", "type", "publish_at", "caption"):
        if not item.get(key):
            p.append(f"Feltet '{key}' mangler.")
    if p:
        return p
    try:
        common.parse_when(item["publish_at"])
    except ValueError as e:
        p.append(str(e))
    kind = item["type"]
    if kind not in ("carousel", "reel"):
        p.append(f"Ukendt type '{kind}' (skal være carousel eller reel).")

    cap = item["caption"]
    if len(cap) > 2200:
        p.append(f"Caption er {len(cap)} tegn, grænsen er 2200.")
    first = cap.strip().split("\n")[0]
    if len(first) > 125:
        p.append(f"Første linje er {len(first)} tegn og bliver klippet midt i en tanke ved 125.")
    if first.startswith("#") or EMOJI.match(first[:1] or " "):
        p.append("Captionen må ikke starte med hashtag eller emoji.")
    tags = HASHTAG.findall(cap)
    if len(tags) > 5:
        p.append(f"{len(tags)} hashtags. Instagram tillader højst 5.")
    if URL.search(cap):
        p.append("Link i captionen er dødt. Brug 'link i bio'.")
    if len(EMOJI.findall(cap)) > 2:
        p.append("Mere end 2 emojis i captionen.")

    facts = " | ".join(item.get("facts", []))
    for where, t in texts(item):
        for ch in t:
            if ch in FORBIDDEN:
                p.append(f"{where}: {FORBIDDEN[ch]}.")
                break
            if unicodedata.category(ch) == "Cf" and ch != "‍":
                p.append(f"{where}: skjult tegn U+{ord(ch):04X}.")
                break
        for n in NUMBER.findall(t):
            if n.strip(".,") not in facts:
                p.append(f"{where}: tallet '{n}' er ikke dækket af 'facts'. Opfundne tal må ikke ud.")

    if kind == "carousel":
        slides = item.get("slides", [])
        if not 5 <= len(slides) <= 10:
            p.append(f"Karrusel har {len(slides)} slides. Skal være 5 til 10.")
        for i, s in enumerate(slides, 1):
            if not s.get("h"):
                p.append(f"slide {i}: mangler overskrift.")
    if kind == "reel":
        cards = item.get("cards", [])
        if not 5 <= len(cards) <= 16:
            p.append(f"Reel har {len(cards)} kort. Skal være 5 til 16.")
        total = sum(common.card_seconds(c) for c in cards)
        if not 15 <= total <= 60:
            p.append(f"Reel varer ca. {total:.0f} sekunder. Skal være 15 til 60.")
    return p


def main():
    bad = 0
    n = 0
    for item in common.queue_items():
        n += 1
        probs = check(item)
        name = item.get("id", item["_path"].name)
        if probs:
            bad += 1
            print(f"FEJL  {name}")
            for x in probs:
                print(f"        {x}")
        else:
            print(f"ok    {name}")
    print(f"\n{n} opslag, {bad} med fejl.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
