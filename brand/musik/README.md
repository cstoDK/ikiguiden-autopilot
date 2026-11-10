# Musik til karruseller

Instagrams API tillader ikke musik fra Instagrams eget bibliotek på karruseller (fejl 2207065, afprøvet 10. november 2026). Derfor udgives karruseller med musik som ægte karruseller, hvor hver slide er en kort video med et af numrene her under. Man swiper stadig, og nummeret fortsætter fra slide til slide.

Alle numre er af Kevin MacLeod (incompetech.com) under licensen Creative Commons Attribution 4.0. Licensen kræver kreditering, så publish.py tilføjer automatisk en linje nederst i captionen, fx "Musik: Dreamer af Kevin MacLeod (incompetech.com), CC BY 4.0". Fjern den ikke.

`liste.txt` styrer hvilke numre der bruges (fil|titel). Nummeret vælges ud fra opslagets id. Et bestemt nummer kan vælges med feltet `"musik": "dreamer.mp3"` i opslaget, og `"musik": false` slår musikken fra.
