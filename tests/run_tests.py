"""Test af hele autopiloten mod en mock af Instagram. Kør: python3 tests/run_tests.py

Beviser alt undtagen selve mødet med Metas rigtige servere.
"""
import copy
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
from mock_graph import FB_TOKEN, GOOD_TOKEN, Mock  # noqa: E402
import lint  # noqa: E402

mock = Mock()
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("  ok   " if cond else "  FEJL ") + name + (f"   <- {detail}" if detail and not cond else ""))


FIXTURES = {"01-tirsdag-reel.json", "02-torsdag-karrusel.json", "02a-onsdag-1200-karrusel.json",
            "03-fredag-reel.json", "04-soendag-karrusel.json"}


def fresh():
    d = Path(tempfile.mkdtemp(prefix="autopilot-"))
    shutil.copytree(REPO / "queue", d / "queue")
    shutil.copytree(REPO / "media", d / "media")
    shutil.copy(REPO / "config.json", d / "config.json")
    # Testene regner med den oprindelige plan, uanset om et opslag er flyttet i den rigtige kø.
    q1 = d / "queue" / "2026-W45" / "01-tirsdag-reel.json"
    o = json.loads(q1.read_text())
    o["publish_at"] = "2026-11-03T19:00:00+01:00"
    q1.write_text(json.dumps(o, ensure_ascii=False))
    q2 = d / "queue" / "2026-W45" / "02-torsdag-karrusel.json"
    o = json.loads(q2.read_text())
    o["publish_at"] = "2026-11-05T19:00:00+01:00"
    q2.write_text(json.dumps(o, ensure_ascii=False))
    # Testene bruger kun de fem oprindelige opslag, uanset hvor mange der senere er lagt i den rigtige kø.
    for extra in (d / "queue" / "2026-W45").glob("*.json"):
        if extra.name not in FIXTURES:
            extra.unlink()
    (d / "state").mkdir()
    (d / "state" / "published.json").write_text('{"posts": {}}\n')
    mock.reset(d / "media")
    return d


def run(root, now, token=GOOD_TOKEN, extra=()):
    env = {**os.environ, "AUTOPILOT_ROOT": str(root)}
    env.pop("IG_ACCESS_TOKEN", None)
    if token is not None:
        env["IG_ACCESS_TOKEN"] = token
    cmd = [sys.executable, str(REPO / "pipeline" / "publish.py"), "--now", now, "--poll", "0.05",
           "--api-base", mock.base, "--public-base", f"{mock.base}/media", *extra]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=root)
    return p.returncode, p.stdout + p.stderr


def state(root):
    return json.loads((root / "state" / "published.json").read_text())["posts"]


TUE = "2026-11-03T18:10:00+00:00"   # 19:10 dansk tid, tirsdagens reel er forfalden
THU = "2026-11-05T18:10:00+00:00"
Q = {p.stem: json.loads(p.read_text()) for p in (REPO / "queue" / "2026-W45").glob("*.json")}

print("\n1. Tørkørsel rører hverken netværk eller status")
d = fresh()
rc, out = run(d, TUE, extra=["--dry-run"])
check("afslutter uden fejl", rc == 0, out)
check("viser REELS-kaldet", "REELS" in out and "tørkørsel" in out, out)
check("ingen kald til Instagram", not mock.calls)
check("status uændret", state(d) == {})

print("\n2. Rigtig kørsel: tirsdagens reel")
d = fresh()
rc, out = run(d, TUE)
check("afslutter uden fejl", rc == 0, out)
st = state(d)["2026-W45-tirsdag-reel"]
check("status er published med media-id", st["status"] == "published" and st.get("media_id"), st)
create = mock.posts("/media")
check("præcis én container", len(create) == 1)
cp = create[0]["params"]
check("media_type REELS", cp["media_type"] == "REELS")
check("video_url peger på reel.mp4", cp["video_url"].endswith("2026-W45/2026-W45-tirsdag-reel/reel.mp4"), cp)
check("caption er uændret", cp["caption"] == Q["01-tirsdag-reel"]["caption"])
pub = mock.posts("/media_publish")
check("præcis én udgivelse, med containerens id", len(pub) == 1 and pub[0]["params"]["creation_id"].startswith("r"))
check("kun tirsdag blev rørt", set(state(d)) == {"2026-W45-tirsdag-reel"})
check("nøglen står ikke i loggen", GOOD_TOKEN not in out)

print("\n3. Samme kørsel igen giver ingen dubletter")
n_before = len(mock.calls)
rc, out = run(d, TUE)
check("afslutter uden fejl", rc == 0)
check("intet at udgive", "Intet at udgive" in out, out)
check("ingen nye kald", len(mock.calls) == n_before)

print("\n4. Torsdagens karrusel (og tirsdagens springes over, fordi den er for gammel)")
d = fresh()
rc, out = run(d, THU)
check("afslutter uden fejl", rc == 0, out)
st = state(d)
check("tirsdag markeret som sprunget over", st["2026-W45-tirsdag-reel"]["status"] == "skipped_stale", st)
check("torsdag udgivet", st["2026-W45-torsdag-karrusel"]["status"] == "published", st)
creates = mock.posts("/media")
kids = [c for c in creates if c["params"].get("is_carousel_item") == "true"]
parent = [c for c in creates if c["params"].get("media_type") == "CAROUSEL"]
NK = len(Q["02-torsdag-karrusel"]["slides"])
check("én børne-container pr. slide med billede-url", len(kids) == NK and all(k["params"]["image_url"].endswith(".jpg") for k in kids))
check("hver slide har alt-tekst", all(k["params"].get("alt_text") for k in kids))
check("én karrusel-container med alle børn og caption", len(parent) == 1 and len(parent[0]["params"]["children"].split(",")) == NK
      and parent[0]["params"]["caption"] == Q["02-torsdag-karrusel"]["caption"])
check("fredag og søndag er ikke rørt", "2026-W45-fredag-reel" not in st and "2026-W45-soendag-karrusel" not in st)

print("\n5. Instagram afviser alt-tekst: genforsøg uden")
d = fresh()
mock.bad_alt = True
rc, out = run(d, THU)
check("udgives alligevel", rc == 0 and state(d)["2026-W45-torsdag-karrusel"]["status"] == "published", out)
kids = [c for c in mock.posts("/media") if c["params"].get("is_carousel_item") == "true" and "alt_text" not in c["params"]]
check("børnene blev oprettet uden alt_text", len(kids) == NK)

print("\n5b. Karrusel med ægte musik fra Instagrams bibliotek")
d = fresh()
mock.music = True
rc, out = run(d, THU)
parent = [c for c in mock.posts("/media") if c["params"].get("media_type") == "CAROUSEL"]
check("udgivet", rc == 0 and state(d)["2026-W45-torsdag-karrusel"]["status"] == "published", out)
check("karrusel-containeren har audio_configuration med nummeret",
      len(parent) == 1 and json.loads(parent[0]["params"].get("audio_configuration", "{}")).get("audio_id") == "777", parent)
check("lydtypen MUSIC er gemt i status", state(d)["2026-W45-torsdag-karrusel"].get("music", {}).get("media_audio_type") == "MUSIC")

print("\n6. Udløbet adgangsnøgle")
d = fresh()
rc, out = run(d, TUE, token="GAMMEL-NOEGLE-123")
check("afslutter med fejl", rc == 1)
check("siger klart hvad der er galt", "Adgangsnøglen" in out, out)
check("nøglen lækker ikke til loggen", "GAMMEL-NOEGLE-123" not in out)
check("intet forsøgt udgivet", not mock.posts("/media"))

print("\n7. PAUSE-filen stopper alt")
d = fresh()
(d / "PAUSE").write_text("")
rc, out = run(d, TUE)
check("afslutter roligt", rc == 0 and "PAUSE" in out, out)
check("ingen kald", not mock.calls)

print("\n8. Ingen nøgle sat endnu")
d = fresh()
rc, out = run(d, TUE, token=None)
check("afslutter uden fejl og siger det", rc == 0 and "ikke tændt" in out, out)
check("ingen kald", not mock.calls)

print("\n9. Genoptagelse efter afbrudt kørsel (container findes, men er ikke udgivet)")
d = fresh()
(d / "state" / "published.json").write_text(json.dumps({"posts": {"2026-W45-tirsdag-reel": {"status": "container", "creation_id": "r99"}}}))
rc, out = run(d, TUE)
check("udgives", rc == 0 and state(d)["2026-W45-tirsdag-reel"]["status"] == "published", out)
check("lavede ikke en ny container", len(mock.posts("/media")) == 0)
check("udgav den gamle container", [c["params"]["creation_id"] for c in mock.posts("/media_publish")] == ["r99"])

print("\n10. Kvalitetsporten spærrer et opslag med tankestreg")
d = fresh()
qf = d / "queue" / "2026-W45" / "01-tirsdag-reel.json"
obj = json.loads(qf.read_text())
obj["caption"] = obj["caption"].replace("Mange tror", "Mange — tror")
qf.write_text(json.dumps(obj, ensure_ascii=False))
rc, out = run(d, TUE)
check("afslutter med fejl", rc == 1 and "tankestreg" in out, out)
check("ingen kald til Instagram", not mock.posts("/media"))
rc, out = run(d, TUE)
check("spærret opslag forsøges ikke igen hver halve time", rc == 0 and not mock.posts("/media"), out)

print("\n11. Medie mangler")
d = fresh()
(d / "media" / "2026-W45" / "2026-W45-tirsdag-reel" / "reel.mp4").unlink()
rc, out = run(d, TUE)
check("spærret med besked om manglende fil", rc == 1 and "reel.mp4 mangler" in out, out)

print("\n12. Hosting leverer forkert filtype (som raw.githubusercontent kan finde på med mp4)")
d = fresh()
mock.octet_mp4 = True
rc, out = run(d, TUE)
check("udgives ikke, og forklarer hvorfor", rc == 1 and "ikke offentligt tilgængeligt" in out, out)
check("ingen container oprettet", not mock.posts("/media"))

print("\n13. KONTOSPÆRRE: nøglen hører til den private profil")
d = fresh()
mock.username = "christianstoltze"
rc, out = run(d, TUE)
check("afslutter med fejl og siger KONTOSPÆRRE", rc == 1 and "KONTOSPÆRRE" in out, out)
check("intet oprettet eller udgivet", not mock.posts("/media") and not mock.posts("/media_publish"))

print("\n14. KONTOSPÆRRE: privat profil står selv i config.json")
d = fresh()
(d / "config.json").write_text('{"instagram_username": "christianstoltze"}')
mock.username = "christianstoltze"
rc, out = run(d, TUE)
check("nægter alligevel", rc == 1 and "KONTOSPÆRRE" in out and not mock.posts("/media"), out)

print("\n15. KONTOSPÆRRE: config.json mangler brugernavn")
d = fresh()
(d / "config.json").write_text('{}')
rc, out = run(d, TUE)
check("nægter", rc == 1 and "KONTOSPÆRRE" in out and not mock.posts("/media"), out)

print("\n16. Facebook-nøgle (Unified login) udgiver på den låste konto")
d = fresh()
rc, out = run(d, TUE, token=FB_TOKEN)
check("udgivet", rc == 0 and state(d)["2026-W45-tirsdag-reel"]["status"] == "published", out)
check("brugte Instagram-kontoens id, ikke /me", mock.posts("/media") and mock.posts("/media")[0]["path"].startswith("17841439605652106/"))
check("nøglen står ikke i loggen", FB_TOKEN not in out)

print("\n17. KONTOSPÆRRE: rigtigt navn, forkert konto-id")
d = fresh()
mock.uid = "999"
rc, out = run(d, TUE)
check("nægter", rc == 1 and "KONTOSPÆRRE" in out and not mock.posts("/media"), out)

print("\n17b. --check-account: tjekker konto uden at udgive")
d = fresh()
rc, out = run(d, TUE, extra=["--check-account"])
check("siger KONTO OK og udgiver intet", rc == 0 and "KONTO OK" in out and "@ikigaiguiden" in out and not mock.posts("/media"), out)
mock.username = "christianstoltze"
rc, out = run(d, TUE, extra=["--check-account"])
check("afvises på privat profil", rc == 1 and "KONTOSPÆRRE" in out, out)

print("\n18. Kvalitetsporten fanger dårligt indhold")
base = copy.deepcopy(Q["02-torsdag-karrusel"])
base["_path"] = REPO / "queue" / "2026-W45" / "x.json"


def with_(**kw):
    o = copy.deepcopy(base)
    o.update(kw)
    return lint.check(o)


check("opfundet tal afvises", any("75" in p for p in with_(caption=base["caption"] + "\n75 procent vælger forkert")))
check("6 hashtags afvises", any("hashtags" in p for p in with_(caption=base["caption"] + " #a #b #c")))
check("link i caption afvises", any("Link" in p for p in with_(caption="Se https://x.dk\n\nTekst")))
check("for lang første linje afvises", any("Første linje" in p for p in with_(caption="x" * 130 + "\n\nTekst")))
check("skjult tegn afvises", any("skjult" in p for p in with_(caption="Hej​ verden")))
check("for få slides afvises", any("slides" in p for p in with_(slides=base["slides"][:3])))
check("godkendt tal i facts accepteres", not any("2" in p and "facts" in p for p in lint.check({**Q["04-soendag-karrusel"], "_path": base["_path"]})))

print("\n19. Tema og tal fra Instagram")
check("ukendt tema afvises", any("tema" in p for p in with_(tema="neon")))
check("foto uden billede afvises", any("foto" in p for p in with_(tema="foto", bg="brand/baggrunde/findes-ikke.jpg")))
check("mørkt tema accepteres", not lint.check({**Q["04-soendag-karrusel"], "_path": base["_path"], "tema": "mørk"}))
import insights  # noqa: E402
rows = [{"kilde": "manuel", "views": 150, "første_linje": "a"},
        {"kilde": "autopilot", "format": "tekstkort", "tema": "lys", "views": 20, "første_linje": "b | c"},
        {"kilde": "autopilot", "format": "liste", "tema": "mørk", "views": 40, "første_linje": "d \u2014 e"}]
md = insights.summarize(rows, [], "2026-11-06T19:00+00:00")
check("oversigt har medianer og ingen tankestreger", "| Alle manuelle opslag | 150 | 1 |" in md and "| Alle autopilot-opslag | 30 | 2 |" in md
      and "\u2014" not in md and "\u2013" not in md, md)
env = {k: v for k, v in os.environ.items() if k != "IG_ACCESS_TOKEN"}
pr = subprocess.run([sys.executable, str(REPO / "pipeline" / "insights.py")], env=env, capture_output=True, text=True)
check("uden nøgle hentes intet og intet fejler", pr.returncode == 0 and "ikke sat" in pr.stdout, pr.stdout + pr.stderr)

mock.close()
failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)} af {len(results)} tjek bestået" + (f"; FEJLEDE: {failed}" if failed else ""))
sys.exit(1 if failed else 0)
