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
    if "fejl" in res or not res.get("data"):
        print("me/accounts:", res if "fejl" in res else "ingen sider")
    me = get("https://graph.facebook.com", "me", fields="id,name,instagram_business_account{id,username}")
    print("me:", {k: me.get(k) for k in ("name", "instagram_business_account", "fejl")})
    base_id = json.load(open("config.json"))["instagram_user_id"]
    for navn in ("the_ikigai_guide",):
        d = get("https://graph.facebook.com", base_id, fields=f"business_discovery.username({navn}){{id,username,followers_count}}")
        bd = d.get("business_discovery") or d
        print(f"opslag @{navn}:", bd)
        if isinstance(bd, dict) and bd.get("id"):
            direkte = get("https://graph.facebook.com", bd["id"], fields="id,username")
            print(f"direkte adgang til @{navn}:", direkte)
    perms = get("https://graph.facebook.com", "me/permissions")
    print("tilladelser:", [p.get("permission") for p in perms.get("data", []) if p.get("status") == "granted"] or perms.get("fejl"))
else:
    print("Nøgletype: Instagram-login (én nøgle pr. konto)")
    print(get("https://graph.instagram.com", "me", fields="user_id,username"))
