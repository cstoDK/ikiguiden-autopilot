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
from mock_graph import GOOD_TOKEN, Mock  # noqa: E402
import lint  # noqa: E402

mock = Mock()
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("  ok   " if cond else "  FEJL ") + name + (f"   <- {detail}" if detail and not cond else ""))


def fresh():
    d = Path(tempfile.mkdtemp(prefix="autopilot-"))
    shutil.copytree(REPO / "queue", d / "queue")
    shutil.copytree(REPO / "media", d / "media")
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
check("8 børne-containere med billede-url", len(kids) == 8 and all(k["params"]["image_url"].endswith(".jpg") for k in kids))
check("hver slide har alt-tekst", all(k["params"].get("alt_text") for k in kids))
check("én karrusel-container med 8 børn og caption", len(parent) == 1 and len(parent[0]["params"]["children"].split(",")) == 8
      and parent[0]["params"]["caption"] == Q["02-torsdag-karrusel"]["caption"])
check("fredag og søndag er ikke rørt", "2026-W45-fredag-reel" not in st and "2026-W45-soendag-karrusel" not in st)

print("\n5. Instagram afviser alt-tekst: genforsøg uden")
d = fresh()
mock.bad_alt = True
rc, out = run(d, THU)
check("udgives alligevel", rc == 0 and state(d)["2026-W45-torsdag-karrusel"]["status"] == "published", out)
kids = [c for c in mock.posts("/media") if c["params"].get("is_carousel_item") == "true" and "alt_text" not in c["params"]]
check("børnene blev oprettet uden alt_text", len(kids) == 8)

print("\n6. Udløbet adgangsnøgle")
d = fresh()
rc, out = run(d, TUE, token="GAMMEL-NOEGLE-123")
check("afslutter med fejl", rc == 1)
check("siger klart hvad der er galt", "Adgangsnøglen" in out, out)
check("nøglen lækker ikke til loggen", "GAMMEL-NOEGLE-123" not in out)
check("fejlen er gemt på opslaget", state(d)["2026-W45-tirsdag-reel"].get("attempts") == 1)

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

print("\n13. Kvalitetsporten fanger dårligt indhold")
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

mock.close()
failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)} af {len(results)} tjek bestået" + (f"; FEJLEDE: {failed}" if failed else ""))
sys.exit(1 if failed else 0)
