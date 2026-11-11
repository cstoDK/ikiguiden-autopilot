# Ikiguiden autopilot

Indhold til Instagram-profilen Ikiguiden bliver skrevet, tegnet og udgivet uden manuelt arbejde.

```
Fredag    ugens generering skriver 7 opslag (1 om dagen kl. 19) i queue/  (brand/WEEKLY_PROMPT.md)
          kvalitetsporten (pipeline/lint.py) afviser alt, der ikke lever op til reglerne
          pipeline/build.py gengiver karruseller (JPEG). Reels er slået fra fra uge 46
Hver 30 min.  GitHub Actions kører pipeline/publish.py og udgiver det, der er forfaldent
Hver 30 min.  samme kørsel sender karrusellerne videre til TikTok (pipeline/tiktok.py), når TikTok er tændt
Hver morgen   pipeline/insights.py henter visninger m.m. til results/OVERSIGT.md (læser kun)
Hver 1. i måneden  pipeline/refresh_token.py forlænger Instagram-nøglen
```

## Mapper

| Sti | Indhold |
| --- | --- |
| `queue/<uge>/*.json` | Opslag: type, tidspunkt, caption, slides eller tekstkort |
| `media/<uge>/<id>/` | Gengivne billeder og video (committes, så Instagram kan hente dem) |
| `state/published.json` | Hvad der er udgivet, sprunget over eller spærret |
| `state/tiktok.json` | Hvad der er sendt til TikTok |
| `brand/` | Stil, eksempler, fakta, ugens opgave |
| `brand/baggrunde/` | Egne billeder til tema `foto` |
| `results/` | Tal fra Instagram, hentet hver morgen |
| `reserve/` | Færdige opslag, der ikke er brugt endnu |
| `pipeline/` | lint, render, build, publish, refresh_token |
| `tests/` | Mock af Instagram og 49 tjek |

## Sikkerhedsnet

- **Kontospærre:** der udgives kun på @ikigaiguiden (`config.json`). Hører nøglen til en anden konto, fx den private profil @christianstoltze, udgives intet. @christianstoltze er desuden spærret i koden uanset config.
- **Kill switch:** opret en tom fil `PAUSE` i roden, så udgives intet. Slet den for at genoptage.
- **Kvalitetsporten:** tankestreger, usynlige tegn, opfundne tal, for mange hashtags, links i caption og for korte eller lange opslag stoppes, før noget gengives eller sendes.
- **Ingen dubletter:** udgivelsen er idempotent. Et opslag, der allerede er udgivet eller har en container, udgives aldrig to gange.
- **Ingen gamle opslag:** er et opslag mere end 18 timer forsinket, springes det over frem for at poste ude af takt.
- **Fejl er synlige:** en fejl får GitHub til at sende en mail og markere kørslen rød.
- **Nøglen lækker ikke:** adgangsnøglen fjernes fra alle fejlbeskeder og logs.

## Engangsopsætning (hos Meta og GitHub)

1. Instagram-profilen skal være en Professional-konto (Creator eller Business).
2. Opret en app hos Meta for developers med produktet "Instagram API with Instagram login", tilføj profilen som testbruger/rolle, og generér en langtidsnøgle (60 dage).
3. Gem nøglen som GitHub secret `IG_ACCESS_TOKEN` (Settings, Secrets and variables, Actions).
4. Valgfrit: gem en GitHub-nøgle med ret til secrets som `GH_PAT`, så nøglen fornyes automatisk hver måned. Uden den skal nøglen genereres igen hvert 60. dag.
5. Aktivér Actions, og kør workflowet "Instagram autopilot" manuelt én gang med knappen Run workflow.

Før trin 3 er alt slukket: publish.py afslutter uden fejl og siger, at autopiloten ikke er tændt.

## TikTok

Karrusellerne sendes også til TikTok som fotokarruseller, med samme billeder og tekst som på Instagram. Reels sendes ikke.

TikToks eget API lader kun godkendte apps poste offentligt, og et værktøj til egne konti kan ikke blive godkendt. Derfor går udgivelsen gennem Zernio, som har en godkendt TikTok-app og er gratis for de første to tilsluttede konti. Før trin 3 herunder er TikTok slukket, og intet sendes.

1. Opret en gratis konto på zernio.com, og tilslut TikTok-profilen.
2. Skriv TikTok-brugernavnet i `config.json` under `tiktok_username` (uden @). Det er kontospærren: der sendes kun til den konto.
3. Lav en API-nøgle hos Zernio, og gem den som GitHub secret `ZERNIO_API_KEY`.
4. Kør workflowet "Tjek TikTok-konto (sender intet)". Det skal svare TIKTOK-KONTO OK.

`tiktok_mode` i `config.json` styrer måden:

- `auto`: opslaget udgives med det samme, og TikTok lægger selv et anbefalet nummer på. Nummeret kan skiftes i appen bagefter.
- `kladde`: opslaget lander i TikTok-indbakken. Du vælger selv lyd og trykker udgiv. TikTok tillader højst 5 ventende kladder pr. døgn.

Et enkelt opslag kan vælge selv med feltet `"tiktok": "kladde"`, og `"tiktok": false` holder det væk fra TikTok. Status står i `state/tiktok.json`. PAUSE-filen, kvalitetsporten og 18-timers-reglen gælder også her.

## Kør lokalt

```
python3 pipeline/build.py           # lint + gengiv
python3 pipeline/publish.py --dry-run --now 2026-11-03T18:10:00+00:00
python3 tests/run_tests.py          # hele pipelinen mod en mock af Instagram
python3 tests/test_tiktok.py         # TikTok-udgivelsen mod en mock af Zernio
```

## Kendte begrænsninger

- Live-kald til Instagram er ikke afprøvet. De er testet mod en mock bygget efter Metas dokumentation, men det første rigtige kørsel er den egentlige prøve.
- Reels (tekst som video) er slået fra fra 10. november 2026, fordi de ikke virkede. Kvalitetsporten afviser nye reels. Kun ægte karruseller (billeder) udgives.
- Musik på karruseller kan ikke sættes på automatisk. Metas lyd-API (`audio_configuration`) gælder kun reels, og Instagram afviser det på karruseller med fejl 2207065 (afprøvet mod kontoen 10. november 2026). publish.py prøver alligevel ved hver udgivelse og udgiver uden musik, når det afvises. Åbner Instagram for det, kommer musikken på af sig selv, og `state/published.json` viser `music.media_audio_type` = MUSIC.
- Slides må aldrig laves om til video for at få lyd på. Det er prøvet og fravalgt.
- Live-kald til Zernio og TikTok er ikke afprøvet. De er testet mod en mock bygget efter Zernios dokumentation. Første rigtige kørsel er den egentlige prøve, så start gerne med `tiktok_mode` sat til `kladde`.
- Hosting af medier sker via raw.githubusercontent.com med jsDelivr som reserve. Repoet skal være offentligt.
- Planlagte workflows i offentlige repos slås fra efter 60 dages inaktivitet. De ugentlige commits holder det i live.
