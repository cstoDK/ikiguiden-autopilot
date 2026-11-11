"""Test af TikTok-udgivelsen mod en mock af Zernio. Kør: python3 tests/test_tiktok.py

Beviser alt undtagen selve mødet med Zernios og TikToks rigtige servere.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "pipeline"))
from mock_zernio import GOOD_KEY, Mock  # noqa: E402
import tiktok  # noqa: E402

mock = Mock()
results = []
WEEK = "2026-W46"
TUE_ID, WED_ID = "2026-W46-tirsdag-1900-karrusel", "2026-W46-onsdag-1900-karrusel"
FILES = {"02-tirsdag-1900-karrusel.json": "2026-11-10T19:00:00+01:00",
         "03-onsdag-1900-karrusel.json": "2026-11-11T19:00:00+01:00",
         "01-mandag-1900-reel.json": "2026-11-09T19:00:00+01:00"}
TUE = "2026-11-10T18:10:00+00:00"   # 19:10 dansk tid, tirsdagens karrusel er forfalden
WED = "2026-11-11T18:10:00+00:00"
Q = {p.name: json.loads(p.read_text()) for p in (REPO / "queue" / WEEK).glob("*.json")}


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("  ok   " if cond else "  FEJL ") + name + (f"   <- {detail}" if detail and not cond else ""))


def fresh(config=None, edit=None):
    d = Path(tempfile.mkdtemp(prefix="autopilot-tiktok-"))
    (d / "queue" / WEEK).mkdir(parents=True)
    for name, when in FILES.items():
        o = dict(Q[name], publish_at=when)
        if edit and name in edit:
            o.update(edit[name])
        (d / "queue" / WEEK / name).write_text(json.dumps(o, ensure_ascii=False))
    shutil.copytree(REPO / "media" / WEEK, d / "media" / WEEK)
    shutil.copytree(REPO / "brand" / "baggrunde", d / "brand" / "baggrunde")  # tema "foto" tjekker, at billedet findes
    cfg = {"instagram_username": "ikigaiguiden", "tiktok_username": "ikigaiguiden", "tiktok_mode": "auto"}
    cfg.update(config or {})
    (d / "config.json").write_text(json.dumps({k: v for k, v in cfg.items() if v is not None}))
    (d / "state").mkdir()
    mock.reset(d / "media")
    return d


def run(root, now, key=GOOD_KEY, extra=()):
    env = {**os.environ, "AUTOPILOT_ROOT": str(root)}
    env.pop("ZERNIO_API_KEY", None)
    if key is not None:
        env["ZERNIO_API_KEY"] = key
    cmd = [sys.executable, str(REPO / "pipeline" / "tiktok.py"), "--now", now,
           "--api-base", f"{mock.base}/v1", "--public-base", f"{mock.base}/media", *extra]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=root)
    return p.returncode, p.stdout + p.stderr


def state(root):
    f = root / "state" / "tiktok.json"
    return json.loads(f.read_text())["posts"] if f.exists() else {}


print("\n1. Uden nøgle sker der ingenting")
d = fresh()
rc, out = run(d, TUE, key=None)
check("afslutter uden fejl og siger, at TikTok ikke er tændt", rc == 0 and "ikke tændt" in out, out)
check("ingen kald", not mock.calls)

print("\n2. Tørkørsel rører hverken netværk eller status")
d = fresh()
rc, out = run(d, TUE, extra=["--dry-run"])
check("afslutter uden fejl", rc == 0, out)
check("viser opslaget", "tørkørsel" in out and "auto_add_music" in out, out)
check("ingen kald og ingen status", not mock.calls and state(d) == {})

print("\n3. Rigtig kørsel: tirsdagens karrusel udgives med musik")
d = fresh()
rc, out = run(d, TUE)
check("afslutter uden fejl", rc == 0, out)
st = state(d)
check("status er published", st.get(TUE_ID, {}).get("status") == "published", st)
posts = mock.created()
check("præcis ét opslag", len(posts) == 1)
b = posts[0]["body"]
NS = len(Q["02-tirsdag-1900-karrusel.json"]["slides"])
check("et billede pr. slide, i rækkefølge", [m["url"].rsplit("/", 1)[1] for m in b["mediaItems"]]
      == [f"slide-{i:02d}.jpg" for i in range(1, NS + 1)] and all(m["type"] == "image" for m in b["mediaItems"]), b)
ts = b["tiktokSettings"]
check("fotoopslag, offentligt, med TikToks anbefalede musik", ts["media_type"] == "photo"
      and ts["privacy_level"] == "PUBLIC_TO_EVERYONE" and ts["auto_add_music"] is True and "draft" not in ts, ts)
check("samtykkefelterne er sat", ts["content_preview_confirmed"] is True and ts["express_consent_given"] is True)
check("hele captionen er beskrivelsen", ts["description"] == Q["02-tirsdag-1900-karrusel.json"]["caption"])
check("titlen er højst 90 tegn og uden hashtags", 0 < len(b["content"]) <= 90 and "#" not in b["content"], b["content"])
check("sendt til den rigtige konto", b["platforms"] == [{"platform": "tiktok", "accountId": "acc1"}])
check("udgives nu", b["publishNow"] is True)
check("fast nøgle mod dubletter", posts[0]["key"] and TUE_ID in posts[0]["key"])
check("onsdag og reelen er ikke rørt", set(st) == {TUE_ID}, st)
check("nøglen står ikke i loggen", GOOD_KEY not in out)

print("\n4. Samme kørsel igen giver ingen dubletter")
n_before = len(mock.calls)
rc, out = run(d, TUE)
check("intet at sende", rc == 0 and "Intet at sende" in out, out)
check("ingen nye kald", len(mock.calls) == n_before)

print("\n5. Kladde: opslaget lander i indbakken uden musikvalg")
d = fresh(config={"tiktok_mode": "kladde"})
rc, out = run(d, TUE)
ts = mock.created()[0]["body"]["tiktokSettings"]
check("status er draft", rc == 0 and state(d)[TUE_ID]["status"] == "draft", out)
check("draft sat, ingen auto-musik og intet synlighedsvalg", ts.get("draft") is True and "auto_add_music" not in ts and "privacy_level" not in ts, ts)
check("loggen siger, hvad Christian skal gøre", "KLADDE SENDT" in out, out)

print("\n6. Et enkelt opslag kan vælge kladde eller holdes væk fra TikTok")
d = fresh(edit={"02-tirsdag-1900-karrusel.json": {"tiktok": "kladde"}})
rc, out = run(d, TUE)
check("opslagets eget valg vinder over config", rc == 0 and state(d)[TUE_ID]["status"] == "draft", out)
d = fresh(edit={"02-tirsdag-1900-karrusel.json": {"tiktok": False}})
rc, out = run(d, TUE)
check("tiktok: false sender intet", rc == 0 and not mock.created() and state(d) == {}, out)

print("\n7. Kontospærre")
d = fresh(config={"tiktok_username": None})
rc, out = run(d, TUE)
check("uden tiktok_username sendes intet, og kontiene vises", rc == 1 and "KONTOSPÆRRE" in out and "@ikigaiguiden" in out and not mock.created(), out)
d = fresh()
mock.accounts = [{"_id": "acc9", "platform": "tiktok", "username": "christianstoltze"}]
rc, out = run(d, TUE)
check("forkert konto hos Zernio: intet sendt", rc == 1 and "KONTOSPÆRRE" in out and not mock.created(), out)
d = fresh(config={"tiktok_username": "christianstoltze"})
mock.accounts = [{"_id": "acc9", "platform": "tiktok", "username": "christianstoltze"}]
rc, out = run(d, TUE)
check("privat profil er spærret, selv hvis den står i config", rc == 1 and "KONTOSPÆRRE" in out and not mock.created(), out)
d = fresh()
rc, out = run(d, TUE, extra=["--check-account"])
check("--check-account siger OK og sender intet", rc == 0 and "TIKTOK-KONTO OK" in out and not mock.created(), out)
rc, out = run(d, TUE, key="forkert")
check("forkert nøgle: tydelig fejl, intet sendt", rc == 1 and "afviste nøglen" in out and not mock.created(), out)

print("\n8. Privat TikTok-konto: der postes ikke skjult")
d = fresh()
mock.levels = ["SELF_ONLY"]
rc, out = run(d, TUE)
check("fejler synligt og sender intet", rc == 1 and "offentligt" in out and not mock.created(), out)
check("forsøget er talt", state(d)[TUE_ID].get("attempts") == 1, state(d))

print("\n9. For gamle opslag og PAUSE")
d = fresh()
rc, out = run(d, "2026-11-11T16:00:00+00:00")
check("22 timer forsinket: sendes ikke", rc == 0 and not mock.created(), out)
d = fresh()
(d / "PAUSE").write_text("")
rc, out = run(d, TUE)
check("PAUSE stopper alt", rc == 0 and "PAUSE" in out and not mock.calls, out)

print("\n10. Opslag undervejs følges op ved næste kørsel")
d = fresh()
mock.post_status = "publishing"
rc, out = run(d, TUE)
check("første kørsel: sendt, ikke bekræftet", rc == 0 and state(d)[TUE_ID]["status"] == "sent", out)
rc, out = run(d, "2026-11-10T18:40:00+00:00")
st = state(d)[TUE_ID]
check("næste kørsel: bekræftet udgivet med adresse", rc == 0 and st["status"] == "published" and "tiktok.com" in st.get("url", ""), out)
check("stadig kun ét opslag", len(mock.created()) == 1)
d = fresh()
mock.post_status, mock.later_status = "publishing", "failed"
run(d, TUE)
rc, out = run(d, "2026-11-10T18:40:00+00:00")
check("afvist bagefter: fejlen bliver synlig", rc == 1 and state(d)[TUE_ID]["status"] == "failed" and "afviste" in out, out)

print("\n11. TikTok afviser med det samme")
d = fresh()
mock.post_status = "failed"
rc, out = run(d, TUE)
check("fejler synligt og markeres failed", rc == 1 and state(d)[TUE_ID]["status"] == "failed" and "capacity" in out, out)
rc, out = run(d, "2026-11-10T18:40:00+00:00")
check("prøver ikke det samme opslag igen af sig selv", len(mock.created()) == 1, out)

print("\n12. Midlertidig serverfejl: genforsøg uden dublet")
d = fresh()
mock.fail_first = 1
rc, out = run(d, TUE)
check("udgivet efter genforsøg", rc == 0 and state(d)[TUE_ID]["status"] == "published", out)
check("begge forsøg brugte samme nøgle, og der er ét opslag", len(mock.created()) == 2
      and mock.created()[0]["key"] == mock.created()[1]["key"] and len(mock.posts) == 1)

print("\n13. Kvalitetsporten gælder også TikTok")
d = fresh(edit={"02-tirsdag-1900-karrusel.json": {"caption": "Se https://x.dk\n\nTekst"}})
rc, out = run(d, TUE)
check("spærret og ikke sendt", rc == 1 and state(d)[TUE_ID]["status"] == "blocked" and not mock.created(), out)

print("\n14. Titlen")
check("kort første linje bruges uændret", tiktok.title_of("Du er ikke doven.\n\nMere tekst #a") == "Du er ikke doven.")
long = "Et meget langt første afsnit som bliver ved og ved og ved, langt ud over de halvfems tegn TikTok tillader i titlen"
t = tiktok.title_of(long)
check("lang linje klippes ved et ordskel", len(t) <= 90 and long.startswith(t) and long[len(t)] == " ", t)
check("hashtags fjernes", "#" not in tiktok.title_of("Hej #studievalg med dig"))
check("hele sætninger foretrækkes", tiktok.title_of(Q["02-tirsdag-1900-karrusel.json"]["caption"])
      == "Du vil være helt sikker, før du vælger uddannelse.")

print("\n15. Onsdagens karrusel dagen efter")
d = fresh()
run(d, TUE)
rc, out = run(d, WED)
check("begge er udgivet, hver for sig", rc == 0 and {k: v["status"] for k, v in state(d).items()} == {TUE_ID: "published", WED_ID: "published"}, out)

ok = sum(1 for _, c in results if c)
print(f"\n{ok} af {len(results)} tjek bestået")
sys.exit(0 if ok == len(results) else 1)
