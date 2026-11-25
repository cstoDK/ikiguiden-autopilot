"""Henter tal for profilens opslag fra Instagram og skriver dem til results/.

Brug: python3 pipeline/insights.py
Kører dagligt i GitHub Actions. Udgiver og ændrer intet på Instagram, den læser kun.
Ugens generering læser results/OVERSIGT.md og bruger tallene til at vælge formater.

Kræver at nøglen har tilladelsen instagram_business_manage_insights. Mangler den, gemmes
stadig likes og kommentarer, og OVERSIGT.md siger, hvad der mangler.
"""
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from publish import Api, ApiError, FORBIDDEN_ACCOUNTS, STATE_PATH  # noqa: E402

RESULTS = common.DATA / "results"
DM_STATE = common.DATA / "state" / "dm.json"
UMAMI_BASE = "https://api.umami.is/v1"
UMAMI_GATEWAY = "https://gateway-eu.umami.is/api"   # bruges med et delingslink (gratis plan, ingen API-nøgle)
UMAMI_SITE = "c9dc8c7f-388d-4a1d-a6ce-8c56251b8df9"   # ikigaiguide.dk, se index.html i ikigai-guide
TEST_EVENTS = ["ikigai_start", "ikigai_faerdig", "arketype_start", "arketype_faerdig", "arketype_del"]
VINKEL_EVENT = {"studievalg": "ikigai_faerdig", "arketype": "arketype_faerdig"}
METRICS = ["views", "reach", "saved", "shares", "total_interactions"]
MAX_MEDIA = 200
PUBLIC_VIEWS = RESULTS / "visninger.json"   # offentlige afspilningstal for reels, aflæst fra profilen i en browser


def log(msg):
    print(msg, flush=True)


def metric_value(entry):
    if "total_value" in entry:
        return entry["total_value"].get("value")
    vals = entry.get("values") or []
    return vals[0].get("value") if vals else None


def fetch_insights(api, media_id):
    """Prøver alle tal på én gang, og ellers ét ad gangen, så ét afvist tal ikke tager resten med."""
    try:
        res = api.get(f"{media_id}/insights", metric=",".join(METRICS))
        return {e["name"]: metric_value(e) for e in res.get("data", [])}, None
    except ApiError as first:
        out, last = {}, str(first)
        for m in METRICS:
            try:
                res = api.get(f"{media_id}/insights", metric=m)
                for e in res.get("data", []):
                    out[e["name"]] = metric_value(e)
            except ApiError as e:
                last = str(e)
        return out, (None if out else last)


def queue_index():
    by_id = {}
    for item in common.queue_items():
        by_id[item.get("id")] = item
    return by_id


def describe(item):
    """Kort beskrivelse af et autopilot-opslag: format og tema."""
    if not item:
        return {"kilde": "manuel"}
    if item.get("format") == "klip":
        fmt = "klip"
    elif item.get("cards"):
        fmt = "tekstkort"
    elif item.get("format") == "linje":
        fmt = "linje"
    elif item.get("format") == "liste":
        fmt = "liste"
    else:
        fmt = "slides"
    return {"kilde": "autopilot", "id": item.get("id"), "format": fmt, "tema": "foto" if fmt == "klip" else item.get("tema", "lys"),
            "planlagt": item.get("publish_at"), "vinkel": item.get("dm")}


# ---------------- Gennemførte tests fra Umami (målingen på ikigaiguide.dk) ----------------

def umami_share_auth(share_id):
    """Adgang via et Umami-delingslink. API-nøgler kræver Umamis betalte plan, delingslinket gør ikke."""
    req = urllib.request.Request(f"{UMAMI_GATEWAY}/share/{share_id}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    return {"base": UMAMI_GATEWAY, "headers": {"x-umami-share-token": data["token"], "x-umami-share-context": "1",
                                                "Accept": "application/json"}}


def _umami_get(key, path, **params):
    if isinstance(key, dict):
        url = f"{key['base']}/{path.lstrip('/')}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=key["headers"]), timeout=60) as r:
            return json.loads(r.read().decode() or "null")
    # Kontoen ligger i Umamis EU-region. Prøv først den fælles adresse og derefter /eu, hvis den fejler.
    last = None
    for base in (UMAMI_BASE, UMAMI_BASE + "/eu"):
        url = f"{base}/{path.lstrip('/')}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"x-umami-api-key": key, "Authorization": f"Bearer {key}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise
            last = e
    raise last


def fetch_umami(key, now, site=UMAMI_SITE):
    """Antal hændelser pr. kilde for de seneste 7 dage og de 7 dage før. Læser kun."""
    periods = {"seneste_7": (now - timedelta(days=7), now), "forrige_7": (now - timedelta(days=14), now - timedelta(days=7))}
    out, errors = {}, []
    for name, (start, end) in periods.items():
        ms = {"startAt": int(start.timestamp() * 1000), "endAt": int(end.timestamp() * 1000)}
        per = {}
        try:
            totals = _umami_get(key, f"websites/{site}/metrics", type="event", **ms) or []
            for row in totals:
                if row.get("x") in TEST_EVENTS:
                    per.setdefault(row["x"], {})["i_alt"] = row.get("y", 0)
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            errors.append(f"Umami metrics: {str(e)[:150]}")
        for ev in TEST_EVENTS:
            try:
                vals = _umami_get(key, f"websites/{site}/event-data/values", event=ev, eventName=ev,
                                  propertyName="kilde", **ms) or []
                for row in vals:
                    per.setdefault(ev, {})[str(row.get("value"))] = row.get("total", 0)
            except (urllib.error.URLError, ValueError, TimeoutError) as e:
                errors.append(f"Umami {ev}: {str(e)[:150]}")
                break
        out[name] = per
    return out, sorted(set(errors))


def _instagram_count(per_event):
    return sum(v for k, v in (per_event or {}).items() if k.startswith("instagram"))


def umami_lines(umami):
    if not umami:
        return ["## Gennemførte tests", "",
                "Mangler: Umamis API kræver den betalte plan (UMAMI_API_KEY er ikke sat), så autopiloten kan ikke se, hvor mange der gennemfører testen. Christian har valgt ikke at betale for det nu.", ""]
    lines = ["## Gennemførte tests (Umami)", "",
             "| Hændelse | Fra Instagram, seneste 7 dage | Forrige 7 dage | Alle kilder, seneste 7 dage |",
             "| --- | --- | --- | --- |"]
    now_, prev = umami.get("seneste_7", {}), umami.get("forrige_7", {})
    for ev in TEST_EVENTS:
        cur = now_.get(ev, {})
        total = cur.get("i_alt", sum(v for k, v in cur.items() if k != "i_alt"))
        lines.append(f"| {ev} | {_instagram_count(cur)} | {_instagram_count(prev.get(ev))} | {total} |")
    return lines + [""]


def vinkel_lines(rows, umami, dm_state, now):
    """Tests pr. vinkel: beskeder sendt, gennemførte tests via besked-linket og visninger, seneste 7 dage."""
    since = (now - timedelta(days=7)).isoformat()
    sent = {}
    for v in (dm_state or {}).get("kommentarer", {}).values():
        if v.get("status") == "sendt" and (v.get("tid") or "") >= since[:16]:
            sent[v.get("link")] = sent.get(v.get("link"), 0) + 1
    lines = ["## Tests pr. vinkel (seneste 7 dage)", "",
             "| Vinkel | Opslag | Visninger | Beskeder sendt | Gennemført via besked | Pr. 1.000 visninger |",
             "| --- | --- | --- | --- | --- | --- |"]
    cur = (umami or {}).get("seneste_7", {})
    for vinkel, ev in VINKEL_EVENT.items():
        rs = [r for r in rows if r.get("vinkel") == vinkel and (r.get("tidspunkt") or "") >= since[:10]]
        views = sum(r.get("views") or 0 for r in rs)
        done = (cur.get(ev) or {}).get("instagram_dm", 0) if umami else None
        rate = round(1000 * done / views, 1) if (done is not None and views) else None
        lines.append(f"| {vinkel} | {len(rs)} | {views or ''} | {sent.get(vinkel, 0)} | "
                     f"{'' if done is None else done} | {'' if rate is None else rate} |")
    if (dm_state or {}).get("status") == "mangler_tilladelse":
        lines += ["", "Beskeder er ikke tændt: " + dm_state.get("besked", "")]
    return lines + [""]


def collect(api, uid):
    state = common.read_json(STATE_PATH).get("posts", {}) if STATE_PATH.exists() else {}
    media_to_post = {str(v.get("media_id")): k for k, v in state.items() if v.get("media_id")}
    items = queue_index()
    rows, errors, after = [], set(), None
    while len(rows) < MAX_MEDIA:
        page = api.get(f"{uid}/media", limit=50, after=after,
                       fields="id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count")
        for m in page.get("data", []):
            stats, err = fetch_insights(api, m["id"])
            if err:
                errors.add(err[:200])
            pid = media_to_post.get(str(m["id"]))
            first = (m.get("caption") or "").strip().split("\n")[0][:90]
            rows.append({"media_id": m["id"], "tidspunkt": m.get("timestamp"), "link": m.get("permalink"),
                         "type": m.get("media_product_type") or m.get("media_type"), "første_linje": first,
                         "likes": m.get("like_count"), "kommentarer": m.get("comments_count"),
                         **stats, **describe(items.get(pid))})
        after = (page.get("paging") or {}).get("cursors", {}).get("after")
        if not after or not (page.get("paging") or {}).get("next"):
            break
    return rows, sorted(errors)


def _shortcode(link):
    m = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]+)", link or "")
    return m.group(1) if m else None


def merge_public_views(rows, path=None):
    """Fylder visninger ud med de offentlige afspilningstal fra results/visninger.json, hvor Meta ikke giver dem.

    Filen skrives af den ugentlige kørsel, der læser instagram.com/ikigaiguiden/reels/ i en browser.
    Returnerer datoen for aflæsningen, eller None hvis intet blev brugt."""
    path = path or PUBLIC_VIEWS
    if not path.exists():
        return None
    data = common.read_json(path)
    counts = data.get("reels") or {}
    used = False
    for r in rows:
        if isinstance(r.get("views"), (int, float)):
            continue
        code = _shortcode(r.get("link"))
        if code in counts and isinstance(counts[code], (int, float)):
            r["views"] = counts[code]
            r["views_offentlig"] = True
            used = True
    return (data.get("aflæst") or "")[:10] if used else None


def _median(rows, key):
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return (round(statistics.median(vals)), len(vals)) if vals else (None, 0)


def summarize(rows, errors, fetched_at, umami=None, dm_state=None, now=None, public_views_date=None):
    """Markdown-oversigt til ugens generering. Ingen tankestreger."""
    has_views = any(isinstance(r.get("views"), (int, float)) for r in rows)
    key = "views" if has_views else "likes"
    lines = [f"# Tal fra Instagram (hentet {fetched_at})", ""]
    lines += umami_lines(umami)
    lines += vinkel_lines(rows, umami, dm_state, now or datetime.now(timezone.utc))
    if has_views and public_views_date:
        lines += [f"Visninger er Instagrams offentlige afspilningstal for reels, aflæst {public_views_date}. "
                  "Karruseller har ingen offentlige tal, og rækkevidde, gemte og delte mangler stadig, "
                  "fordi nøglen ikke har tilladelsen instagram_business_manage_insights.", ""]
    if not has_views:
        lines += ["Visninger mangler: nøglen har ikke tilladelsen instagram_business_manage_insights.",
                  "Oversigten bruger derfor likes. Giv nøglen tilladelsen hos Meta for at få visninger.", ""]
    lines += [f"## Median {key} pr. gruppe", "", "| Gruppe | Median | Antal |", "| --- | --- | --- |"]
    groups = [("Alle manuelle opslag", [r for r in rows if r.get("kilde") == "manuel"]),
              ("Alle autopilot-opslag", [r for r in rows if r.get("kilde") == "autopilot"])]
    for f in ("klip", "tekstkort", "slides", "liste", "linje"):
        groups.append((f"Autopilot, format {f}", [r for r in rows if r.get("format") == f]))
    for t in common.THEME_NAMES:
        groups.append((f"Autopilot, tema {t}", [r for r in rows if r.get("kilde") == "autopilot" and r.get("tema") == t]))
    for name, rs in groups:
        med, n = _median(rs, key)
        if n:
            lines.append(f"| {name} | {med} | {n} |")
    lines += ["", "## Alle opslag, nyeste først", "",
              "| Dato | Kilde | Format | Tema | Visninger | Rækkevidde | Gemt | Delt | Likes | Første linje |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]

    def cell(v):
        return "" if v is None else str(v)

    for r in sorted(rows, key=lambda r: r.get("tidspunkt") or "", reverse=True):
        first = (r.get("første_linje") or "").replace("|", "/")
        lines.append("| " + " | ".join([
            (r.get("tidspunkt") or "")[:10], r.get("kilde", ""), cell(r.get("format")), cell(r.get("tema")),
            cell(r.get("views")), cell(r.get("reach")), cell(r.get("saved")), cell(r.get("shares")),
            cell(r.get("likes")), first]) + " |")
    if errors:
        lines += ["", "## Fejl fra Instagram", ""] + [f"* {e}" for e in errors]
    text = "\n".join(lines) + "\n"
    for bad, good in (("\u2014", ","), ("\u2013", ","), ("\u2026", "...")):
        text = text.replace(bad, good)
    return text


def main():
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        log("IG_ACCESS_TOKEN er ikke sat. Der hentes ingen tal.")
        return 0
    cfg = common.read_json(common.DATA / "config.json")
    expected_id = str(cfg.get("instagram_user_id", "")).strip()
    fb_token = token.startswith("EAA")
    base = "https://graph.facebook.com" if fb_token else "https://graph.instagram.com"
    api = Api(base, os.environ.get("IG_API_VERSION", "v23.0"), token, expected_id if fb_token else None)
    try:
        uid = api.user_id()
    except ApiError as e:
        log(f"Kunne ikke slå kontoen op: {e}")
        return 1
    expected = str(cfg.get("instagram_username", "")).lower().lstrip("@")
    actual = str(api.username or "").lower().lstrip("@")
    if actual != expected or actual in FORBIDDEN_ACCOUNTS or (expected_id and uid != expected_id):
        log(f"KONTOSPÆRRE: nøglen hører til @{actual or '?'}, ikke @{expected}. Der hentes ingen tal.")
        return 1
    rows, errors = collect(api, uid)
    public_views_date = merge_public_views(rows)
    now = datetime.now(timezone.utc)
    fetched_at = now.isoformat(timespec="minutes")
    umami = None
    key = os.environ.get("UMAMI_API_KEY", "").strip()
    share_id = os.environ.get("UMAMI_SHARE_ID", "").strip() or str(cfg.get("umami_share_id", "")).strip()
    if not key and share_id:
        try:
            key = umami_share_auth(share_id)
        except (urllib.error.URLError, ValueError, KeyError, TimeoutError) as e:
            errors = sorted(set(errors) | {f"Umami delingslink: {str(e)[:150]}"})
    if key:
        umami, uerr = fetch_umami(key, now)
        errors = sorted(set(errors) | set(uerr))
    dm_state = common.read_json(DM_STATE) if DM_STATE.exists() else None
    common.write_json(RESULTS / "insights.json", {"hentet": fetched_at, "opslag": rows, "fejl": errors, "umami": umami})
    (RESULTS / "OVERSIGT.md").write_text(summarize(rows, errors, fetched_at, umami, dm_state, now, public_views_date), encoding="utf-8")
    log(f"Hentede tal for {len(rows)} opslag." + (f" {len(errors)} fejltyper, se results/OVERSIGT.md." if errors else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
