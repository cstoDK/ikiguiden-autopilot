#!/usr/bin/env python3
"""Forlænger Instagram-adgangsnøglen (gælder 60 dage). Kører en gang om måneden.

Er hemmeligheden GH_PAT sat (en GitHub-nøgle med ret til at skrive secrets), gemmes den
nye nøgle automatisk som IG_ACCESS_TOKEN. Ellers forlænges nøglen kun hos Meta, og du
får en fejlmail fra GitHub, når den til sidst udløber.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
if not token:
    print("Ingen nøgle at forny. Autopiloten er ikke tændt endnu.")
    sys.exit(0)

url = "https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode(
    {"grant_type": "ig_refresh_token", "access_token": token})
try:
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.loads(r.read().decode())
except urllib.error.HTTPError as e:
    print(f"Fornyelsen blev afvist (HTTP {e.code}). Nøglen skal genereres igen hos Meta.")
    sys.exit(1)

new = data.get("access_token", "")
days = round(data.get("expires_in", 0) / 86400)
print(f"Nøglen er forlænget og gælder nu ca. {days} dage.")
pat = os.environ.get("GH_PAT", "").strip()
if new and pat and new != token:
    print(f"::add-mask::{new}")
    res = subprocess.run(["gh", "secret", "set", "IG_ACCESS_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
                         input=new.encode(), env={**os.environ, "GH_TOKEN": pat}, capture_output=True)
    if res.returncode != 0:
        print("Kunne ikke gemme den nye nøgle som secret.")
        sys.exit(1)
    print("Den nye nøgle er gemt som secret.")
elif not pat:
    print("GH_PAT er ikke sat, så en ny nøgle gemmes ikke automatisk.")
