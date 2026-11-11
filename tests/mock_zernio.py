"""Mock af Zernios API (kun det, tiktok.py bruger) plus statisk medie-hosting.

Henter selv hvert billede, så testen beviser, at adresserne peger på rigtige filer.
"""
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

GOOD_KEY = "sk_TESTKEY"


class Mock:
    def __init__(self):
        self.reset(None)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def reset(self, media_root):
        self.media_root = media_root
        self.calls = []
        self.accounts = [{"_id": "acc1", "platform": "tiktok", "username": "ikigaiguiden"}]
        self.levels = ["PUBLIC_TO_EVERYONE", "SELF_ONLY"]
        self.post_status = "published"   # hvad TikTok svarer på et nyt opslag
        self.later_status = "published"  # hvad et opslag undervejs ender som
        self.fail_first = 0              # antal 500-svar før det lykkes
        self.posts_by_key = {}
        self.posts = {}
        self.n = 0

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}"

    def created(self):
        return [c for c in self.calls if c["method"] == "POST" and c["path"] == "posts"]

    def _handler(self):
        mock = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj=None, raw=None, ctype="application/json"):
                body = raw if raw is not None else json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _auth(self):
                if self.headers.get("Authorization") != f"Bearer {GOOD_KEY}":
                    self._send(401, {"error": "Invalid API key", "code": "invalid_credentials"})
                    return False
                return True

            def do_GET(self):
                u = urlparse(self.path)
                if u.path.startswith("/media/"):
                    f = Path(mock.media_root) / u.path[len("/media/"):]
                    if not f.is_file():
                        return self._send(404, raw=b"nej", ctype="text/plain")
                    data = f.read_bytes()
                    if self.headers.get("Range"):
                        return self._send(206, raw=data[:1024], ctype="image/jpeg")
                    return self._send(200, raw=data, ctype="image/jpeg")
                if not self._auth():
                    return
                parts = u.path.strip("/").split("/")[1:]
                mock.calls.append({"method": "GET", "path": "/".join(parts),
                                   "params": {k: v[0] for k, v in parse_qs(u.query).items()}})
                if parts == ["accounts"]:
                    return self._send(200, {"accounts": mock.accounts, "hasAnalyticsAccess": False})
                if len(parts) == 4 and parts[0] == "accounts" and parts[2:] == ["tiktok", "creator-info"]:
                    return self._send(200, {"creator": {"nickname": "Ikiguiden", "canPostMore": True},
                                            "privacyLevels": [{"value": v, "label": v} for v in mock.levels]})
                if len(parts) == 2 and parts[0] == "posts":
                    post = mock.posts.get(parts[1])
                    if not post:
                        return self._send(404, {"error": "Post not found"})
                    if post["status"] == "publishing":
                        post["status"] = post["platforms"][0]["status"] = mock.later_status
                        if mock.later_status == "failed":
                            post["platforms"][0]["errorMessage"] = "Billedet blev afvist"
                        else:
                            post["platforms"][0]["platformPostUrl"] = f"https://www.tiktok.com/@ikigaiguiden/photo/{parts[1]}"
                    return self._send(200, {"post": post})
                self._send(404, {"error": "Ukendt endpoint"})

            def do_POST(self):
                u = urlparse(self.path)
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n).decode() or "{}")
                if not self._auth():
                    return
                parts = u.path.strip("/").split("/")[1:]
                key = self.headers.get("Idempotency-Key")
                mock.calls.append({"method": "POST", "path": "/".join(parts), "body": body, "key": key})
                if parts != ["posts"]:
                    return self._send(404, {"error": "Ukendt endpoint"})
                if mock.fail_first > 0:
                    mock.fail_first -= 1
                    return self._send(500, {"error": "Midlertidig fejl"})
                if key in mock.posts_by_key:
                    return self._send(409, {"error": "Duplicate request", "existingPostId": mock.posts_by_key[key]})
                for m in body.get("mediaItems", []):
                    try:
                        with urllib.request.urlopen(m["url"], timeout=10) as r:
                            if r.status != 200:
                                raise ValueError(r.status)
                    except Exception:
                        return self._send(400, {"error": "Media URL kunne ikke hentes"})
                ids = {a["_id"] for a in mock.accounts}
                if any(p.get("accountId") not in ids for p in body.get("platforms", [])):
                    return self._send(400, {"error": "Ukendt konto"})
                mock.n += 1
                pid = f"post{mock.n}"
                draft = body.get("tiktokSettings", {}).get("draft")
                status = "published" if draft else mock.post_status
                plat = {"platform": "tiktok", "status": status, "platformPostUrl": None}
                if status == "failed":
                    plat["errorMessage"] = "TikTok direct posting is at capacity right now"
                post = {"_id": pid, "status": status, "platforms": [plat]}
                mock.posts[pid] = post
                mock.posts_by_key[key] = pid
                self._send(207 if status == "failed" else 201, {"message": "ok", "post": post})

        return H
