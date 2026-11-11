#!/usr/bin/env python3
"""Sender forfaldne karruseller fra queue/ til TikTok som fotokarruseller.

TikToks eget API lader kun godkendte apps poste offentligt, og et værktøj til egne konti
kan ikke blive godkendt. Derfor går udgivelsen gennem Zernio (gratis for de første to
konti), som har en godkendt TikTok-app. Uden ZERNIO_API_KEY gør scriptet ingenting.

To måder at udgive på (config.json "tiktok_mode", eller feltet "tiktok" i et opslag):
  auto    opslaget udgives med det samme, og TikTok lægger selv et anbefalet nummer på.
  kladde  opslaget lander i TikTok-indbakken. Du vælger selv lyd og trykker udgiv.
Feltet "tiktok": false i et opslag holder det helt væk fra TikTok.

Sikkerhedsnet:
  - PAUSE: findes filen PAUSE i roden, sendes intet.
  - Kontospærre: der sendes kun til den TikTok-konto, der står i config.json ("tiktok_username").
  - Kvalitetsporten (lint.py) skal bestå.
  - Opslag, der er mere end --max-late-hours forsinket, sendes ikke.
  - Hvert opslag sendes højst én gang. Zernio får en fast Idempotency-Key pr. opslag,
    så et genforsøg efter en netfejl ikke kan give en dublet.
  - Nøglen skrives aldrig til loggen.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import publish  # noqa: E402
from publish import ApiError, log  # noqa: E402

STATE_PATH = common.ROOT / "state" / "tiktok.json"
DEFAULT_BASE = "https://zernio.com/api/v1"
MODES = ("auto", "kladde")
TITLE_MAX = 90          # TikToks grænse for titlen på et fotoopslag
DESCRIPTION_MAX = 4000  # TikToks grænse for teksten under et fotoopslag
MAX_PHOTOS = 35


class Zernio:
    def __init__(self, base, key):
        self.base = base.rstrip("/")
        self.key = key

    def _scrub(self, text):
        return str(text).replace(self.key, "***") if self.key else str(text)

    def call(self, method, path, body=None, params=None, headers=None, retries=2):
        url = f"{self.base}/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        hdr = {"Authorization": f"Bearer {self.key}", "Accept": "application/json", **(headers or {})}
        if data is not None:
            hdr["Content-Type"] = "application/json"
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, data=data, method=method, headers=hdr)
                with urllib.request.urlopen(req, timeout=180) as r:
                    return r.status, json.loads(r.read().decode() or "{}")
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                try:
                    obj = json.loads(raw)
                except ValueError:
                    obj = {}
                if e.code == 409 and isinstance(obj, dict) and obj.get("existingPostId"):
                    return 409, obj
                if (e.code >= 500 or e.code == 429) and attempt < retries:
                    time.sleep(3 * 2 ** attempt)
                    continue
                msg = obj.get("error") or obj.get("message") if isinstance(obj, dict) else None
                if isinstance(msg, dict):
                    msg = msg.get("message") or json.dumps(msg, ensure_ascii=False)
                raise ApiError(self._scrub(msg or raw[:300] or f"HTTP {e.code}"), http=e.code)
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < retries:
                    time.sleep(3 * 2 ** attempt)
                    continue
                raise ApiError(f"Netfejl mod Zernio: {self._scrub(e)}")


# ---------- tekst ----------

def title_of(caption):
    """Titlen på fotoopslaget: første linje uden hashtags, højst 90 tegn, klippet ved et ordskel."""
    first = caption.strip().split("\n")[0]
    first = re.sub(r"(?<!\w)#\w+", "", first)
    first = re.sub(r"\s+", " ", first).strip()
    if len(first) <= TITLE_MAX:
        return first
    # Helst hele sætninger: klip efter det sidste punktum, der kan være der.
    ends = [m.end() for m in re.finditer(r"[.!?](?= )", first[:TITLE_MAX + 1])]
    if ends and ends[-1] >= 20:
        return first[:ends[-1]]
    cut = first[:TITLE_MAX + 1]
    cut = cut[:cut.rfind(" ")] if " " in cut else first[:TITLE_MAX]
    return cut.rstrip(" ,;:")


def mode_of(item, cfg):
    """Returnerer 'auto', 'kladde' eller None (opslaget skal ikke på TikTok)."""
    v = item.get("tiktok")
    if v is False:
        return None
    mode = v if isinstance(v, str) else cfg.get("tiktok_mode", "auto")
    if mode not in MODES:
        raise ApiError(f"Ukendt TikTok-måde '{mode}' (skal være auto eller kladde).")
    return mode


# ---------- konto ----------

def _acc_id(a):
    return str(a.get("_id") or a.get("id") or a.get("accountId") or "")


def _acc_name(a):
    return str(a.get("username") or a.get("handle") or a.get("displayName") or "").lower().lstrip("@")


def find_account(api, cfg):
    """Finder den ene TikTok-konto, der må sendes til. Returnerer (id, brugernavn) eller kaster ApiError."""
    expected = str(cfg.get("tiktok_username", "")).lower().lstrip("@")
    _, res = api.call("GET", "accounts", params={"platform": "tiktok"})
    accounts = res.get("accounts", res) if isinstance(res, dict) else res
    tik = [a for a in (accounts or []) if isinstance(a, dict) and str(a.get("platform", "tiktok")).lower() == "tiktok"]
    names = ", ".join("@" + (_acc_name(a) or "?") for a in tik) or "ingen"
    if not expected:
        raise ApiError(f"KONTOSPÆRRE: 'tiktok_username' mangler i config.json. Tilsluttede TikTok-konti hos Zernio: {names}.")
    if expected in publish.FORBIDDEN_ACCOUNTS:
        raise ApiError(f"KONTOSPÆRRE: @{expected} er spærret og må aldrig bruges af autopiloten.")
    for a in tik:
        if _acc_name(a) == expected and _acc_id(a):
            return _acc_id(a), _acc_name(a)
    raise ApiError(f"KONTOSPÆRRE: autopiloten må kun sende til @{expected}, men Zernio har: {names}. Intet sendt.")


def public_level(api, account_id):
    """Tjekker at kontoen kan poste offentligt lige nu. Kaster ApiError, hvis den ikke kan."""
    try:
        _, info = api.call("GET", f"accounts/{account_id}/tiktok/creator-info", params={"mediaType": "photo"})
    except ApiError as e:
        if e.http == 429:
            raise ApiError("TikTok siger, at kontoen har nået dagens grænse for opslag.", http=429)
        log(f"  kunne ikke hente kontoens indstillinger ({e}); prøver med offentligt opslag")
        return "PUBLIC_TO_EVERYONE"
    levels = [(x.get("value") if isinstance(x, dict) else x) for x in info.get("privacyLevels", [])]
    if levels and "PUBLIC_TO_EVERYONE" not in levels:
        raise ApiError("TikTok-kontoen kan ikke poste offentligt (er den sat til privat?). Tilladt: " + ", ".join(map(str, levels)))
    return "PUBLIC_TO_EVERYONE"


# ---------- afsendelse ----------

def build_body(item, urls, account_id, mode, privacy):
    settings = {
        "media_type": "photo",
        "photo_cover_index": 0,
        "description": item["caption"][:DESCRIPTION_MAX],
        "allow_comment": True,
        "content_preview_confirmed": True,
        "express_consent_given": True,
    }
    if mode == "kladde":
        settings["draft"] = True
    else:
        settings["privacy_level"] = privacy
        settings["auto_add_music"] = True
    return {
        "content": title_of(item["caption"]),
        "mediaItems": [{"type": "image", "url": u} for u in urls],
        "platforms": [{"platform": "tiktok", "accountId": account_id}],
        "tiktokSettings": settings,
        "publishNow": True,
    }


def read_result(res):
    """Trækker (post-id, status, fejl, adresse) ud af Zernios svar."""
    post = res.get("post", res) if isinstance(res, dict) else {}
    plats = [p for p in post.get("platforms", []) if isinstance(p, dict) and p.get("platform") == "tiktok"]
    p = plats[0] if plats else {}
    return (str(post.get("_id") or post.get("id") or ""), str(p.get("status") or post.get("status") or ""),
            p.get("errorMessage") or post.get("errorMessage"), p.get("platformPostUrl"))


def send_item(api, item, st, account_id, mode, args):
    rel_dir = f"{item['_path'].parent.name}/{item['id']}"
    n = len(item["slides"])
    if n > MAX_PHOTOS:
        raise ApiError(f"TikTok tillader højst {MAX_PHOTOS} billeder, opslaget har {n}.")
    urls = [publish.resolve_url(f"{rel_dir}/slide-{i:02d}.jpg", "image", args) for i in range(1, n + 1)]
    privacy = None if (mode == "kladde" or args.dry_run) else public_level(api, account_id)
    body = build_body(item, urls, account_id, mode, privacy or "PUBLIC_TO_EVERYONE")
    if args.dry_run:
        log(f"  [tørkørsel] POST posts: {len(urls)} billeder, titel: {body['content']}")
        log("  [tørkørsel] tiktokSettings " + json.dumps({k: v for k, v in body["tiktokSettings"].items() if k != "description"}))
        return
    key = f"ikiguiden-tiktok-{item['id']}-{st['hash'][:10]}"
    code, res = api.call("POST", "posts", body=body, headers={"Idempotency-Key": key})
    if code == 409:
        st.update(status="sent", post_id=str(res.get("existingPostId")), mode=mode)
        log(f"  Zernio havde allerede opslaget ({st['post_id']}); sender det ikke igen")
        return
    post_id, status, err, url = read_result(res)
    st.update(post_id=post_id, mode=mode, at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    if status == "failed" or (code == 207 and err):
        # Et genforsøg med samme nøgle ville bare få det samme afviste opslag igen. Stop her, så fejlen ses.
        st["status"] = "failed"
        raise ApiError(f"TikTok afviste opslaget: {err or 'ingen detaljer'}")
    if mode == "kladde":
        st["status"] = "draft"
        log(f"  KLADDE SENDT {item['id']}: åbn TikTok-indbakken, vælg lyd og udgiv")
    elif status == "published":
        st["status"] = "published"
        if url:
            st["url"] = url
        log(f"  UDGIVET PÅ TIKTOK {item['id']} {url or post_id}")
    else:
        st["status"] = "sent"
        log(f"  SENDT TIL TIKTOK {item['id']} (status {status or 'ukendt'}); tjekkes igen ved næste kørsel")


def follow_up(api, state, now, save):
    """Opslag, der var undervejs sidst: hent den endelige status. Returnerer antal fejlede."""
    failed = 0
    for pid, st in state["posts"].items():
        if st.get("status") != "sent" or not st.get("post_id"):
            continue
        try:
            sent_at = datetime.fromisoformat(st.get("at", ""))
        except ValueError:
            sent_at = now
        try:
            _, res = api.call("GET", f"posts/{st['post_id']}")
        except ApiError as e:
            log(f"  kunne ikke tjekke {pid} hos Zernio ({e})")
            continue
        _, status, err, url = read_result(res)
        if status == "published":
            st["status"] = "published"
            if url:
                st["url"] = url
            log(f"  bekræftet udgivet på TikTok: {pid} {url or ''}".rstrip())
        elif status == "failed":
            st.update(status="failed", last_error=str(err or "ingen detaljer")[:300])
            failed += 1
            log(f"  FEJL: TikTok afviste {pid}: {st['last_error']}")
        elif now - sent_at > timedelta(hours=24):
            st.update(status="failed", last_error=f"stadig '{status}' efter 24 timer")
            failed += 1
            log(f"  FEJL: {pid} blev aldrig færdig hos TikTok")
        else:
            continue
        save()
    return failed


def load_state():
    if STATE_PATH.exists():
        return common.read_json(STATE_PATH)
    return {"posts": {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="vis hvad der ville ske, uden at sende")
    ap.add_argument("--now", help="ISO-tidspunkt at regne fra (til test)")
    ap.add_argument("--check-account", action="store_true", help="kun kontrol af nøgle og konto, sender intet")
    ap.add_argument("--only", help="send kun dette opslag-id")
    ap.add_argument("--api-base", default=os.environ.get("ZERNIO_API_BASE", DEFAULT_BASE))
    ap.add_argument("--public-base", help="fast base-adresse til medier (til test)")
    ap.add_argument("--max-late-hours", type=float, default=18.0)
    args = ap.parse_args()

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cfg = common.read_json(common.ROOT / "config.json")
    state = load_state()

    def save():
        if not args.dry_run:
            common.write_json(STATE_PATH, state)

    due = []
    for item in common.queue_items():
        if item.get("type") != "carousel" or (args.only and item.get("id") != args.only):
            continue
        pid = item.get("id", item["_path"].name)
        st = state["posts"].get(pid, {})
        if st.get("status") in ("published", "draft", "sent"):
            continue
        try:
            when = common.parse_when(item["publish_at"])
            mode = mode_of(item, cfg)
        except (KeyError, ValueError, ApiError) as e:
            log(f"FEJL {pid}: {e}")
            continue
        if mode is None or now < when or now - when > timedelta(hours=args.max_late_hours):
            continue
        if st.get("status") in ("blocked", "failed") and st.get("hash") == publish.item_hash(item):
            continue
        due.append((item, mode))

    if (common.ROOT / "PAUSE").exists():
        log("PAUSE-filen findes: der sendes ingenting til TikTok.")
        return 0
    key = os.environ.get("ZERNIO_API_KEY", "").strip()
    if not key and not args.dry_run:
        log("ZERNIO_API_KEY er ikke sat. TikTok er ikke tændt endnu.")
        return 0
    pending = any(s.get("status") == "sent" for s in state["posts"].values())
    if not due and not pending and not args.check_account:
        log("Intet at sende til TikTok lige nu.")
        return 0

    api = Zernio(args.api_base, key)
    account_id, username = "DRY_ACCOUNT", "(tørkørsel)"
    if not args.dry_run:
        try:
            account_id, username = find_account(api, cfg)
        except ApiError as e:
            if e.http == 401:
                log("FEJL: Zernio afviste nøglen. Lav en ny hos Zernio og opdatér secret ZERNIO_API_KEY.")
            log(f"{e}")
            return 1
    if args.check_account:
        log(f"TIKTOK-KONTO OK: Zernio er tilsluttet @{username}. Der er sendt intet.")
        return 0

    errors = 0 if args.dry_run else follow_up(api, state, now, save)
    for item, mode in due:
        pid = item["id"]
        log(f"Sender {pid} til TikTok @{username} ({mode}, planlagt {item['publish_at']})")
        probs = publish.validate(item)
        if probs:
            errors += 1
            log("  Spærret af kvalitetsporten:")
            for x in probs:
                log(f"    {x}")
            state["posts"][pid] = {"status": "blocked", "hash": publish.item_hash(item), "problems": probs}
            save()
            continue
        st = state["posts"].setdefault(pid, {})
        st["hash"] = publish.item_hash(item)
        try:
            send_item(api, item, st, account_id, mode, args)
            st.pop("last_error", None)
            save()
        except ApiError as e:
            errors += 1
            st["attempts"] = st.get("attempts", 0) + 1
            st["last_error"] = str(e)[:300]
            if st["attempts"] >= 3:
                st["status"] = "failed"
            save()
            log(f"  FEJL: {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
