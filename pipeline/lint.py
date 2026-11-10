"""Kvalitetsport. Et opslag med fejl bliver hverken bygget eller udgivet.

Brug: python3 pipeline/lint.py            (tjekker alle opslag i queue/)
"""
import re
import sys
import unicodedata
from datetime import datetime, timezone
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
REELS_STOP = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


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
    # Video-karruseller (reels med tekst) virkede ikke. Fra uge 46 udgives kun ægte karruseller.
    try:
        if kind == "reel" and common.parse_when(item["publish_at"]) >= REELS_STOP:
            p.append("Reels er slået fra. Lav opslaget som \"type\": \"carousel\" med slides.")
    except ValueError:
        pass

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

    tema = item.get("tema", "lys")
    if tema not in common.THEME_NAMES:
        p.append(f"Ukendt tema '{tema}' (skal være et af {', '.join(common.THEME_NAMES)}).")
    if tema == "foto":
        bg = str(item.get("bg", ""))
        f = common.ROOT / bg
        if not bg.startswith(common.PHOTO_DIR + "/") or f.suffix.lower() not in (".jpg", ".jpeg", ".png") or not f.is_file():
            p.append(f"Tema 'foto' kræver feltet 'bg' med et billede i {common.PHOTO_DIR}/, fandt '{bg}'.")
    elif item.get("bg"):
        p.append("Feltet 'bg' bruges kun sammen med tema 'foto'.")

    facts = " | ".join(item.get("facts", []))
    # Liste-karruseller: antallet af punkter er strukturelt, ikke en faktapåstand ("5 ting ...").
    n_list = sum(1 for sl in item.get("slides", []) if sl.get("kind") == "liste")
    if n_list:
        facts += f" | {n_list}"
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

    if kind == "carousel" or (kind == "reel" and item.get("slides")):
        slides = item.get("slides", [])
        if not 5 <= len(slides) <= 10:
            p.append(f"Karrusel har {len(slides)} slides. Skal være 5 til 10.")
        for i, s in enumerate(slides, 1):
            if not s.get("h"):
                p.append(f"slide {i}: mangler overskrift.")
            if s.get("kind", "text") not in ("hook", "text", "cta", "liste", "produkt"):
                p.append(f"slide {i}: ukendt slide-type '{s.get('kind')}'.")
        nums = [s.get("num") for s in slides if s.get("kind") == "liste"]
        if nums and nums != list(range(1, len(nums) + 1)):
            p.append(f"Liste-slides skal nummereres 1 til {len(nums)} i rækkefølge, fandt {nums}.")
        if nums and slides[-1].get("kind") not in ("produkt", "cta"):
            p.append("En liste-karrusel skal slutte med en produkt- eller cta-slide.")
    if kind == "reel" and item.get("slides"):
        total = sum(common.slide_seconds(s) for s in item["slides"]) + common.SWIPE_SECONDS * (len(item["slides"]) - 1)
        if not 15 <= total <= 60:
            p.append(f"Swipe-reel varer ca. {total:.0f} sekunder. Skal være 15 til 60.")
    elif kind == "reel":
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
