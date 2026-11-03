"""Undersøger Instagrams lyd-API (ig_audio) mod den rigtige konto. Udgiver INTET.

Opretter højst prøve-containere (de udløber af sig selv efter et døgn og vises aldrig).
Nøglen skrives aldrig ud.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN = os.environ["IG_ACCESS_TOKEN"]
IG = json.loads((ROOT / "config.json").read_text())["instagram_user_id"]
REPO = os.environ.get("GITHUB_REPOSITORY", "cstoDK/ikiguiden-autopilot")
SHA = os.environ.get("GITHUB_SHA", "main")


def call(method, path, params, version):
    params = {**params, "access_token": TOKEN}
    url = f"https://graph.facebook.com/{version}/{path}"
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def show(label, res):
    txt = json.dumps(res, ensure_ascii=False).replace(TOKEN, "***")
    print(f"{label}: {txt[:900]}")


audio_id = None
version = "v26.0"
for params in ({"audio_type": "music", "ig_user_id": IG, "q": "lofi"},
               {"audio_type": "music", "ig_user_id": IG, "search_query": "lofi chill"},
               {"audio_type": "music", "ig_user_id": IG}):
    st, res = call("GET", "ig_audio", params, version)
    items = (res.get("audio") or res.get("data") or []) if isinstance(res, dict) else []
    print(f"GET ig_audio {params}: status {st}, {len(items)} numre, nøgler {list(res)[:5] if isinstance(res, dict) else ''}")
    for it in items[:6]:
        print("   ", it.get("audio_id"), "|", it.get("title"), "|", it.get("display_artist"), "|", it.get("duration_in_ms"))
    if isinstance(res, dict) and res.get("error"):
        show("   fejl", res)
    if items and not audio_id:
        audio_id = items[0].get("audio_id")

print("FUNDET audio_id:", audio_id, "version:", version)
if not audio_id:
    sys.exit(0)

video = f"https://raw.githubusercontent.com/{REPO}/{SHA}/media/2026-W45/2026-W45-tirsdag-1200-reel/reel.mp4"
st, res = call("GET", str(audio_id), {"fields": "id,title,display_artist,audio_type,duration_in_ms"}, version)
show("GET audio metadata", [st, res])
candidates = [
    {"audio_id": audio_id},
    {"audio_configuration": json.dumps({"audio_id": audio_id})},
    {"audio_configuration": json.dumps([{"audio_id": audio_id}])},
    {"music_sound_id": audio_id},
    {"audio_name": "x", "bogus_param_xyz": "1"},  # kontrol: afviser API'et ukendte felter?
]
for extra in candidates:
    st, res = call("POST", f"{IG}/media", {"media_type": "REELS", "video_url": video, **extra}, version)
    show(f"POST container {list(extra)}", [st, res])
