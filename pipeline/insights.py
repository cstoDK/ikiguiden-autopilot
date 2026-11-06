"""Henter tal for profilens opslag fra Instagram og skriver dem til results/.

Brug: python3 pipeline/insights.py
Kører dagligt i GitHub Actions. Udgiver og ændrer intet på Instagram, den læser kun.
Ugens generering læser results/OVERSIGT.md og bruger tallene til at vælge formater.

Kræver at nøglen har tilladelsen instagram_business_manage_insights. Mangler den, gemmes
stadig likes og kommentarer, og OVERSIGT.md siger, hvad der mangler.
"""
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from publish import Api, ApiError, FORBIDDEN_ACCOUNTS, STATE_PATH  # noqa: E402

RESULTS = common.ROOT / "results"
METRICS = ["views", "reach", "saved", "shares", "total_interactions"]
MAX_MEDIA = 200


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
    if item.get("cards"):
        fmt = "tekstkort"
    elif item.get("format") == "linje":
        fmt = "linje"
    elif item.get("format") == "liste":
        fmt = "liste"
    else:
        fmt = "slides"
    return {"kilde": "autopilot", "id": item.get("id"), "format": fmt, "tema": item.get("tema", "lys"),
            "planlagt": item.get("publish_at")}


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


def _median(rows, key):
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return (round(statistics.median(vals)), len(vals)) if vals else (None, 0)


def summarize(rows, errors, fetched_at):
    """Markdown-oversigt til ugens generering. Ingen tankestreger."""
    has_views = any(isinstance(r.get("views"), (int, float)) for r in rows)
    key = "views" if has_views else "likes"
    lines = [f"# Tal fra Instagram (hentet {fetched_at})", ""]
    if not has_views:
        lines += ["Visninger mangler: nøglen har ikke tilladelsen instagram_business_manage_insights.",
                  "Oversigten bruger derfor likes. Giv nøglen tilladelsen hos Meta for at få visninger.", ""]
    lines += [f"## Median {key} pr. gruppe", "", "| Gruppe | Median | Antal |", "| --- | --- | --- |"]
    groups = [("Alle manuelle opslag", [r for r in rows if r.get("kilde") == "manuel"]),
              ("Alle autopilot-opslag", [r for r in rows if r.get("kilde") == "autopilot"])]
    for f in ("tekstkort", "slides", "liste", "linje"):
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
    cfg = common.read_json(common.ROOT / "config.json")
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
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="minutes")
    common.write_json(RESULTS / "insights.json", {"hentet": fetched_at, "opslag": rows, "fejl": errors})
    (RESULTS / "OVERSIGT.md").write_text(summarize(rows, errors, fetched_at), encoding="utf-8")
    log(f"Hentede tal for {len(rows)} opslag." + (f" {len(errors)} fejltyper, se results/OVERSIGT.md." if errors else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
