# Weekly task: next week's content for @the_ikigai_guide (English)

You run without a human reader. Make reasonable choices, say which at the top of your final message, and only stop if something cannot be undone.

This profile shares the engine with the Danish @ikigaiguiden but has its own folder: everything lives in `profiles/en/` (queue, media, state, results, config). Backgrounds and clips are shared in `brand/baggrunde/` and `brand/klip/` in the repo root. Build and test with `AUTOPILOT_PROFILE=en` in front of every command.

## 1. Read first

- `profiles/en/brand/ARCHETYPES.md`: the 12 archetypes. Spell the names exactly like that.
- `profiles/en/brand/FACTS.md`: the only facts allowed.
- `brand/STYLE.md` and `brand/EKSEMPLER.md`: the Danish voice. Use the same tone in English: short, honest, a bit funny, never preachy.
- `profiles/en/queue/` and `profiles/en/state/published.json`: do not repeat topics, hooks or first lines.
- `profiles/en/results/OVERSIGT.md`: numbers per post (fetched daily). Let them steer the week.

## 2. Make 7 clip reels for next week (Monday to Sunday, one a day at 21:00)

Folder `profiles/en/queue/<ISO week>/`, files `01-monday-2100-reel.json` and so on, id `<week>-<day>-2100-reel` (English day names). Copy the structure from `profiles/en/queue/2026-W49/`. `publish_at` in Europe/Copenhagen with offset (+01:00 in winter, +02:00 in summer). `"dm": "arketype"` on every post.

- The theme is the archetypes from the test: status, what people really want, how each archetype acts in everyday life (work, school, friends, relationships). Use both the men's and the women's names across the week.
- `lines`: 2 to 4 short lines, max 70 characters each and max 34 words in total. Line 1 must stop a stranger and must not mention the test, the profile, ikigai or link in bio.
- `[[word]]` highlights one word. At most once per clip. No emojis on the clip.
- Caption: hook in the first line, the honest point in 2 to 4 short lines (max about 400 characters), a question people can answer, and finally "Comment ARCHETYPE and I'll send you the test 📩". Max 3 hashtags, max 2 emojis, no URL.
- `bg`: one of the clips in `brand/klip/` (preferred) or images in `brand/baggrunde/`. Never the same background twice in a week. `stil`: `hvid`, `sort` or `ren` (white text with shadow, only on calm or dark footage). Never the same style two days in a row.
- At least 4 different openings in a week: recognition ("The Rebel in a meeting"), choice ("King. Explorer. Jester."), contrast ("The Magician vs the Idealist"), Pov, observation.
- No numbers unless they are in FACTS.md and in the post's `facts` field. "12 archetypes" needs `"facts": ["12 archetypes"]`.
- No em dashes, no curly quotes, no "…". No clichés ("journey", "unlock", "game changer", "in today's world"). No claims that the test knows your "true self".

## 3. Build and check

1. `AUTOPILOT_PROFILE=en python3 pipeline/build.py` (the quality gate runs first). Fix the text until it passes. Never go around the gate.
2. `python3 tests/run_tests.py` must be green.
3. Look at `cover.jpg` for each new clip. The text must be readable against the background.
4. If build touched media for posts that are already published, restore them with `git checkout -- profiles/en/media/<week>`.

## 4. Commit

Commit `profiles/en/queue/` and `profiles/en/media/` on main with the message `English content week <nr>`, and push. Never touch `profiles/en/state/`, `profiles/en/config.json` or `pipeline/publish.py`, and never create `PAUSE`.

## 5. Finish

At most 6 lines in Danish: which topics and formats you chose, what was not made and why.
