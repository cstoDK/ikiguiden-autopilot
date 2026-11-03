"""Fælles hjælpefunktioner for Ikiguiden-autopiloten."""
import json
import os
import re
import subprocess
from datetime import datetime
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
