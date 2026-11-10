"""Fælles hjælpefunktioner for Ikiguiden-autopiloten."""
import json
import os
import re
import subprocess
import hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("AUTOPILOT_ROOT") or Path(__file__).resolve().parent.parent)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_when(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("publish_at skal have tidszone, fx 2026-11-03T19:00:00+01:00")
    return dt


def queue_items():
    for path in sorted((ROOT / "queue").glob("*/*.json")):
        item = read_json(path)
        item["_path"] = path
        yield item


def clean(item):
    return {k: v for k, v in item.items() if not k.startswith("_")}


def media_dir(item):
    return ROOT / "media" / item["_path"].parent.name / item["id"]


def strip_marks(text):
    return re.sub(r"\[\[|\]\]", "", text)


def card_seconds(text):
    """Hvor længe et tekstkort står på skærmen i en stum reel (læsetid)."""
    words = len(strip_marks(text).split())
    return round(min(4.5, max(1.8, 0.7 + 0.38 * words)), 2)


def ensure_fonts():
    """Henter Playfair Display og Inter via npm, hvis de ikke allerede er hentet."""
    base = ROOT / ".fonts" / "node_modules" / "@fontsource"
    need = ["playfair-display", "inter"]
    if not all((base / n / "files").exists() for n in need):
        subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund", "--prefix", str(ROOT / ".fonts"),
             "@fontsource/playfair-display", "@fontsource/inter"],
            check=True,
        )
    return base


def slide_seconds(slide):
    """Hvor længe en slide står stille i en swipe-reel, før den glider videre."""
    words = len(strip_marks(" ".join(slide.get("h", []) + slide.get("sub", []))).split())
    return round(min(5.5, max(2.6, 0.9 + 0.33 * words)), 2)


SWIPE_SECONDS = 0.55


# Temaer, som render.py kan tegne. "foto" kræver feltet "bg" med et billede i brand/baggrunde/.
THEME_NAMES = ("lys", "mørk", "grøn", "brun", "foto")
PHOTO_DIR = "brand/baggrunde"


# ---------------- Musik på karruseller ----------------
# Instagrams API tillader ikke musik fra biblioteket på karruseller. Derfor bliver hver slide en kort
# video med et rigtigt instrumentalnummer fra brand/musik/ (Kevin MacLeod, CC BY 4.0). Karrusellen
# er stadig en ægte karrusel, man swiper i, men der spiller musik på hver slide.
MUSIC_DIR = "brand/musik"
MUSIC_FROM = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
SLIDE_VIDEO_SECONDS = 12   # hver slide-video; Instagram looper den, hvis man bliver hængende
SLIDE_AUDIO_STEP = 5       # slide 2 fortsætter nummeret 5 sekunder længere fremme osv.


def music_tracks():
    f = ROOT / MUSIC_DIR / "liste.txt"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if "|" in line:
            name, title = line.split("|", 1)
            if (ROOT / MUSIC_DIR / name).is_file():
                out.append((name.strip(), title.strip()))
    return out


def carousel_music(item):
    """Nummeret (fil, titel) til en karrusel, eller None hvis den skal være uden musik."""
    if item.get("type") != "carousel" or item.get("musik") is False:
        return None
    try:
        if parse_when(item["publish_at"]) < MUSIC_FROM:
            return None
    except (KeyError, ValueError):
        return None
    tracks = music_tracks()
    if not tracks:
        return None
    if item.get("musik") and isinstance(item["musik"], str):
        for t in tracks:
            if t[0] == item["musik"]:
                return t
    return tracks[int(hashlib.sha1(item["id"].encode()).hexdigest()[:8], 16) % len(tracks)]


def music_credit(track):
    return f"Musik: {track[1]} af Kevin MacLeod (incompetech.com), CC BY 4.0"
