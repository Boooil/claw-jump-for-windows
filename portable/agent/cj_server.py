import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

from cj_debug import dbg


class _RequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/healthz":
            self._respond(200, {"ok": True})
        else:
            self._respond(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/event":
            self._respond(404, {"error": "not_found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._respond(400, {"error": "missing_body"})
            return

        t_recv = time.time()
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid_json"})
            return

        if not isinstance(payload, dict):
            self._respond(400, {"error": "invalid_payload"})
            return

        event_name = payload.get("event", "?")
        dbg("server", "received event=%s session=%s", event_name, payload.get("sessionId", ""))

        callback = self.server.callback
        if callback:
            callback(payload)

        self._respond(202, {"accepted": True})

    def _respond(self, status_code, body_obj):
        body = json.dumps(body_obj).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)


class EventServer:
    """Lightweight HTTP server that accepts JSON events on POST /event."""

    def __init__(self, port=47653, callback=None):
        self._port = port
        self._server = None
        self._thread = None
        self._running = False
        self.callback = callback

    @property
    def port(self):
        return self._port

    def start(self):
        self._server = HTTPServer(("127.0.0.1", self._port), _RequestHandler)
        self._server.callback = self.callback
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._running = True

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None
        self._running = False
