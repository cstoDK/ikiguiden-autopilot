# Ugens opgave: lav næste uges indhold til @Ikiguiden

Du kører uden en menneskelig læser. Træf rimelige valg, skriv øverst i din afsluttende besked hvilke, og stop kun hvis noget ikke kan fortrydes.

## 1. Læs først

- `brand/STYLE.md`, `brand/EKSEMPLER.md`, `brand/KARRUSEL.md`: stemme og visuel stil.
- `brand/FACTS.md`: eneste tilladte fakta og tal.
- `queue/` og `state/published.json`: hvad der er lavet og udgivet de seneste uger. Gentag ikke emner, hooks eller første linjer.
- `results/OVERSIGT.md`: tal for hvert opslag på profilen, hentet dagligt af `pipeline/insights.py`. Læs den først og lad tallene styre ugens valg (se afsnittet om tal nederst).
- `reserve/`: færdige opslag, der blev skrevet, men ikke brugt. Du må tage dem i brug (giv dem nyt id, filnavn, `publish_at` og `tema`), hvis emnet ikke er udgivet endnu.
- `brand/baggrunde/`: Christians egne billeder til tema `foto`.

Brand-filerne bruger selv tankestreger og har eksempler med dem (fx "mini-test — link i bio"). Kopiér aldrig tegnet. Gengivelsen følger `pipeline/render.py`, ikke pixelmålene i KARRUSEL.md.

## 2. Lav 7 opslag til næste uge (mandag til søndag, 1 om dagen)

Mappe: `queue/<ISO-uge>/`, fx `queue/2026-W47/`. Filnavne `01-mandag-1900-karrusel.json` osv. Kopiér felter og format fra ugen før. Id'et er `<uge>-<dag>-<kl>-<type>`.

Fast tid (Europe/Copenhagen, med tidszone i `publish_at`, +01:00 om vinteren og +02:00 i sommertid): hver dag kl. 19:00. Ét opslag om dagen, fordi to om dagen gav færre visninger pr. opslag. Undgå to opslag i træk med samme emne eller samme første linje.

Hver uge skal blandingen mindst indeholde 2 opslag af typen **teach**, 2 af typen **opinion** og 2 af typen **offer** (leder til den gratis mini-test via link i bio). Resten må være korte observationer og spørgsmål til følgerne, så længe de holder sig til FACTS.md.

Mangler du friske vinkler uden at opfinde fakta, så lav færre opslag frem for gentagelser. Højst 7, aldrig fyld med næsten ens indhold. Skriv i afslutningen, hvis du lavede færre.

Opslag af typen proof (resultater, historier, udtalelser fra brugere) og story (personlige historier) må du aldrig lave selv. Der er ingen verificerede at bygge på.

### Karruseller: brug liste-formatet

Mindst halvdelen af ugens karruseller skal være liste-karruseller (se `queue/2026-W45/02-torsdag-karrusel.json` som skabelon):
- Slide 1 `hook`: et liste-løfte, fx "5 ting, ingen fortæller dig, før du vælger uddannelse". Tallet skal være lig antallet af punkter.
- Slides `liste` med `num` 1, 2, 3 ...: én kort påstand som overskrift og en til to sætninger under.
- Sidste slide `produkt`: viser testen på en telefon. Overskrift "Tag den gratis [[mini-test]]." og under "2 minutter. Ingen login. Link i bio." med "2 minutter" i `facts`.
- Første linje i captionen gentager liste-løftet. Slut med et spørgsmål, folk kan svare på med et nummer.

Formater og overskriftsskabeloner må gerne lånes fra opslag, der går godt i nichen (også engelske om studievalg, karriere og "college"). Tekst og billeder fra andre må aldrig kopieres.

## 3. Regler der ikke kan forhandles

- Ingen tankestreger, ingen krøllede citationstegn, intet "…"-tegn.
- Ingen tal uden at de står i FACTS.md og i opslagets `facts`-felt.
- Hook i første linje (højst 125 tegn), konkret og uden hilsen eller emoji i starten.
- Højst 3 hashtags, højst 2 emojis, ingen URL i caption. Eneste opfordring er "Link i bio".
- Karrusel: 5 til 10 slides. Reels er slået fra.
- Skriv i du-form, dansk, uden floskler som "i dagens samfund", "rejse", "unlock", "game changer".
- Ingen medicinske, juridiske eller økonomiske løfter. Ingen påstande om at kende brugerens "rigtige" svar.

## 4. Byg og tjek

1. `python3 pipeline/build.py` (kvalitetsporten kører først og stopper ved fejl). Ret teksten, til den passerer. Omgå aldrig porten.
2. `python3 tests/run_tests.py` skal være grøn.
3. Kig på mindst én gengivet slide fra hvert tema, så teksten ikke løber ud over kanten og kan læses.

## 5. Udgiv til køen

Commit `queue/` og `media/` på main med beskeden `Indhold uge <nr>`, og push. Publisering sker af sig selv fra GitHub Actions på de planlagte tidspunkter. Rør aldrig `state/`, `config.json` eller `pipeline/publish.py`, og opret aldrig `PAUSE`.

## 6. Afslut kort

Højst 6 linjer på dansk: hvilke emner og formater du valgte, hvad der ikke blev lavet og hvorfor, og om noget skal afgøres af et menneske. Ingen opremsning af trin.

## Tillæg: sammenhængende "følg linjen"-karrusel

Mindst 1 af ugens opslag skal have `"format": "linje"`. Her løber én linje ubrudt hen over alle slides, så man skal swipe for at følge den. Hver slide har feltet `linje` med en af værdierne `lige`, `løkker`, `kaos`, `bølge` og `mål`. Første slide er `lige`, sidste er `mål` (pil mod CTA), og imellem bruges linjen som billede på pointen, fx lige vs. filtret, eller tvivl der retter sig ud. Teksten skal være kort, fordi linjen fylder nederste halvdel: højst 2 korte linjer overskrift plus én kort undertekst pr. slide, 5 til 7 slides. Se `queue/2026-W45/13-tirsdag-1900-karrusel.json` som eksempel. Find gerne på nye historier, linjen kan fortælle, i stedet for at gentage eksemplet.

## VIGTIGST, gælder over alt ovenfor: kun ægte karruseller, 1 om dagen, varieret udseende

Lav ALLE 7 opslag som `"type": "carousel"` med `slides`. Ingen `"type": "reel"` og ingen `cards`. Video-karruseller (slides udgivet som video) virkede ikke på profilen, så de er slået fra, og kvalitetsporten afviser nye reels.

- Filnavne og id slutter på `karrusel`, fx `01-mandag-1900-karrusel.json` og `2026-W47-mandag-1900-karrusel`.
- 5 til 10 slides. Mindst 1 liste-karrusel (`"format": "liste"`) og mindst 1 linje-karrusel (`"format": "linje"`) om ugen. Resten almindelige slides (hook, text, cta, produkt).
- Første slide skal få en fremmed til at swipe. Det må gerne slutte med en lille åbning, der kræver næste slide.
- Tema `foto` virker også på karruseller: billedet ligger dæmpet bag hver slide.
- Slides udgives som billeder. Lav aldrig slides om til video, heller ikke for at få musik på. Musik kan kun sættes på i Instagram-appen, ikke af autopiloten.

### Tema: profilen må ikke ligne én lang beige flade

Hvert opslag har feltet `"tema"`: `lys`, `mørk`, `grøn`, `brun` eller `foto`. Brug mindst 3 forskellige temaer om ugen, og aldrig samme tema to dage i træk (tjek også sidste opslag i ugen før). Tema `foto` kræver `"bg": "brand/baggrunde/<fil>.jpg"` og må kun bruge billeder, der ligger i den mappe. Ligger der billeder, så brug foto til mindst 2 opslag, og aldrig samme billede to gange på en uge.

### Tal styrer valget

Visningerne faldt fra omkring 150 til 10 til 60, da autopiloten gik i gang med 2 opslag om dagen i samme beige udseende. Tallet om "150 visninger for reels" gælder derfor ikke længere. Læs `results/OVERSIGT.md` og:

- Lav flere af de formater, temaer og emner, der har højest median, og færre af dem i bunden. Skriv i afslutningen, hvad tallene fik dig til at ændre.
- Manuelle opslag (dem Christian selv har lavet) er målestokken. Ligger autopiloten langt under dem, så skriv det i afslutningen.
- Mangler filen eller visningstallene, så skriv det i afslutningen og fortsæt med blandingen ovenfor.

## Tillæg: første kort skal stoppe en fremmed

De fleste, der ser et opslag, følger ikke profilen. Første kort skal derfor give mening og vække genkendelse hos en fremmed, uden at nævne testen, Ikigai-guiden eller prisen. Et offer-opslag åbner med en observation eller et problem og kommer først til testen bagefter. Et opslag, der åbner med produktet, skal skrives om.
