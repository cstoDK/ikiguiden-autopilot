"""Mock af Instagram API with Instagram Login (kun det, publisheren bruger) plus statisk medie-hosting.

Efterligner den dokumenterede rækkefølge: container -> status_code FINISHED -> media_publish.
Henter selv image_url/video_url, så testen beviser, at adresserne peger på rigtige filer.
"""
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

GOOD_TOKEN = "TESTTOKEN"
FB_TOKEN = "EAATESTTOKEN"
IG_ID = "17841439605652106"
CTYPES = {".jpg": "image/jpeg", ".mp4": "video/mp4"}


class Mock:
    def __init__(self):
        self.reset(None)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def reset(self, media_root):
        self.media_root = media_root
        self.calls = []
        self.bad_alt = False
        self.music = False
        self.octet_mp4 = False
        self.n = 0
        self.containers = {}
        self.published = set()
        self.polls = {}
        self.username = "ikigaiguiden"
        self.uid = IG_ID

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}"

    def posts(self, suffix):
        return [c for c in self.calls if c["method"] == "POST" and c["path"].endswith(suffix)]

    def _handler(self):
        mock = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj=None, raw=None, ctype="application/json", extra=None):
                body = raw if raw is not None else json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _err(self, msg, code, http=400):
                self._send(http, {"error": {"message": msg, "code": code}})

            def _auth(self, params):
                if params.get("access_token") not in (GOOD_TOKEN, FB_TOKEN):
                    self._err("Error validating access token: Session has expired", 190, 401)
                    return False
                return True

            def do_GET(self):
                u = urlparse(self.path)
                if u.path.startswith("/media/"):
                    f = Path(mock.media_root) / u.path[len("/media/"):]
                    if not f.is_file():
                        return self._send(404, raw=b"nej", ctype="text/plain")
                    data = f.read_bytes()
                    ctype = CTYPES.get(f.suffix, "application/octet-stream")
                    if mock.octet_mp4 and f.suffix == ".mp4":
                        ctype = "application/octet-stream"
                    rng = self.headers.get("Range")
                    if rng:
                        return self._send(206, raw=data[:1024], ctype=ctype)
                    return self._send(200, raw=data, ctype=ctype)
                params = {k: v[0] for k, v in parse_qs(u.query).items()}
                if not self._auth(params):
                    return
                parts = u.path.strip("/").split("/")[1:]
                mock.calls.append({"method": "GET", "path": "/".join(parts), "params": {k: v for k, v in params.items() if k != "access_token"}})
                fields = params.get("fields", "")
                if parts == ["me"]:
                    if params.get("access_token") == FB_TOKEN:
                        return self._send(200, {"id": "systemuser1", "name": "System User"})
                    return self._send(200, {"user_id": mock.uid, "username": mock.username})
                cid = parts[0]
                if parts == ["ig_audio"]:
                    if not mock.music:
                        return self._err("Ukendt objekt", 100)
                    return self._send(200, {"audio": [{"audio_id": "777", "title": "Rolig", "display_artist": "Test",
                                                       "duration_in_ms": 120000}]})
                if "media_audio_type" in fields:
                    return self._send(200, {"media_audio_type": "MUSIC" if mock.music else "ORIGINAL"})
                if "username" in fields:
                    if cid != mock.uid:
                        return self._err("Ukendt objekt", 100)
                    return self._send(200, {"id": mock.uid, "username": mock.username})
                if "permalink" in fields:
                    return self._send(200, {"permalink": f"https://www.instagram.com/p/{cid}/"})
                mock.polls[cid] = mock.polls.get(cid, 0) + 1
                if cid.startswith("r") and mock.polls[cid] == 1:
                    return self._send(200, {"status_code": "IN_PROGRESS"})
                return self._send(200, {"status_code": "FINISHED"})

            def do_POST(self):
                u = urlparse(self.path)
                n = int(self.headers.get("Content-Length", 0))
                params = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()}
                if not self._auth(params):
                    return
                parts = u.path.strip("/").split("/")[1:]
                clean = {k: v for k, v in params.items() if k != "access_token"}
                mock.calls.append({"method": "POST", "path": "/".join(parts), "params": clean})
                if parts[-1] == "media":
                    if mock.bad_alt and "alt_text" in params:
                        return self._err("Invalid parameter alt_text", 100)
                    media_url = params.get("image_url") or params.get("video_url")
                    if media_url:
                        try:
                            with urllib.request.urlopen(media_url, timeout=10) as r:
                                if r.status != 200:
                                    raise ValueError(r.status)
                        except Exception:
                            return self._err("Media URL kunne ikke hentes", 9004)
                    mock.n += 1
                    if params.get("media_type") == "REELS":
                        cid = f"r{mock.n}"
                    elif params.get("media_type") == "CAROUSEL":
                        ids = params.get("children", "").split(",")
                        if not ids or any(i not in mock.containers for i in ids):
                            return self._err("Ukendt child-container", 100)
                        cid = f"k{mock.n}"
                    else:
                        cid = f"c{mock.n}"
                    mock.containers[cid] = params
                    return self._send(200, {"id": cid})
                if parts[-1] == "media_publish":
                    cid = params.get("creation_id")
                    if cid in mock.published:
                        return self._err("Mediet er allerede udgivet", 9007)
                    mock.published.add(cid)
                    mock.n += 1
                    return self._send(200, {"id": f"m{mock.n}"})
                self._err("Ukendt endpoint", 100, 404)

        return H

    def close(self):
        self.httpd.shutdown()
