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
    for i, c in enumerate(item.get("lines", []), 1):
        out.append((f"linje {i}", str(c)))
    return out


def check_klip(item):
    """Klip-reel: eget billede eller klip i baggrunden og 1 til 4 korte linjer tekst."""
    p = []
    lines = item.get("lines")
    if not isinstance(lines, list) or not 1 <= len(lines) <= 4 or not all(isinstance(x, str) and x.strip() for x in lines):
        return ["Klip-reel kræver feltet 'lines' med 1 til 4 korte linjer tekst."]
    for i, t in enumerate(lines, 1):
        n = len(common.strip_marks(t))
        if n > 70:
            p.append(f"linje {i}: {n} tegn. En linje på et klip må højst være 70 tegn.")
        if EMOJI.search(t):
            p.append(f"linje {i}: emojis kan ikke gengives på klippet. Brug dem kun i captionen.")
    words = sum(len(common.strip_marks(t).split()) for t in lines)
    if words > 34:
        p.append(f"Klippet har {words} ord. Højst 34, ellers når ingen at læse det.")
    if re.search(r"mini-test|link i bio|ikigai|ikiguiden|gratis", lines[0], re.I):
        p.append("linje 1: første linje skal stoppe en fremmed og må ikke nævne testen, profilen eller link i bio.")
    bg = str(item.get("bg", ""))
    f = common.ROOT / bg
    ok_img = bg.startswith(common.PHOTO_DIR + "/") and f.suffix.lower() in common.KLIP_IMAGE_EXT
    ok_vid = bg.startswith(common.KLIP_DIR + "/") and f.suffix.lower() in common.KLIP_VIDEO_EXT
    if not (ok_img or ok_vid) or ".." in bg or not f.is_file():
        p.append(f"Klip-reel kræver feltet 'bg' med et billede i {common.PHOTO_DIR}/ eller et klip i {common.KLIP_DIR}/, fandt '{bg}'.")
    if item.get("stil", "hvid") not in common.KLIP_STYLES:
        p.append(f"Ukendt stil '{item.get('stil')}' (skal være en af {', '.join(common.KLIP_STYLES)}).")
    if item.get("slides") or item.get("cards"):
        p.append("En klip-reel bruger kun 'lines', ikke 'slides' eller 'cards'.")
    total = common.klip_times(item)[1]
    if not 5 <= total <= 15:
        p.append(f"Klippet varer {total:.0f} sekunder. Skal være 5 til 15.")
    return p


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
    if item.get("dm") not in (None, "studievalg", "arketype"):
        p.append("Feltet 'dm' skal være 'studievalg' eller 'arketype' (det link, en TEST-kommentar får).")
    kind = item["type"]
    if kind not in ("carousel", "reel"):
        p.append(f"Ukendt type '{kind}' (skal være carousel eller reel).")
    klip = kind == "reel" and item.get("format") == "klip"
    if item.get("format") == "klip" and kind != "reel":
        p.append("Formatet 'klip' kræver \"type\": \"reel\".")
    # Tekstkort som video virkede ikke og er slået fra. Den eneste reel, der må laves, er formatet "klip".
    try:
        if kind == "reel" and not klip and common.parse_when(item["publish_at"]) >= REELS_STOP:
            p.append("Tekst-reels er slået fra. Lav en klip-reel (\"format\": \"klip\" med lines og bg) eller en karrusel.")
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
    if klip:
        p += check_klip(item)
    elif tema not in common.THEME_NAMES:
        p.append(f"Ukendt tema '{tema}' (skal være et af {', '.join(common.THEME_NAMES)}).")
    if klip:
        pass
    elif tema == "foto":
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
    elif kind == "reel" and not klip:
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
