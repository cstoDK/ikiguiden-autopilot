# Ugens opgave: lav næste uges indhold til @Ikiguiden

Du kører uden en menneskelig læser. Træf rimelige valg, skriv øverst i din afsluttende besked hvilke, og stop kun hvis noget ikke kan fortrydes.

## 1. Læs først

- `brand/STYLE.md` og `brand/EKSEMPLER.md`: stemmen. `brand/KARRUSEL.md` gælder kun karruseller, som er sat på pause.
- `brand/FACTS.md`: eneste tilladte fakta og tal.
- `brand/ARKETYPER.md`: de 12 arketyper fra arketypetesten. Navnene skal staves præcis sådan.
- `queue/` og `state/published.json`: hvad der er lavet og udgivet de seneste uger. Gentag ikke emner, hooks eller første linjer.
- `results/OVERSIGT.md`: tal for hvert opslag på profilen, hentet dagligt af `pipeline/insights.py`. Læs den først og lad tallene styre ugens valg (se afsnittet om tal nederst).
- `reserve/`: færdige karruseller, der blev skrevet, men ikke brugt. Emnerne og captionerne må genbruges i klip-reels, hvis emnet ikke er udgivet endnu.
- `brand/baggrunde/` og `brand/klip/`: Christians egne billeder og videoklip, der bruges som baggrund i klip-reels.

Brand-filerne bruger selv tankestreger og har eksempler med dem (fx "mini-test — link i bio"). Kopiér aldrig tegnet. Gengivelsen følger `pipeline/render.py`, ikke pixelmålene i KARRUSEL.md.

## 2. Lav 7 klip-reels til næste uge (mandag til søndag, 1 om dagen)

Strategien blev lagt om 15. november 2026, fordi tallene var entydige. Christians egne reels (eget billede eller klip i fuld skærm, få korte linjer tekst, få sekunder) fik typisk 120 til 250 visninger og enkelte over 1.500. Autopilotens beige tekstkort og karruseller fik 10 til 60. Autopiloten laver derfor nu den slags reels, Christian selv lavede, og ikke karruseller.

Mappe: `queue/<ISO-uge>/`, fx `queue/2026-W48/`. Filnavne `01-mandag-1900-reel.json` osv. Id'et er `<uge>-<dag>-1900-reel`. Brug `queue/2026-W47/` som skabelon:

```json
{
  "id": "2026-W47-mandag-1900-reel",
  "type": "reel",
  "format": "klip",
  "publish_at": "2026-11-16T19:00:00+01:00",
  "bg": "brand/baggrunde/skovvej-sving.jpg",
  "stil": "hvid",
  "lines": ["Pov: du tror, du skal vælge rigtigt i første forsøg", "Det skal du ikke.", "De fleste finder vej ved at prøve sig frem."],
  "caption": "..."
}
```

Fast tid (Europe/Copenhagen, med tidszone i `publish_at`, +01:00 om vinteren og +02:00 i sommertid): hver dag kl. 19:00. Ét opslag om dagen.

### Sådan skrives et klip

- `lines`: 2 til 4 korte linjer, højst 70 tegn pr. linje og højst 34 ord i alt. De dukker op én ad gangen. Hele klippet varer 6 til 10 sekunder, så det bliver set til ende og kører i ring.
- Linje 1 er hele opslaget for de fleste. Den skal stoppe en fremmed, der ikke følger profilen, og må ikke nævne testen, profilen eller link i bio. Den står på skærmen fra første billede og er også forsiden i gitteret.
- Sidste linje er pointen eller et spørgsmål. Højst 2 af ugens 7 klip må slutte med "Link i bio" på selve klippet. Resten har kun opfordringen i captionen.
- Ingen emojis på klippet (de kan ikke gengives). Brug dem i captionen.
- `[[ord]]` fremhæver ét ord med grøn. Brug det højst én gang pr. klip.
- Captionen: hook i første linje, den ærlige pointe i 2 til 4 korte linjer (højst ca. 400 tegn i alt), et spørgsmål folk kan svare på, og til sidst kommentar-opfordringen (se nedenfor).

### Kommentar giver link (det vigtigste mål er gennemførte tests)

Målet er ikke visninger, men gennemførte tests. Vejen via profilen og "link i bio" taber de fleste. Derfor svarer autopiloten selv med linket i en besked, når nogen kommenterer (pipeline/comments.py, hvert kvarter).

- Hvert klip har feltet `"dm"`: `"studievalg"` eller `"arketype"`. Det er det link, en TEST-kommentar får.
- Captionen slutter altid med én af disse, så den passer til `dm`:
  - studievalg: "Skriv TEST i kommentarerne, så sender jeg dig testen 📩"
  - arketype: "Skriv ARKETYPE i kommentarerne, så sender jeg dig testen 📩"
- Højst 3 af ugens 7 klip må have opfordringen ("Skriv TEST" eller "Skriv ARKETYPE") som sidste linje på selve klippet. Resten slutter med pointen eller et spørgsmål.
- "Link i bio" må stå som anden mulighed i captionen, men aldrig som eneste opfordring.

### Vinkler: test af arketyper mod studievalg (uge 48 og 49)

I uge 48 og 49 testes to vinkler mod hinanden. Lav 4 arketype-klip (`"dm": "arketype"`) og 3 studievalgs-klip (`"dm": "studievalg"`) om ugen, og bland dem, så samme vinkel aldrig kører tre dage i træk.

- Arketype-klip bruger navnene og kernelinjerne i `brand/ARKETYPER.md` og formaterne nederst i den fil. Brug begge versioner (fx Kongen og Dronningen) på tværs af ugen. Tallet 12 må kun bruges med "12 arketyper" i `facts`.
- Studievalgs-klip skrives som hidtil.
- Fra uge 50: se på "Tests pr. vinkel" i `results/OVERSIGT.md`. Giver én vinkel klart flere gennemførte tests pr. 1.000 visninger, så får den 5 af 7 klip. Er tallene for små til at sige noget, så fortsæt 4 mod 3, og skriv det i afslutningen.

### Variation, så tallene kan vise, hvad der virker

Brug mindst 4 forskellige åbninger på en uge, og aldrig samme åbning to dage i træk:

- Pov: "Pov: du tror, du skal vælge rigtigt i første forsøg"
- Modsætning: "Du er ikke lost. Du er bare overstimuleret."
- Spørgsmål: "Startet på studiet og allerede i tvivl?"
- Observation: "Alle har en mening om, hvad du skal læse."
- Sådan gør du: "Sådan siger du til dine forældre, at du er i tvivl"
- Genkendelig hverdag med lidt humor. De af Christians reels, der fik flest visninger, var sjove og genkendelige, ikke belærende.

Indholdet skal stadig blandes: mindst 2 teach, 2 opinion og 2 offer om ugen. Typen kan ses i captionen, ikke nødvendigvis på klippet. Proof og story må du aldrig lave selv.

### Baggrund og stil

- `bg` er et af Christians egne billeder i `brand/baggrunde/` eller et af hans videoklip i `brand/klip/`. Ligger der klip i `brand/klip/`, så brug dem først: ægte video slår et stillbillede med zoom.
- Aldrig samme baggrund to gange på en uge, og undgå dem, der blev brugt de sidste 3 dage ugen før.
- `stil` er `hvid` (sort tekst på hvide etiketter), `sort` (hvid tekst på sorte etiketter) eller `ren` (hvid tekst med skygge, kun på rolige eller mørke billeder). Skift mellem dem. Aldrig samme stil to dage i træk.
- Feltet `tema` bruges ikke på klip-reels.
- Musik sættes på af sig selv fra Instagrams bibliotek ved udgivelsen. Du kan styre stemningen med `"music_search": "lofi chill"`, men behøver det ikke.

Mangler du friske vinkler uden at opfinde fakta, så lav færre opslag frem for gentagelser. Skriv i afslutningen, hvis du lavede færre.

### Karruseller

Karruseller er sat på pause, fordi de fik 10 til 15 visninger. Lav kun en karrusel, hvis `results/OVERSIGT.md` viser visningstal, og karruseller dér ligger over klip-reels. Så gælder de gamle regler: 5 til 10 slides, tema og `slides` som i `queue/2026-W46/`. Tekst-reels med `cards` eller `slides` som video må aldrig laves. Kvalitetsporten afviser dem.

## 3. Regler der ikke kan forhandles

- Ingen tankestreger, ingen krøllede citationstegn, intet "…"-tegn.
- Ingen tal uden at de står i FACTS.md og i opslagets `facts`-felt.
- Hook i første linje (højst 125 tegn), konkret og uden hilsen eller emoji i starten.
- Højst 3 hashtags, højst 2 emojis, ingen URL i caption. Eneste opfordring er "Link i bio".
- Kun reels i formatet klip. Tekst-reels er slået fra.
- Skriv i du-form, dansk, uden floskler som "i dagens samfund", "rejse", "unlock", "game changer".
- Ingen medicinske, juridiske eller økonomiske løfter. Ingen påstande om at kende brugerens "rigtige" svar.

## 4. Byg og tjek

1. `python3 pipeline/build.py` (kvalitetsporten kører først og stopper ved fejl). Ret teksten, til den passerer. Omgå aldrig porten.
2. `python3 tests/run_tests.py` skal være grøn.
3. Kig på `cover.jpg` for hvert nyt klip, og træk det sidste billede ud af mindst 2 af videoerne. Teksten skal kunne læses mod baggrunden og må ikke løbe ud over kanten. Kan den ikke læses, så skift `stil` eller `bg`.
4. Har build rørt medier for opslag, der allerede er udgivet, så gendan dem med `git checkout -- media/<uge>`.

## 5. Udgiv til køen

Commit `queue/` og `media/` på main med beskeden `Indhold uge <nr>`, og push. Publisering sker af sig selv fra GitHub Actions på de planlagte tidspunkter. Rør aldrig `state/`, `config.json` eller `pipeline/publish.py`, og opret aldrig `PAUSE`.

## 6. Afslut kort

Højst 6 linjer på dansk: hvilke emner og formater du valgte, hvad der ikke blev lavet og hvorfor, og om noget skal afgøres af et menneske. Ingen opremsning af trin.

## Tal styrer valget

Læs `results/OVERSIGT.md` først. Det tal, der tæller mest, er gennemførte tests fra Instagram (afsnittet "Gennemførte tests" fra Umami). Visninger, gemte og delte forklarer, hvorfor det tal går op eller ned. Gruppen "Autopilot, format klip" er de nye reels, og "Alle manuelle opslag" er målestokken.

- Er der visningstal: lav flere klip med de åbninger, baggrunde og stilarter, der ligger højest, og færre af dem i bunden. Skriv i afslutningen, hvad tallene fik dig til at ændre, og om klip-reels ligger på niveau med de manuelle.
- Mangler visningstallene (nøglen har ikke tilladelsen til det), så er likes for få til at styre efter. Hold blandingen ovenfor, og skriv i afslutningen, at visninger mangler.
- Ligger klip-reels efter 3 uger stadig langt under de manuelle, så skriv det tydeligt i afslutningen. Så er det baggrundene, der skal skiftes ud med ægte videoklip i `brand/klip/`, og det kan kun Christian levere.
