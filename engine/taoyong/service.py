"""Loopback-only JSON service that exposes the TaoYongStudio engine to the
Tauri shell.

Security model
--------------
* Binds 127.0.0.1 only — never reachable from the network.
* Requires a bearer token that is generated per launch and handed to the Rust
  side over the process' stdout.
* Rejects requests whose Host header is not a loopback address (anti
  DNS-rebinding).
"""
import argparse
import json
import os
import socket
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import api as apimod

TOKEN = ""
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}


class Handler(BaseHTTPRequestHandler):
    server_version = "TaoYongStudioEngine/2.0"

    # -------------------------------------------------------------- helpers
    def log_message(self, fmt, *args):  # quieter console
        if os.environ.get("TAOYONG_VERBOSE"):
            sys.stderr.write("[engine] " + (fmt % args) + "\n")

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0].strip()
        return host in LOOPBACK_HOSTS

    def _auth_ok(self):
        got = self.headers.get("X-TAOYONG-TOKEN") or ""
        return bool(TOKEN) and got == TOKEN

    def _send(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(raw)
        except Exception:
            pass

    def _dispatch(self, method):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        if not self._host_ok():
            self._send(403, {"error": "ปฏิเสธคำขอจากโฮสต์ที่ไม่ใช่ loopback"})
            return
        if not self._auth_ok():
            self._send(401, {"error": "โทเคนไม่ถูกต้อง"})
            return

        handler = apimod.ROUTES.get((method, path))
        if handler is None:
            self._send(404, {"error": "ไม่พบเส้นทาง %s %s" % (method, path)})
            return

        body = {}
        if method in ("POST", "PUT"):
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length > 0:
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw.decode("utf-8"))
                except Exception as e:
                    self._send(400, {"error": "JSON ที่ส่งมาไม่ถูกต้อง: %s" % e})
                    return
            if not isinstance(body, dict):
                body = {}

        try:
            result = handler(query, body)
        except Exception as e:
            detail = "%s" % e
            sys.stderr.write("[engine] %s %s -> %s\n%s\n" % (method, path, detail,
                                                              traceback.format_exc(limit=6)))
            self._send(400, {"error": detail})
            return
        if not isinstance(result, dict):
            result = {"ok": True, "result": result}
        self._send(200, result)

    # -------------------------------------------------------------- verbs
    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")


def serve(host="127.0.0.1", port=0, token=None):
    global TOKEN
    TOKEN = token or os.environ.get("TAOYONG_TOKEN", "")

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    httpd = Server((host, port), Handler)
    actual_port = httpd.server_address[1]
    # tell the Rust side where to connect
    sys.stdout.write(json.dumps({"port": actual_port, "token": TOKEN, "host": host}) + "\n")
    sys.stdout.flush()
    try:
        httpd.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="TaoYongStudio engine service")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--token", default="")
    args = ap.parse_args(argv)
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("refusing to bind a non-loopback address: %s" % args.host, file=sys.stderr)
        return 2
    serve(args.host, args.port, args.token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
