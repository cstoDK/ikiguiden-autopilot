"""Render karruseller (JPEG 1080x1440) og stumme tekst-reels (MP4 1080x1920).

Stil efter brand/KARRUSEL.md: Playfair Display + Inter, lys varm baggrund, én grøn
accent, tynd bjælke øverst, intet andet pynt. Skriftstørrelserne er større end i
specifikationen, fordi 24 px brødtekst er ulæseligt på en telefon.

Reels er tekstkort uden lyd. Teksten holdes inden for Instagrams sikre zone:
ikke over y=230 og ikke under y=1440, og de højre 230 px holdes fri.
"""
import hashlib
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path

import common

BG, INK, BROWN, GREEN = "#F5F0EA", "#1A1A1A", "#8B5E3C", "#4A7C59"
CAROUSEL_SIZES = {"hook": (108, 54), "text": (84, 54), "cta": (96, 58), "liste": (84, 52), "produkt": (80, 44)}


def fmt(text):
    esc = html.escape(text)
    esc = re.sub(r"\[\[(.+?)\]\]", r'<span class="g">\1</span>', esc)
    return esc.replace("mini-test", '<span class="nw">mini-test</span>')


def font_css():
    base = common.ensure_fonts()

    def face(pkg, name, weight):
        f = base / pkg / "files" / f"{pkg}-latin-{weight}-normal.woff2"
        return (f"@font-face{{font-family:'{name}';font-weight:{weight};"
                f"src:url('file://{f}') format('woff2');}}")

    return "".join([face("playfair-display", "Playfair Display", 800),
                    face("inter", "Inter", 400), face("inter", "Inter", 600)])


BASE_CSS = f"""
html,body{{margin:0;padding:0;background:{BG}}}
.slide{{position:relative;overflow:hidden;background:{BG};color:{INK};font-family:'Inter',sans-serif}}
.bar{{position:absolute;top:0;left:0;right:0;height:14px;background:{BROWN}}}
.h,.s{{text-wrap:balance}}
.h{{font-family:'Playfair Display',serif;font-weight:800;line-height:1.16;margin:0 0 18px;letter-spacing:-0.4px}}
.s{{line-height:1.38;margin:30px 0 0;font-weight:400}}
.s + .s{{margin-top:14px}}
.nw{{white-space:nowrap}}
.g{{color:{GREEN}}}
.cta .h{{color:{BROWN}}}
"""


# Produktslide: en telefon med testens første spørgsmål, ordret fra ikigaiguide.dk.
PHONE = f"""<div class="phone"><div class="screen">
<div class="pcat">Det du elsker</div>
<div class="pq">Hvilke aktiviteter får dig til at glemme tid og sted?</div>
<div class="chips"><span>Skrive</span><span>Undervise</span><span>Analysere</span><span>Tale med mennesker</span><span>Skabe noget</span><span>Lære nyt</span></div>
<div class="pbtn">Næste</div></div></div>"""
PHONE_CSS = f"""
.phone{{margin:44px 0 0;width:520px;height:640px;border:14px solid {INK};border-bottom:none;border-radius:64px 64px 0 0;background:#FFFDF9;overflow:hidden;align-self:flex-start}}
.screen{{padding:58px 44px}}
.pcat{{font-size:22px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:{GREEN}}}
.pq{{font-family:'Playfair Display',serif;font-weight:800;font-size:40px;line-height:1.18;margin:18px 0 30px}}
.chips span{{display:inline-block;font-size:22px;padding:10px 18px;margin:0 10px 12px 0;border:2px solid #D9CFC3;border-radius:999px}}
.pbtn{{margin-top:22px;background:{INK};color:#fff;font-weight:600;font-size:24px;text-align:center;padding:18px;border-radius:14px}}
"""


def carousel_html(slide, n, total, fonts):
    kind = slide.get("kind", "text")
    hs, ss = CAROUSEL_SIZES[kind]
    heads = "".join(f'<div class="h">{fmt(t)}</div>' for t in slide["h"])
    subs = "".join(f'<div class="s">{fmt(t)}</div>' for t in slide.get("sub", []))
    cta = " cta" if kind == "cta" else ""
    num = f'<div class="num">{int(slide["num"])}</div>' if kind == "liste" and slide.get("num") else ""
    phone = PHONE if kind == "produkt" else ""
    top = "150px" if kind == "produkt" else "170px"
    return f"""<!doctype html><html lang="da"><head><meta charset="utf-8"><style>{fonts}{BASE_CSS}{PHONE_CSS}
.num{{font-family:'Playfair Display',serif;font-weight:800;font-size:220px;line-height:1;color:{GREEN};margin:0 0 20px}}
.slide{{width:1080px;height:1440px}}
.content{{position:absolute;left:96px;right:96px;top:{top};bottom:210px;display:flex;flex-direction:column;justify-content:center}}
.h{{font-size:{hs}px}} .s{{font-size:{ss}px}}
.foot{{position:absolute;left:96px;right:96px;bottom:84px;display:flex;justify-content:space-between;align-items:baseline;font-size:28px;color:{BROWN};font-weight:600;letter-spacing:1.5px}}
.foot .n{{font-weight:400;color:{INK};opacity:.55;letter-spacing:1px}}
</style></head><body><div class="slide{cta}"><div class="bar"></div>
<div class="content">{num}{heads}{subs}{phone}</div>
<div class="foot"><span>Ikiguiden</span><span class="n">{n}/{total}</span></div></div></body></html>"""


def reel_html(text, fonts):
    plain = common.strip_marks(text)
    size = 116 if len(plain) <= 32 else 100 if len(plain) <= 62 else 88
    cta = " cta" if re.search(r"link i bio", plain, re.I) else ""
    return f"""<!doctype html><html lang="da"><head><meta charset="utf-8"><style>{fonts}{BASE_CSS}
.slide{{width:1080px;height:1920px}}
.content{{position:absolute;left:96px;top:260px;width:754px;height:1120px;display:flex;flex-direction:column;justify-content:center}}
.h{{font-size:{size}px;margin:0}}
.tag{{position:absolute;left:96px;top:1340px;font-size:28px;font-weight:600;letter-spacing:1.5px;color:{BROWN}}}
</style></head><body><div class="slide{cta}"><div class="bar"></div>
<div class="content"><div class="h">{fmt(text)}</div></div>
<div class="tag">Ikiguiden</div></div></body></html>"""


def shot(page, html_text, workdir, name, path, kind="jpeg"):
    hp = Path(workdir) / f"{name}.html"
    hp.write_text(html_text, encoding="utf-8")
    page.goto(f"file://{hp}")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(200)
    if kind == "jpeg":
        page.screenshot(path=str(path), type="jpeg", quality=92)
    else:
        page.screenshot(path=str(path), type="png")


def render_carousel(page, item, out):
    fonts = font_css()
    slides = item["slides"]
    page.set_viewport_size({"width": 1080, "height": 1440})
    with tempfile.TemporaryDirectory() as tmp:
        for i, s in enumerate(slides, 1):
            shot(page, carousel_html(s, i, len(slides), fonts), tmp, f"s{i}", out / f"slide-{i:02d}.jpg")


def render_reel(page, item, out):
    fonts = font_css()
    cards = item["cards"]
    page.set_viewport_size({"width": 1080, "height": 1920})
    with tempfile.TemporaryDirectory() as tmp:
        frames = []
        for i, c in enumerate(cards, 1):
            fp = Path(tmp) / f"f{i:02d}.png"
            shot(page, reel_html(c, fonts), tmp, f"c{i}", fp, kind="png")
            frames.append(fp)
        listing = Path(tmp) / "list.txt"
        lines = []
        for fp, c in zip(frames, cards):
            lines += [f"file '{fp}'", f"duration {common.card_seconds(c)}"]
        lines.append(f"file '{frames[-1]}'")
        listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-f", "lavfi", "-i", f"aevalsrc={music_expr([common.card_seconds(c) for c in cards])}|{music_expr([common.card_seconds(c) for c in cards])}:s=44100:d={sum(common.card_seconds(c) for c in cards) + 0.5:.2f}",
             "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-af", "volume=0.5,alimiter=limit=0.85", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out / "reel.mp4")],
            check=True,
        )
        page.set_viewport_size({"width": 1080, "height": 1920})
        page.goto(f"file://{frames[0]}")
        page.screenshot(path=str(out / "cover.jpg"), type="jpeg", quality=92)


def music_expr(durations):
    """Eget, rettighedsfrit lydbed: varm akkord, langsom svævning og et blødt klik hver gang kortet skifter."""
    total = sum(durations)
    notes = [(110.0, 0.20), (164.81, 0.14), (220.0, 0.12), (261.63, 0.09), (329.63, 0.06)]
    pad = "+".join(f"{a}*sin(2*PI*{f}*t)" for f, a in notes)
    swell = f"(0.75+0.25*sin(2*PI*0.11*t))*min(1,t/1.5)*min(1,({total}-t)/1.5)"
    ticks, t0 = [], 0.0
    for d in durations[:-1]:
        t0 += d
        ticks.append(f"0.35*exp(-30*max(0,t-{t0:.2f}))*sin(2*PI*880*t)*gte(t,{t0:.2f})")
    expr = f"0.55*({pad})*{swell}" + ("+" + "+".join(ticks) if ticks else "")
    return expr.replace(",", "\\,")


def item_hash(item):
    payload = {k: item.get(k) for k in ("type", "slides", "cards")}
    return hashlib.sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def render_item(page, item, force=False):
    out = common.media_dir(item)
    out.mkdir(parents=True, exist_ok=True)
    stamp = out / ".hash"
    h = item_hash(item)
    if not force and stamp.exists() and stamp.read_text() == h:
        return False
    for f in out.iterdir():
        if f.is_file():
            f.unlink()
    (render_carousel if item["type"] == "carousel" else render_reel)(page, item, out)
    stamp.write_text(h)
    return True
