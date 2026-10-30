#!/usr/bin/env python3
"""Udgiver forfaldne opslag fra queue/ til Instagram (Instagram API with Instagram Login).

Kører i GitHub Actions hver halve time. Uden IG_ACCESS_TOKEN gør den ingenting.

Sikkerhedsnet:
  - PAUSE: findes filen PAUSE i roden, udgives intet.
  - Kvalitetsporten (lint.py) skal bestå, ellers udgives opslaget ikke.
  - Opslag, der er mere end --max-late-hours forsinket, springes over i stedet for at blive postet gammelt.
  - Hvert opslag udgives højst én gang. Status gemmes efter hvert trin, så en afbrudt kørsel genoptages
    uden at lave dubletter.
  - Adgangsnøglen skrives aldrig til loggen.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import lint  # noqa: E402

STATE_PATH = common.ROOT / "state" / "published.json"


class ApiError(Exception):
    def __init__(self, message, http=None, code=None, sub=None):
        super().__init__(message)
        self.http, self.code, self.sub = http, code, sub


def log(msg):
    print(msg, flush=True)


# ---------- Instagram API ----------

class Api:
    def __init__(self, base, version, token):
        self.base = f"{base.rstrip('/')}/{version}"
        self.token = token
        self._uid = None
        self.username = None

    def _scrub(self, text):
        return str(text).replace(self.token, "***") if self.token else str(text)

    def _call(self, method, path, params, retries):
        url = f"{self.base}/{path.lstrip('/')}"
        p = {k: v for k, v in params.items() if v is not None}
        p["access_token"] = self.token
        body = urllib.parse.urlencode(p)
        for attempt in range(retries + 1):
            try:
                if method == "GET":
                    req = urllib.request.Request(f"{url}?{body}")
                else:
                    req = urllib.request.Request(url, data=body.encode(), method="POST")
                with urllib.request.urlopen(req, timeout=90) as r:
                    return json.loads(r.read().decode() or "{}")
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                try:
                    err = json.loads(raw).get("error", {})
                except ValueError:
                    err = {"message": raw[:200]}
                if e.code >= 500 and attempt < retries:
                    time.sleep(3 * 2 ** attempt)
                    continue
                raise ApiError(self._scrub(err.get("message", raw[:200])), http=e.code,
                               code=err.get("code"), sub=err.get("error_subcode"))
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < retries:
                    time.sleep(3 * 2 ** attempt)
                    continue
                raise ApiError(f"Netfejl mod Instagram: {self._scrub(e)}")

    def get(self, path, **params):
        return self._call("GET", path, params, retries=2)

    def post(self, path, retries=2, **params):
        return self._call("POST", path, params, retries=retries)

    def user_id(self):
        if not self._uid:
            me = self.get("me", fields="user_id,username")
            self._uid = str(me.get("user_id") or me.get("id") or "")
            self.username = me.get("username")
            if not self._uid:
                raise ApiError("Instagram returnerede intet konto-id.")
        return self._uid


class DryApi:
    """Tørkørsel: skriver hvad der ville ske, uden at røre netværket."""

    username = "(tørkørsel)"

    def __init__(self):
        self.n = 0

    def user_id(self):
        return "DRY_USER"

    def post(self, path, retries=2, **params):
        self.n += 1
        shown = {k: (v if len(str(v)) < 90 else str(v)[:87] + "...") for k, v in params.items() if v is not None}
        log(f"  [tørkørsel] POST {path} {json.dumps(shown, ensure_ascii=False)}")
        return {"id": f"DRY_{self.n}"}

    def get(self, path, **params):
        if path.startswith("DRY_") and "permalink" in params.get("fields", ""):
            return {"permalink": "https://www.instagram.com/p/DRY/"}
        return {"status_code": "FINISHED"}


def wait_ready(api, container_id, timeout, interval):
    end = time.time() + timeout
    while True:
        r = api.get(container_id, fields="status_code,status")
        s = r.get("status_code")
        if s == "FINISHED":
            return
        if s in ("ERROR", "EXPIRED"):
            raise ApiError(f"Instagram afviste mediet (status {s}: {r.get('status', 'ingen detaljer')}).")
        if time.time() > end:
            raise ApiError("Instagram blev ikke færdig med at behandle mediet i tide.")
        time.sleep(interval)


# ---------- offentlige adresser til medier ----------

def url_candidates(rel, args):
    if args.public_base:
        return [f"{args.public_base.rstrip('/')}/{rel}"]
    repo, sha = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_SHA")
    if not (repo and sha):
        raise ApiError("GITHUB_REPOSITORY/GITHUB_SHA mangler, så medie-adresser kan ikke dannes.")
    return [f"https://raw.githubusercontent.com/{repo}/{sha}/media/{rel}",
            f"https://cdn.jsdelivr.net/gh/{repo}@{sha}/media/{rel}"]


def resolve_url(rel, kind, args):
    """Første adresse, der rent faktisk leverer den rigtige filtype. Instagram henter selv filen."""
    want = "image/jpeg" if kind == "image" else "video/"
    problems = []
    cands = url_candidates(rel, args)
    if args.dry_run:
        return cands[0]
    for url in cands:
        try:
            req = urllib.request.Request(url, headers={"Range": "bytes=0-1023"})
            with urllib.request.urlopen(req, timeout=30) as r:
                ctype = r.headers.get("Content-Type", "")
                if r.status in (200, 206) and ctype.startswith(want):
                    return url
                problems.append(f"{url} gav {r.status} {ctype}")
        except (urllib.error.URLError, TimeoutError) as e:
            problems.append(f"{url} kunne ikke hentes ({e})")
    raise ApiError("Mediet er ikke offentligt tilgængeligt endnu: " + "; ".join(problems))


# ---------- opslag ----------

def item_hash(item):
    return hashlib.sha1(json.dumps(common.clean(item), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def alt_text(slide):
    return common.strip_marks(" ".join(slide["h"] + slide.get("sub", [])))[:1000]


def validate(item):
    probs = lint.check(item)
    mdir = common.media_dir(item)
    rel_dir = f"{item['_path'].parent.name}/{item['id']}"
    if item["type"] == "carousel":
        for i in range(1, len(item.get("slides", [])) + 1):
            if not (mdir / f"slide-{i:02d}.jpg").exists():
                probs.append(f"media/{rel_dir}/slide-{i:02d}.jpg mangler (kør build.py).")
    elif not (mdir / "reel.mp4").exists():
        probs.append(f"media/{rel_dir}/reel.mp4 mangler (kør build.py).")
    return probs


def create_container(api, uid, item, args):
    rel_dir = f"{item['_path'].parent.name}/{item['id']}"
    if item["type"] == "reel":
        url = resolve_url(f"{rel_dir}/reel.mp4", "video", args)
        r = api.post(f"{uid}/media", media_type="REELS", video_url=url, caption=item["caption"],
                     share_to_feed="true")
        return r["id"]
    children = []
    for i, slide in enumerate(item["slides"], 1):
        url = resolve_url(f"{rel_dir}/slide-{i:02d}.jpg", "image", args)
        try:
            r = api.post(f"{uid}/media", image_url=url, is_carousel_item="true", alt_text=alt_text(slide))
        except ApiError as e:
            if e.code != 100:
                raise
            r = api.post(f"{uid}/media", image_url=url, is_carousel_item="true")  # uden alt-tekst
        wait_ready(api, r["id"], args.timeout, args.poll)
        children.append(r["id"])
    r = api.post(f"{uid}/media", media_type="CAROUSEL", children=",".join(children), caption=item["caption"])
    return r["id"]


def publish_item(api, item, state, args, save):
    pid = item["id"]
    st = state["posts"].setdefault(pid, {})
    st["hash"] = item_hash(item)
    uid = api.user_id()
    log(f"  konto: @{api.username}")

    cid = st.get("creation_id")
    if cid and st.get("status") == "container":
        try:
            code = api.get(cid, fields="status_code").get("status_code")
        except ApiError:
            code = "ERROR"
        if code in ("ERROR", "EXPIRED"):
            log("  tidligere container er ugyldig, laver en ny")
            cid = None
        else:
            log(f"  genoptager container {cid}")
    if not cid:
        cid = create_container(api, uid, item, args)
        st.update(status="container", creation_id=cid)
        save()
    wait_ready(api, cid, args.timeout, args.poll)
    media_id = api.post(f"{uid}/media_publish", retries=0, creation_id=cid)["id"]
    try:
        permalink = api.get(media_id, fields="permalink").get("permalink")
    except ApiError:
        permalink = None
    st.update(status="published", media_id=media_id, permalink=permalink,
              at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    st.pop("creation_id", None)
    save()
    log(f"  UDGIVET {pid} {permalink or media_id}")


# ---------- status ----------

def load_state():
    if STATE_PATH.exists():
        return common.read_json(STATE_PATH)
    return {"posts": {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="vis hvad der ville ske, uden at udgive")
    ap.add_argument("--now", help="ISO-tidspunkt at regne fra (til test)")
    ap.add_argument("--only", help="udgiv kun dette opslag-id")
    ap.add_argument("--api-base", default="https://graph.instagram.com")
    ap.add_argument("--api-version", default=os.environ.get("IG_API_VERSION", "v23.0"))
    ap.add_argument("--public-base", help="fast base-adresse til medier (til test)")
    ap.add_argument("--max-late-hours", type=float, default=18.0)
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--poll", type=float, default=10)
    args = ap.parse_args()

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    state = load_state()

    def save():
        if not args.dry_run:
            common.write_json(STATE_PATH, state)

    due, marked = [], False
    for item in common.queue_items():
        if args.only and item.get("id") != args.only:
            continue
        pid = item.get("id", item["_path"].name)
        st = state["posts"].get(pid, {})
        if st.get("status") in ("published", "skipped_stale"):
            continue
        try:
            when = common.parse_when(item["publish_at"])
        except (KeyError, ValueError) as e:
            log(f"FEJL {pid}: {e}")
            continue
        if now < when:
            continue
        late = now - when
        if late > timedelta(hours=args.max_late_hours) and st.get("status") != "container":
            log(f"springer {pid} over: {late} for sent")
            state["posts"][pid] = {"status": "skipped_stale", "at": now.isoformat(timespec="seconds"),
                                   "reason": f"{late} forsinket"}
            marked = True
            continue
        if st.get("status") in ("blocked", "failed") and st.get("hash") == item_hash(item):
            continue
        due.append(item)
    if marked:
        save()

    if (common.ROOT / "PAUSE").exists():
        log("PAUSE-filen findes: der udgives ingenting.")
        return 0
    if not due:
        log("Intet at udgive lige nu.")
        return 0
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token and not args.dry_run:
        log("IG_ACCESS_TOKEN er ikke sat. Autopiloten er ikke tændt endnu.")
        return 0

    api = DryApi() if args.dry_run else Api(args.api_base, args.api_version, token)
    errors = 0
    for item in due:
        pid = item["id"]
        log(f"Udgiver {pid} ({item['type']}, planlagt {item['publish_at']})")
        probs = validate(item)
        if probs:
            errors += 1
            log("  Spærret af kvalitetsporten:")
            for x in probs:
                log(f"    {x}")
            state["posts"][pid] = {"status": "blocked", "hash": item_hash(item), "problems": probs}
            save()
            continue
        try:
            publish_item(api, item, state, args, save)
        except ApiError as e:
            errors += 1
            st = state["posts"].setdefault(pid, {})
            st["attempts"] = st.get("attempts", 0) + 1
            st["last_error"] = str(e)[:300]
            if st["attempts"] >= 3:
                st["status"] = "failed"
            save()
            if e.code == 190 or e.http == 401:
                log("  FEJL: Adgangsnøglen er udløbet eller afvist. Generér en ny hos Meta og opdatér secret IG_ACCESS_TOKEN.")
            log(f"  FEJL: {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
