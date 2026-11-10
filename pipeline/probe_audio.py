"""Prøver om Instagram tager imod en karrusel med video-slides (med musik). Udgiver INTET."""
import json, os, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
TOKEN = os.environ["IG_ACCESS_TOKEN"]
IG = json.loads((ROOT / "config.json").read_text())["instagram_user_id"]
REPO = os.environ.get("GITHUB_REPOSITORY", "cstoDK/ikiguiden-autopilot")
SHA = os.environ.get("GITHUB_SHA", "main")
BASE = ("https://graph.facebook.com" if TOKEN.startswith("EAA") else "https://graph.instagram.com") + "/v23.0/"

def call(method, path, params):
    params = {**params, "access_token": TOKEN}
    url, data = BASE + path, None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method), timeout=90) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")

def wait(cid):
    for _ in range(60):
        r = call("GET", cid, {"fields": "status_code,status"})
        if r.get("status_code") in ("FINISHED", "ERROR", "EXPIRED"):
            return r
        time.sleep(5)
    return r

kids = []
for i in (1, 2, 3):
    url = f"https://raw.githubusercontent.com/{REPO}/{SHA}/media/2026-W46/2026-W46-onsdag-1900-karrusel/slide-0{i}.mp4"
    r = call("POST", f"{IG}/media", {"media_type": "VIDEO", "video_url": url, "is_carousel_item": "true"})
    print("barn", i, json.dumps(r)[:300], flush=True)
    if r.get("id"):
        print("   status", json.dumps(wait(r["id"]))[:300], flush=True)
        kids.append(r["id"])
r = call("POST", f"{IG}/media", {"media_type": "CAROUSEL", "children": ",".join(kids), "caption": "test"})
print("KARRUSEL", json.dumps(r)[:300])
if r.get("id"):
    print("KARRUSEL status", json.dumps(wait(r["id"]))[:300])
