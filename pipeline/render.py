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
import music

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
             "-i", str(music.beat(sum(common.card_seconds(c) for c in cards), item["id"], Path(tmp) / "beat.wav")),
             "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-af", "volume=0.8,alimiter=limit=0.9", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out / "reel.mp4")],
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
    payload = {k: item.get(k) for k in ("type", "format", "slides", "cards")}
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
    if item["type"] == "reel" and item.get("slides"):
        render_swipe_reel(page, item, out)
    elif item["type"] == "carousel" and item.get("format") == "linje":
        render_panorama(page, item, out)
    else:
        (render_carousel if item["type"] == "carousel" else render_reel)(page, item, out)
    stamp.write_text(h)
    return True


# ---------------- Sammenhængende "følg linjen"-karrusel ----------------
# Én bred tegning (1080 x antal slides) med en linje, der løber hen over alle slides.
# Linjen er lige i reklamen, filtret i virkeligheden og retter sig ud mod testen.
import math  # noqa: E402

LINE_Y = 1060


def _segment(style, x0, w=1080):
    pts = []
    if style == "lige":
        pts = [(x0 + x, LINE_Y) for x in range(0, w + 1, 20)]
    elif style in ("løkker", "kaos"):
        k = 2 if style == "løkker" else 3
        a = w / (2 * math.pi * k)
        b = 150 if style == "løkker" else 120
        n = 400
        for i in range(n + 1):
            t = 2 * math.pi * k * i / n
            drift = 0 if style == "løkker" else 70 * math.sin(t / k * 1.5)
            pts.append((x0 + a * t - b * math.sin(t), LINE_Y + b * (math.cos(t) - 1) + drift * math.sin(t / 2) ** 2))
    elif style == "bølge":
        for x in range(0, w + 1, 8):
            amp = 110 * (1 - x / w) ** 1.4
            pts.append((x0 + x, LINE_Y - amp * math.sin(x / w * 2 * math.pi * 2.5)))
    elif style == "mål":
        pts = [(x0 + x, LINE_Y) for x in range(0, w - 180 + 1, 20)]
    return pts


def panorama_html(item, fonts):
    slides = item["slides"]
    n = len(slides)
    pts = []
    for i, s in enumerate(slides):
        seg = _segment(s.get("linje", "lige"), i * 1080)
        if i == 0:
            seg = [p for p in seg if p[0] >= 150]
        pts += seg
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    ex, ey = pts[-1]
    blocks = []
    for i, s in enumerate(slides):
        kind = s.get("kind", "text")
        hs, ss = {"hook": (104, 50), "cta": (92, 50)}.get(kind, (84, 50))
        heads = "".join(f'<div class="h" style="font-size:{hs}px">{fmt(t)}</div>' for t in s["h"])
        subs = "".join(f'<div class="s" style="font-size:{ss}px">{fmt(t)}</div>' for t in s.get("sub", []))
        cls = " cta" if kind == "cta" else ""
        blocks.append(f'<div class="blk{cls}" style="left:{i*1080+96}px">{heads}{subs}</div>'
                      f'<div class="foot" style="left:{i*1080+96}px"><span>Ikiguiden</span><span class="n">{i+1}/{n}</span></div>')
    return f"""<!doctype html><html lang="da"><head><meta charset="utf-8"><style>{fonts}{BASE_CSS}
body{{width:{n*1080}px;height:1440px;position:relative;overflow:hidden;background:{BG}}}
.bar{{position:absolute;top:0;left:0;width:{n*1080}px;height:14px;background:{BROWN}}}
.blk{{position:absolute;top:170px;width:888px;height:600px;display:flex;flex-direction:column;justify-content:flex-start;color:{INK};font-family:'Inter',sans-serif}}
.blk.cta .h{{color:{BROWN}}}
.foot{{position:absolute;bottom:84px;width:888px;display:flex;justify-content:space-between;font-size:28px;color:{BROWN};font-weight:600;letter-spacing:1.5px;font-family:'Inter',sans-serif}}
.foot .n{{font-weight:400;color:{INK};opacity:.55}}
.dig{{position:absolute;left:96px;top:{LINE_Y+40}px;font-family:'Inter';font-weight:600;font-size:30px;color:{GREEN};letter-spacing:1px}}
</style></head><body><div class="bar"></div>
<svg width="{n*1080}" height="1440" style="position:absolute;left:0;top:0">
<path d="{d}" fill="none" stroke="{INK}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="150" cy="{LINE_Y}" r="26" fill="{GREEN}"/>
<path d="M{ex-10},{ey-44} L{ex+46},{ey} L{ex-10},{ey+44} Z" fill="{GREEN}"/>
</svg><div class="dig">DIG</div>{''.join(blocks)}</body></html>"""


def render_panorama(page, item, out):
    from PIL import Image
    n = len(item["slides"])
    page.set_viewport_size({"width": 1080 * n, "height": 1440})
    with tempfile.TemporaryDirectory() as tmp:
        full = Path(tmp) / "pano.png"
        shot(page, panorama_html(item, font_css()), tmp, "pano", full, kind="png")
        im = Image.open(full).convert("RGB")
        for i in range(n):
            im.crop((i * 1080, 0, (i + 1) * 1080, 1440)).save(out / f"slide-{i+1:02d}.jpg", quality=92)


# ---------------- Swipe-reel: en karrusel som video, med beat ----------------
# Slides glider til siden som et swipe. Instagram viser reels for mange flere end
# karruseller, og en reel kan have lyd, hvad en automatisk udgivet karrusel ikke kan.
def render_swipe_reel(page, item, out):
    from PIL import Image
    slides = item["slides"]
    n = len(slides)
    with tempfile.TemporaryDirectory() as tmp:
        if item.get("format") == "linje":
            page.set_viewport_size({"width": 1080 * n, "height": 1440})
            full = Path(tmp) / "pano.png"
            shot(page, panorama_html(item, font_css()), tmp, "pano", full, kind="png")
            strip = Image.open(full).convert("RGB")
        else:
            fonts = font_css()
            page.set_viewport_size({"width": 1080, "height": 1440})
            strip = Image.new("RGB", (1080 * n, 1440))
            for i, s in enumerate(slides, 1):
                fp = Path(tmp) / f"s{i}.png"
                shot(page, carousel_html(s, i, n, fonts), tmp, f"s{i}", fp, kind="png")
                strip.paste(Image.open(fp).convert("RGB"), ((i - 1) * 1080, 0))
        holds = [common.slide_seconds(s) for s in slides]
        sw = common.SWIPE_SECONDS
        total = sum(holds) + sw * (n - 1)
        fps = 30
        bg = Image.new("RGB", (1080, 1920), BG)
        bar = Image.new("RGB", (1080, 14), BROWN)
        # Tidslinje: (start, slut, fra-slide) for hvert swipe.
        events, t = [], 0.0
        for i in range(n - 1):
            t += holds[i]
            events.append((t, t + sw, i))
            t += sw

        def offset_at(t):
            pos = 0.0
            for a, b, i in events:
                if t >= b:
                    pos = i + 1
                elif t >= a:
                    u = (t - a) / sw
                    u = 1 - (1 - u) ** 3  # bremser blødt op som et rigtigt swipe
                    return (i + u) * 1080
            return pos * 1080

        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1080x1920",
               "-r", str(fps), "-i", "-",
               "-i", str(music.beat(total, item["id"], Path(tmp) / "beat.wav")),
               "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-af", "volume=0.8,alimiter=limit=0.9", "-c:a", "aac", "-b:a", "128k", "-shortest",
               "-movflags", "+faststart", str(out / "reel.mp4")]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        first = None
        for f in range(int(total * fps)):
            x = int(round(offset_at(f / fps)))
            frame = bg.copy()
            frame.paste(strip.crop((x, 0, x + 1080, 1440)), (0, 240))
            if first is None:
                first = frame
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg fejlede under swipe-reel")
        first.save(out / "cover.jpg", quality=92)
