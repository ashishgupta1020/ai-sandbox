import http.client
import socket
import threading
import time
import unittest
from contextlib import closing

from taskman.tasker_server import start_server


def _pick_free_port(host: str = "127.0.0.1") -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind((host, 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


class TestStartUI(unittest.TestCase):
    def test_start_and_exit(self):
        host = "127.0.0.1"
        port = _pick_free_port(host)

        t = threading.Thread(target=start_server, kwargs={"host": host, "port": port})
        t.daemon = True
        t.start()

        # Wait for the server to come up
        deadline = time.time() + 3.0
        connected = False
        while time.time() < deadline:
            try:
                with closing(http.client.HTTPConnection(host, port, timeout=0.25)) as conn:
                    conn.request("GET", "/health")
                    resp = conn.getresponse()
                    body = resp.read()
                    if resp.status == 200:
                        connected = True
                        break
            except Exception:
                time.sleep(0.05)
        self.assertTrue(connected, "UI server did not start in time")

        # Ask it to exit gracefully
        with closing(http.client.HTTPConnection(host, port, timeout=1)) as conn:
            conn.request("POST", "/api/exit", body=b"{}", headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            # Do not read body to avoid races during shutdown
            self.assertEqual(resp.status, 200)

        # Server thread should exit shortly
        t.join(timeout=2)
        self.assertFalse(t.is_alive(), "UI server thread did not stop")


if __name__ == "__main__":
    unittest.main()
