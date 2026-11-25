#!/usr/bin/env python3
"""Sender testen som besked til dem, der kommenterer TEST (eller ARKETYPE) på et opslag.

Brug: python3 pipeline/comments.py [--dry-run]
Kører i GitHub Actions hvert kvarter. Uden IG_ACCESS_TOKEN gør den ingenting.

Hvorfor: vejen opslag, profil, link i bio, test taber de fleste undervejs. En kommentar, der
udløser en besked med linket, springer profilen over, og kommentarerne giver samtidig opslaget
mere rækkevidde.

Sådan virker det:
  - Henter de nyeste opslag og deres kommentarer.
  - En kommentar med ordet ARKETYPE får linket til arketypetesten. En kommentar med TEST, TESTEN
    eller LINK får det link, opslaget peger på (feltet "dm" i køen: "studievalg" eller "arketype").
  - Svarer med én besked (Metas "private reply", kun muligt inden for 7 dage) og et kort offentligt
    svar under kommentaren, så andre kan se, at det virker.

Sikkerhedsnet:
  - Samme kontospærre som udgivelsen: kun @ikigaiguiden, aldrig den private profil.
  - PAUSE i roden stopper også beskederne.
  - Hver kommentar får højst én besked. Den markeres, før beskeden sendes, så en afbrudt kørsel
    hellere springer én over end sender to.
  - Status i state/dm.json gemmer kun en hash af kommentarens id. Repoet er offentligt, så ingen
    brugernavne eller kommentartekster gemmes.
  - Mangler nøglen tilladelserne, skrives det i state/dm.json og loggen, og kørslen ender grønt,
    så der ikke kommer en fejlmail hvert kvarter.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from publish import Api, ApiError, FORBIDDEN_ACCOUNTS, STATE_PATH  # noqa: E402

DM_STATE = common.DATA / "state" / "dm.json"
SITE = "https://ikigaiguide.dk"
LINKS = {"studievalg": f"{SITE}/dm", "arketype": f"{SITE}/dm/arketype"}
MESSAGES = {
    "studievalg": ("Hej! Her er testen, du bad om:\n{link}\n\n"
                   "Den er gratis, du skal ikke logge ind, og du får dit resultat med det samme."),
    "arketype": ("Hej! Her er arketypetesten:\n{link}\n\n"
                 "Den er gratis, du skal ikke logge ind, og du ser din arketype med det samme."),
}
PUBLIC_REPLIES = ["Sendt til dig i en besked 📩", "Tjek din indbakke 📩", "Du har fået linket i en besked 📩"]
ARKETYPE_WORD = re.compile(r"\barketype[nr]?\b", re.I)
TEST_WORD = re.compile(r"\b(test|testen|link|linket)\b", re.I)
if common.PROFILE == "en":
    # @the_ikigai_guide: alt peger på den engelske arketypetest.
    _EN = f"{SITE}/en/dm"
    LINKS = {"studievalg": _EN, "arketype": _EN}
    _MSG = ("Hi! Here's the archetype test:\n{link}\n\n"
            "It's free, no login, and you see your archetype right away.")
    MESSAGES = {"studievalg": _MSG, "arketype": _MSG}
    PUBLIC_REPLIES = ["Sent it to your DMs 📩", "Check your inbox 📩", "Link is in your DMs 📩"]
    ARKETYPE_WORD = re.compile(r"\barchetypes?\b", re.I)
    TEST_WORD = re.compile(r"\b(test|link|quiz)\b", re.I)
MAX_COMMENT_CHARS = 80
MAX_PER_RUN = 25
MEDIA_DAYS = 14
REPLY_DAYS = 7          # Meta tillader kun private replies inden for 7 dage
KEEP_DAYS = 45
PERMISSION_CODES = {3, 10, 200, 230}


def log(msg):
    print(msg, flush=True)


def comment_key(comment_id):
    return hashlib.sha256(str(comment_id).encode()).hexdigest()[:20]


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


def wanted_link(text, post_dm):
    """Hvilket link en kommentar skal have, eller None hvis den ikke beder om testen."""
    text = (text or "").strip()
    if not text or len(text) > MAX_COMMENT_CHARS:
        return None
    if ARKETYPE_WORD.search(text):
        return "arketype"
    if TEST_WORD.search(text):
        return post_dm if post_dm in LINKS else "studievalg"
    return None


def post_dm_map():
    """media_id -> feltet "dm" fra køen (studievalg som standard)."""
    published = common.read_json(STATE_PATH).get("posts", {}) if STATE_PATH.exists() else {}
    items = {i.get("id"): i for i in common.queue_items()}
    out = {}
    for pid, st in published.items():
        if st.get("media_id"):
            out[str(st["media_id"])] = (items.get(pid) or {}).get("dm", "studievalg")
    return out


def load_state():
    if DM_STATE.exists():
        s = common.read_json(DM_STATE)
    else:
        s = {}
    s.setdefault("kommentarer", {})
    s.setdefault("sendt_i_alt", 0)
    return s


def prune(state, now):
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat(timespec="minutes")
    state["kommentarer"] = {k: v for k, v in state["kommentarer"].items() if (v.get("tid") or "") >= cutoff}


def is_permission_error(e):
    msg = str(e).lower()
    return e.code in PERMISSION_CODES or "permission" in msg or "not authorized" in msg


def run(api, uid, own_username, now, dry):
    state = load_state()
    prune(state, now)
    dm_by_media = post_dm_map()
    media = api.get(f"{uid}/media", limit=25, fields="id,timestamp,comments_count").get("data", [])
    sent = skipped = 0
    errors = []
    for m in media:
        ts = parse_ts(m.get("timestamp"))
        if not m.get("comments_count") or (ts and ts < now - timedelta(days=MEDIA_DAYS)):
            continue
        comments = api.get(f"{m['id']}/comments", limit=50, fields="id,text,timestamp,username").get("data", [])
        for c in comments:
            key = comment_key(c["id"])
            if key in state["kommentarer"]:
                continue
            if (c.get("username") or "").lower() == own_username:
                continue
            link = wanted_link(c.get("text"), dm_by_media.get(str(m["id"]), "studievalg"))
            if not link:
                continue
            cts = parse_ts(c.get("timestamp"))
            if cts and cts < now - timedelta(days=REPLY_DAYS):
                state["kommentarer"][key] = {"tid": now.isoformat(timespec="minutes"), "status": "for_gammel"}
                skipped += 1
                continue
            if sent >= MAX_PER_RUN:
                break
            if dry:
                log(f"(tørkørsel) ville sende {link}-linket som svar på en kommentar på {m['id']}")
                sent += 1
                continue
            entry = {"tid": now.isoformat(timespec="minutes"), "status": "sender", "link": link, "opslag": str(m["id"])}
            state["kommentarer"][key] = entry
            common.write_json(DM_STATE, state)
            try:
                api.post(f"{uid}/messages", retries=0,
                         recipient=json.dumps({"comment_id": c["id"]}),
                         message=json.dumps({"text": MESSAGES[link].format(link=LINKS[link])}, ensure_ascii=False))
            except ApiError as e:
                if is_permission_error(e):
                    del state["kommentarer"][key]
                    raise
                entry["status"] = "fejl"
                errors.append(str(e)[:200])
                common.write_json(DM_STATE, state)
                continue
            entry["status"] = "sendt"
            state["sendt_i_alt"] = state.get("sendt_i_alt", 0) + 1
            sent += 1
            try:
                api.post(f"{c['id']}/replies", retries=0,
                         message=PUBLIC_REPLIES[state["sendt_i_alt"] % len(PUBLIC_REPLIES)])
            except ApiError as e:
                entry["offentligt_svar"] = "fejl"
                errors.append(f"offentligt svar: {str(e)[:150]}")
            common.write_json(DM_STATE, state)
    return state, sent, skipped, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--api-base", default=None)
    ap.add_argument("--now", default=None)
    args = ap.parse_args()

    if (common.ROOT / "PAUSE").exists() or (common.DATA / "PAUSE").exists():
        log("PAUSE findes. Der sendes ingen beskeder.")
        return 0
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        log("IG_ACCESS_TOKEN er ikke sat. Der sendes ingen beskeder.")
        return 0
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    cfg = common.read_json(common.DATA / "config.json")
    expected_id = str(cfg.get("instagram_user_id", "")).strip()
    fb_token = token.startswith("EAA")
    base = args.api_base or ("https://graph.facebook.com" if fb_token else "https://graph.instagram.com")
    api = Api(base, os.environ.get("IG_API_VERSION", "v23.0"), token, expected_id if fb_token else None)
    try:
        uid = api.user_id()
    except ApiError as e:
        log(f"Kunne ikke slå kontoen op: {e}")
        return 1
    expected = str(cfg.get("instagram_username", "")).lower().lstrip("@")
    actual = str(api.username or "").lower().lstrip("@")
    if actual != expected or actual in FORBIDDEN_ACCOUNTS or (expected_id and uid != expected_id):
        log(f"KONTOSPÆRRE: nøglen hører til @{actual or '?'}, ikke @{expected}. Der sendes intet.")
        return 1

    try:
        state, sent, skipped, errors = run(api, uid, actual, now, args.dry_run)
    except ApiError as e:
        if not is_permission_error(e):
            log(f"Fejl fra Instagram: {e}")
            return 1
        state = load_state()
        changed = state.get("status") != "mangler_tilladelse"
        state["status"] = "mangler_tilladelse"
        state["besked"] = ("Nøglen mangler instagram_business_manage_comments og/eller "
                           "instagram_business_manage_messages, eller beskedadgang er slået fra i appen.")
        if changed and not args.dry_run:
            state["siden"] = now.isoformat(timespec="minutes")
            common.write_json(DM_STATE, state)
        log(f"Beskeder er ikke tændt endnu: {state['besked']} ({e})")
        return 0

    if args.dry_run:
        log(f"Tørkørsel: {sent} beskeder ville blive sendt.")
        return 0
    # Skriv kun, når noget har ændret sig, så der ikke kommer et commit hvert kvarter.
    if sent or skipped or errors or state.get("status") != "aktiv":
        if state.get("status") != "aktiv":
            state["siden"] = now.isoformat(timespec="minutes")
        state["status"] = "aktiv"
        state.pop("besked", None)
        if errors:
            state["seneste_fejl"] = errors[-5:]
        common.write_json(DM_STATE, state)
    log(f"Sendte {sent} beskeder." + (f" {skipped} kommentarer var for gamle." if skipped else "")
        + (f" {len(errors)} fejl, se state/dm.json." if errors else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
