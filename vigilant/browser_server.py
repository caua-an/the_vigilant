"""Comunicação local com as extensões dos navegadores."""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

PORT = 47653


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    def respond(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        origin = self.headers.get('Origin', '')
        if origin.startswith(('chrome-extension://', 'moz-extension://')):
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path != '/state':
            self.send_error(404)
            return
        with self.server.state_lock:
            domains = list(self.server.domains)
            exceptions = list(self.server.exceptions)
            name = parse_qs(url.query).get('browser', [''])[0]
            origin = self.headers.get('Origin', '')
            if ((not origin and name in ('brave', 'chrome', 'firefox')) or
                    (name == 'firefox' and origin.startswith('moz-extension://')) or
                    (name in ('brave', 'chrome') and origin.startswith('chrome-extension://'))):
                self.server.last_seen[name] = time.monotonic()
        self.respond({'domains': domains, 'exceptions': exceptions})

    def do_POST(self):
        if self.path != '/attempt' or not self.headers.get('Origin', '').startswith(('chrome-extension://', 'moz-extension://')):
            self.send_error(403)
            return
        self.server.events.put('attempt')
        self.respond({'ok': True})

    def log_message(self, format, *args):
        pass
