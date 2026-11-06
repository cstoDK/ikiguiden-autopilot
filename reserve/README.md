# Reserve

Færdige opslag, der blev skrevet, men ikke kom i køen. Pipelinen rører dem ikke, fordi den kun læser `queue/`.

Ugens generering må flytte et af dem til `queue/<uge>/`, give det nyt id, filnavn, `publish_at` og `tema`, og så køre build og tests som normalt.
