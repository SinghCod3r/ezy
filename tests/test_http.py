import json
import sys, os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send_json(self, status, payload, headers=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/echo-query"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            self._send_json(200, {"query": {k: v[0] for k, v in qs.items()}})
        elif self.path == "/headers":
            self._send_json(200, {"authorization": self.headers.get("Authorization", "")})
        elif self.path == "/not-found":
            self._send_json(404, {"error": "not found"})
        elif self.path == "/server-error":
            self._send_json(500, {"error": "boom"})
        elif self.path == "/slow":
            time.sleep(2)
            self._send_json(200, {"ok": True})
        elif self.path == "/bad-json":
            body = b"{not valid json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/download":
            body = b"file contents for download test"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send_json(200, {"ok": True, "path": self.path})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        self._send_json(201, {"received": data})

    def do_DELETE(self):
        self._send_json(200, {"deleted": True})


@pytest.fixture(scope="module")
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def test_get_json(ezy, server):
    ezy.run(f'response = get "{server}/ping"\nsay response.status\nsay response.json.ok\n')
    assert ezy.lines == ["200", "true"]


def test_get_is_successful(ezy, server):
    ezy.run(f'response = get "{server}/ping"\nsay response is successful\n')
    assert ezy.lines == ["true"]


def test_get_404_is_failed(ezy, server):
    ezy.run(f'response = get "{server}/not-found"\nsay response.status\nsay response is failed\n')
    assert ezy.lines == ["404", "true"]


def test_get_500(ezy, server):
    ezy.run(f'response = get "{server}/server-error"\nsay response.status\n')
    assert ezy.lines == ["500"]


def test_get_with_query_params(ezy, server):
    src = f'response = get "{server}/echo-query" with query {{"q": "printer", "page": 2}}\nsay response.json.query.q\n'
    ezy.run(src)
    assert ezy.lines == ["printer"]


def test_get_with_header(ezy, server):
    src = f'response = get "{server}/headers" with header {{"Authorization": "Bearer TOKEN"}}\nsay response.json.authorization\n'
    ezy.run(src)
    assert ezy.lines == ["Bearer TOKEN"]


def test_post_json_body(ezy, server):
    src = f'response = post "{server}/users" send json {{"name": "Ayush"}}\nsay response.status\nsay response.json.received.name\n'
    ezy.run(src)
    assert ezy.lines == ["201", "Ayush"]


def test_delete_verb(ezy, server):
    ezy.run(f'response = delete "{server}/users/1"\nsay response.json.deleted\n')
    assert ezy.lines == ["true"]


def test_malformed_json_response_raises(ezy, server):
    from ezy.errors import EzyRuntimeError
    with pytest.raises(EzyRuntimeError) as exc:
        ezy.run(f'response = get "{server}/bad-json"\nsay response.json\n')
    assert exc.value.error_type == "JsonError"


def test_timeout(ezy, server):
    src = f'response = get "{server}/slow" with timeout 1 seconds\nsay response.ok\nsay response.error\n'
    ezy.run(src)
    assert ezy.lines[0] == "false"
    assert "timed out" in ezy.lines[1]


def test_connection_failure(ezy):
    # Nothing listens on this port.
    ezy.run('response = get "http://127.0.0.1:1"\nsay response.ok\n')
    assert ezy.lines == ["false"]


def test_dns_failure(ezy):
    ezy.run('response = get "http://this-domain-should-not-resolve.invalid"\nsay response.ok\n')
    assert ezy.lines == ["false"]


def test_download_file(ezy, server, tmp_path):
    dest = tmp_path / "out.bin"
    ezy.run(f'download "{server}/download"\nsave as "{dest}"\n')
    assert dest.read_bytes() == b"file contents for download test"


def test_download_failure_raises(ezy, server):
    from ezy.errors import EzyRuntimeError
    with pytest.raises(EzyRuntimeError) as exc:
        ezy.run(f'download "{server}/not-found"\nsave as "/tmp/should_not_exist.bin"\n')
    assert exc.value.error_type == "HttpError"


def test_http_get_url_display(ezy, server):
    ezy.run(f'response = get "{server}/ping"\nsay response.url\n')
    assert ezy.lines[0].startswith(server)
