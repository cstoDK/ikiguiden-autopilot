#!/usr/bin/env python3
"""Viser hvilke Instagram-konti nøglen kan nå (brugernavn og id). Udgiver intet og viser aldrig nøglen."""
import json, os, sys, urllib.parse, urllib.request

token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
if not token:
    print("IG_ACCESS_TOKEN mangler"); sys.exit(0)
v = os.environ.get("IG_API_VERSION", "v23.0")

def get(base, path, **params):
    params["access_token"] = token
    url = f"{base}/{v}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300].replace(token, "***")
        return {"fejl": e.code, "svar": body}

if token.startswith("EAA"):
    print("Nøgletype: Facebook")
    res = get("https://graph.facebook.com", "me/accounts", fields="name,instagram_business_account{id,username}", limit=50)
    for side in res.get("data", []):
        ig = side.get("instagram_business_account") or {}
        print(f"Facebook-side: {side.get('name')} -> Instagram: @{ig.get('username', '-')} (id {ig.get('id', '-')})")
    if "fejl" in res:
        print(res)
else:
    print("Nøgletype: Instagram-login (én nøgle pr. konto)")
    print(get("https://graph.instagram.com", "me", fields="user_id,username"))
