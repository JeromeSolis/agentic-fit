import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from solution import fetch_user_name


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/users/1":
            body = json.dumps({"name": "Ada"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture()
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_returns_name(server):
    assert fetch_user_name(server, 1) == "Ada"


def test_raises_on_missing(server):
    with pytest.raises(ValueError):
        fetch_user_name(server, 999)
