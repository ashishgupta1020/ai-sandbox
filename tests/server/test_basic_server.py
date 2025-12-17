import threading
import time
import unittest
import http.client
from contextlib import closing

from taskman.server.tasker_server import _UIRequestHandler  # testing internal handler intentionally
from http.server import ThreadingHTTPServer


class _ServerThread:
    """Run ThreadingHTTPServer in a background thread for tests."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.server = ThreadingHTTPServer((host, port), _UIRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.1})
        self.thread.daemon = True

    @property
    def address(self):
        host, port = self.server.server_address
        return host, port

    def start(self):
        self.thread.start()
        # tiny delay to ensure the server is listening before we connect
        time.sleep(0.05)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class TestBasicServer(unittest.TestCase):
    def setUp(self):
        self.srv = _ServerThread()
        self.srv.start()
        self.host, self.port = self.srv.address

    def tearDown(self):
        self.srv.stop()

    def _request(self, path: str):
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request("GET", path)
            resp = conn.getresponse()
            body = resp.read()
            return resp, body

    def test_health_endpoint(self):
        resp, body = self._request("/health")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "application/json; charset=utf-8")
        self.assertIn(b'"status"', body)
        self.assertIn(b'"ok"', body)

    def test_root_serves_index_html(self):
        resp, body = self._request("/")
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.getheader("Content-Type", "").startswith("text/html"))
        # index.html shipped in repo should contain a basic title/header
        self.assertTrue(len(body) > 0)

    def test_static_css_served(self):
        resp, body = self._request("/styles/index.css")
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.getheader("Content-Type", "").startswith("text/css"))
        self.assertTrue(len(body) > 0)

    def test_404_for_missing(self):
        resp, body = self._request("/no-such-file.txt")
        self.assertEqual(resp.status, 404)

    def test_blocks_traversal(self):
        resp, body = self._request("/../../etc/passwd")
        self.assertEqual(resp.status, 400)


if __name__ == "__main__":
    unittest.main()
