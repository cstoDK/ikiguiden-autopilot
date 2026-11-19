# Ikiguiden autopilot

Indhold til Instagram-profilen Ikiguiden bliver skrevet, tegnet og udgivet uden manuelt arbejde.

```
Fredag    ugens generering skriver 7 klip-reels (1 om dagen kl. 19) i queue/  (brand/WEEKLY_PROMPT.md)
          kvalitetsporten (pipeline/lint.py) afviser alt, der ikke lever op til reglerne
          pipeline/build.py gengiver klip-reels (MP4 1080x1920) og eventuelle karruseller (JPEG)
Hver 30 min.  GitHub Actions kører pipeline/publish.py og udgiver det, der er forfaldent
Hvert kvarter pipeline/comments.py sender testen som besked til dem, der kommenterer TEST eller ARKETYPE
Hver morgen   pipeline/insights.py henter visninger m.m. til results/OVERSIGT.md (læser kun)
Hver 1. i måneden  pipeline/refresh_token.py forlænger Instagram-nøglen
```

## Mapper

| Sti | Indhold |
| --- | --- |
| `queue/<uge>/*.json` | Opslag: type, tidspunkt, caption, slides eller tekstkort |
| `media/<uge>/<id>/` | Gengivne billeder og video (committes, så Instagram kan hente dem) |
| `state/published.json` | Hvad der er udgivet, sprunget over eller spærret |
| `brand/` | Stil, eksempler, fakta, ugens opgave |
| `brand/baggrunde/` | Egne billeder, baggrund i klip-reels (og tema `foto`) |
| `brand/klip/` | Egne videoklip, baggrund i klip-reels. Bruges før billederne, når der ligger nogen |
| `results/` | Tal fra Instagram, hentet hver morgen |
| `reserve/` | Færdige opslag, der ikke er brugt endnu |
| `pipeline/` | lint, render, build, publish, refresh_token |
| `tests/` | Mock af Instagram og 79 tjek |

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
4. Til beskeder ved kommentarer og visningstal skal nøglen også have `instagram_business_manage_insights`, `instagram_business_manage_comments` og `instagram_business_manage_messages`, og beskedadgang for forbundne værktøjer skal være slået til i Instagram-appen. Indtil da står `state/dm.json` på "mangler_tilladelse", og intet fejler.
5. Gem en API-nøgle fra Umami som secret `UMAMI_API_KEY`, så `results/OVERSIGT.md` viser gennemførte tests fra Instagram.
6. Valgfrit: gem en GitHub-nøgle med ret til secrets som `GH_PAT`, så nøglen fornyes automatisk hver måned. Uden den skal nøglen genereres igen hvert 60. dag.
7. Aktivér Actions, og kør workflowet "Instagram autopilot" manuelt én gang med knappen Run workflow.

Før trin 3 er alt slukket: publish.py afslutter uden fejl og siger, at autopiloten ikke er tændt.

## Kør lokalt

```
python3 pipeline/build.py           # lint + gengiv
python3 pipeline/publish.py --dry-run --now 2026-11-03T18:10:00+00:00
python3 tests/run_tests.py          # hele pipelinen mod en mock af Instagram
```

## Kendte begrænsninger

- Live-kald til Instagram er ikke afprøvet. De er testet mod en mock bygget efter Metas dokumentation, men det første rigtige kørsel er den egentlige prøve.
- Strategi fra 15. november 2026: autopiloten laver klip-reels (`"format": "klip"`), der ligner Christians egne reels: eget billede eller klip i fuld skærm, 2 til 4 korte linjer, 6 til 10 sekunder. De manuelle reels fik typisk 120 til 250 visninger, autopilotens tekstkort og karruseller 10 til 60. Karruseller er sat på pause og ligger i `reserve/`.
- Tekst-reels (tekstkort eller slides som video) er slået fra og afvises af kvalitetsporten. Slides må aldrig laves om til video.
- Klip-reels får musik fra Instagrams bibliotek ved udgivelsen (`audio_configuration`). Afviser Instagram nummeret, udgives klippet med autopilotens egen rolige beat. Karruseller kan ikke få musik automatisk (fejl 2207065).
- Uden videoklip i `brand/klip/` er baggrunden et stillbillede med langsom zoom. Ægte video virker bedre.
- Visningstal kræver, at nøglen har tilladelsen `instagram_business_manage_insights`. Uden den viser `results/OVERSIGT.md` kun likes, og autopiloten kan ikke selv se, om strategien virker.
- Hosting af medier sker via raw.githubusercontent.com med jsDelivr som reserve. Repoet skal være offentligt.
- Planlagte workflows i offentlige repos slås fra efter 60 dages inaktivitet. De ugentlige commits holder det i live.
