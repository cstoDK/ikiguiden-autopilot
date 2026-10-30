# Ugens opgave: lav næste uges indhold til @Ikiguiden

Du kører uden en menneskelig læser. Træf rimelige valg, skriv øverst i din afsluttende besked hvilke, og stop kun hvis noget ikke kan fortrydes.

## 1. Læs først

- `brand/STYLE.md`, `brand/EKSEMPLER.md`, `brand/KARRUSEL.md`: stemme og visuel stil.
- `brand/FACTS.md`: eneste tilladte fakta og tal.
- `queue/` og `state/published.json`: hvad der er lavet og udgivet de seneste uger. Gentag ikke emner, hooks eller første linjer.
- Mappen `results/` hvis den findes (indsigter fra tidligere uger).

Brand-filerne bruger selv tankestreger og har eksempler med dem (fx "mini-test — link i bio"). Kopiér aldrig tegnet. Gengivelsen følger `pipeline/render.py`, ikke pixelmålene i KARRUSEL.md.

## 2. Lav 4 opslag til næste uge (mandag til søndag)

Mappe: `queue/<ISO-uge>/`, fx `queue/2026-W46/`. Filnavne `01-tirsdag-reel.json` osv. Kopiér felter og format fra ugen før. Id'et er `<uge>-<dag>-<type>`.

Faste tider (Europe/Copenhagen, med tidszone i `publish_at`): tirsdag 19:00 reel, torsdag 19:00 karrusel, fredag 17:30 reel, søndag 19:00 karrusel. Skift til +02:00 i sommertid.

Hver uge skal blandingen mindst indeholde:
- et opslag af typen **teach** (konkret indsigt om valg af uddannelse eller retning),
- et opslag af typen **opinion** (en klar holdning, der kan diskuteres),
- et opslag af typen **offer** (leder til den gratis mini-test via link i bio).

Opslag af typen proof (resultater, historier, udtalelser fra brugere) og story (personlige historier) må du aldrig lave selv. Der er ingen verificerede at bygge på.

## 3. Regler der ikke kan forhandles

- Ingen tankestreger, ingen krøllede citationstegn, intet "…"-tegn.
- Ingen tal uden at de står i FACTS.md og i opslagets `facts`-felt.
- Hook i første linje (højst 125 tegn), konkret og uden hilsen eller emoji i starten.
- Højst 3 hashtags, højst 2 emojis, ingen URL i caption. Eneste opfordring er "Link i bio".
- Reel: 5 til 16 tekstkort, samlet 15 til 60 sekunder. Karrusel: 5 til 10 slides.
- Skriv i du-form, dansk, uden floskler som "i dagens samfund", "rejse", "unlock", "game changer".
- Ingen medicinske, juridiske eller økonomiske løfter. Ingen påstande om at kende brugerens "rigtige" svar.

## 4. Byg og tjek

1. `python3 pipeline/build.py` (kvalitetsporten kører først og stopper ved fejl). Ret teksten, til den passerer. Omgå aldrig porten.
2. `python3 tests/run_tests.py` skal være grøn.
3. Kig på mindst én gengivet slide og ét reel-kontaktark, så teksten ikke løber ud over kanten.

## 5. Udgiv til køen

Commit `queue/` og `media/` på main med beskeden `Indhold uge <nr>`, og push. Publisering sker af sig selv fra GitHub Actions på de planlagte tidspunkter. Rør aldrig `state/`, `config.json` eller `pipeline/publish.py`, og opret aldrig `PAUSE`.

## 6. Afslut kort

Højst 6 linjer på dansk: hvilke emner og formater du valgte, hvad der ikke blev lavet og hvorfor, og om noget skal afgøres af et menneske. Ingen opremsning af trin.
