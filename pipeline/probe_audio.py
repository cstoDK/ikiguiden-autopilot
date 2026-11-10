"""Undersøger om Instagram tager imod musik på karruseller. Udgiver INTET.

Opretter kun prøve-containere (de udløber af sig selv og vises aldrig). Nøglen skrives aldrig ud.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN = os.environ["IG_ACCESS_TOKEN"]
IG = json.loads((ROOT / "config.json").read_text())["instagram_user_id"]
REPO = os.environ.get("GITHUB_REPOSITORY", "cstoDK/ikiguiden-autopilot")
SHA = os.environ.get("GITHUB_SHA", "main")
BASE = "https://graph.facebook.com" if TOKEN.startswith("EAA") else "https://graph.instagram.com"


def call(method, path, params, version):
    params = {**params, "access_token": TOKEN}
    url = f"{BASE}/{version}/{path}"
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method), timeout=90) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def show(label, res):
    print(f"{label}: {json.dumps(res, ensure_ascii=False).replace(TOKEN, '***')[:700]}", flush=True)


def wait(cid, version):
    import time
    for _ in range(30):
        st, r = call("GET", cid, {"fields": "status_code,status"}, version)
        if r.get("status_code") in ("FINISHED", "ERROR", "EXPIRED"):
            return r
        time.sleep(4)
    return r


img = f"https://raw.githubusercontent.com/{REPO}/{SHA}/media/2026-W46/2026-W46-tirsdag-1900-karrusel/slide-0{{}}.jpg"
for version in ("v23.0", "v26.0"):
    print(f"\n===== {version} =====")
    st, res = call("GET", "ig_audio", {"audio_type": "music", "ig_user_id": IG, "search_query": "chill piano"}, version)
    tracks = res.get("audio") or []
    print("ig_audio", st, len(tracks))
    if not tracks:
        show("ig_audio", res)
        continue
    aid = str(tracks[0]["audio_id"])
    kids = []
    for i in (1, 2):
        st, r = call("POST", f"{IG}/media", {"image_url": img.format(i), "is_carousel_item": "true"}, version)
        show(f"barn {i}", [st, r])
        if r.get("id"):
            wait(r["id"], version)
            kids.append(r["id"])
    if len(kids) < 2:
        continue
    ch = ",".join(kids)
    variants = {
        "cfg fuld": {"audio_configuration": json.dumps({"audio_id": aid, "audio_volume": 100, "video_volume": 0})},
        "cfg kun id": {"audio_configuration": json.dumps({"audio_id": aid})},
        "cfg liste": {"audio_configuration": json.dumps([{"audio_id": aid}])},
        "audio_id": {"audio_id": aid},
        "music_id": {"music_id": aid},
        "audio_asset_id": {"audio_asset_id": aid},
        "kontrol bogus": {"bogus_param_xyz": "1"},
        "kontrol ingen": {},
    }
    for name, extra in variants.items():
        st, r = call("POST", f"{IG}/media", {"media_type": "CAROUSEL", "children": ch, "caption": "test", **extra}, version)
        show(f"KARRUSEL {name}", [st, r])
        if r.get("id"):
            show("   status", wait(r["id"], version))
    # Musik på et enkelt barn
    st, r = call("POST", f"{IG}/media", {"image_url": img.format(3), "is_carousel_item": "true",
                                          "audio_configuration": json.dumps({"audio_id": aid})}, version)
    show("BARN med cfg", [st, r])
