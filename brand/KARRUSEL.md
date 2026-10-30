---
name: carousel-maker
description: Lav Instagram og TikTok carousels til Ikiguiden. Brug denne skill når brugeren beder om at lave et carousel, slides, en slide-serie, eller visuelt indhold til sociale medier. Brug også denne skill hvis brugeren siger "lav et carousel om X", "byg slides til", "design et opslag med flere sider" eller lignende.
---

# Carousel-Maker — Ikiguiden

## Format

- **Størrelse:** 1080 × 1440 px (3:4) — altid, ingen undtagelser
- **Slides:** 8–10 max. Sjældent under 5.
- **Output:** HTML/CSS med præcis pixel-layout, eksporterbar som PNG per slide

---

## Farvepalette

| Rolle | Hex |
|---|---|
| Baggrund (primær) | `#F5F0EA` |
| Kort/slide baggrund | `#F0E8E0` |
| Primær tekst | `#1A1A1A` |
| Accent (links, CTA) | `#8B5E3C` |
| Grøn accent (highlights) | `#4A7C59` |
| Hvid (kontrast) | `#FFFFFF` |

Brug aldrig hårde/mættede farver. Paletten er varm, organisk og rolig.

---

## Typografi

- **Overskrift:** Playfair Display (serif) — tung, varm, autoritet
- **Brødtekst:** Inter (sans-serif) — clean, læsbar
- Begge fås fra Google Fonts
- Skriftstørrelser:
  - Hook-slide overskrift: 52–64px
  - Mellemslide overskrift: 36–44px
  - Brødtekst: 22–26px
  - CTA-tekst: 24–28px bold

---

## Slidestruktur

### Slide 1 — Hook (scroll-stopper)
- Én enkelt provokerende sætning
- Stor skrift, meget luft
- Undertitel må gerne uddybe med 1 linje
- Ingen lister

### Slide 2–7 — Værdi-slides
- Én pointe per slide
- Max 3–4 linjer tekst
- Linjeskift som åndedrætspause (som i voice-skillen)
- Brug gerne et enkelt nøgleord i grøn accent

### Slide 8 (næstsidst) — Opsummering/indsigt
- Den centrale pointe gentaget klarere
- Kort. 2–3 linjer.

### Sidste slide — CTA
Vælg én af disse (eller lad brugeren specificere):
- "Tag den gratis mini-test — link i bio 🔗"
- "Følg for mere om retning og studievalg"
- "Gem dette — du får brug for det"
- "Skriv [ord] i kommentaren, så sender jeg linket"

---

## Layoutprincipper

- Masser af whitespace — aldrig overfyldt
- Tekst altid venstrejusteret ELLER centreret — aldrig blandet
- Ingen skygger, gradienter eller dekorative elementer
- Evt. simpel linje eller farvet bjælke øverst som brandingmarkør
- Logo/branding diskret nederst på hver slide (lille, ikke forstyrrende)

---

## Tone på slides

Følg ikiguiden-style skillen. Kortere end i opslagstekster.
En slide = én tanke. Aldrig mere.

---

## Output-format

Generer hvert slide som en selvstændig HTML-blok med inline CSS.
Brug `width: 1080px; height: 1440px` som container.
Inkluder Google Fonts import øverst.

Slides nummereres: Slide 1/8, Slide 2/8 osv.
