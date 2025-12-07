import http.client
import json
import shutil
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from http.server import ThreadingHTTPServer

from taskman.server import tasker_server
from taskman.server.todo.todo_api import TodoAPI
from taskman.server.todo.todo_store import TodoStore
from taskman.server.tasker_server import _UIRequestHandler


class _ServerThread:
    def __init__(self, handler_cls=_UIRequestHandler):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.1})
        self.thread.daemon = True

    @property
    def address(self):
        return self.server.server_address

    def start(self):
        self.thread.start()
        time.sleep(0.05)

    def stop(self):
        try:
            self.server.shutdown()
        finally:
            self.server.server_close()
            self.thread.join(timeout=2)


class TestTodoServerEndpoints(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="taskman-todo-server-")
        self.db_path = Path(self.tmpdir) / "todo.db"
        self.orig_todo_api = tasker_server._todo_api
        tasker_server._todo_api = TodoAPI(store_factory=lambda: TodoStore(db_path=self.db_path))

        self.srv = _ServerThread()
        self.srv.start()
        self.host, self.port = self.srv.address

    def tearDown(self):
        self.srv.stop()
        tasker_server._todo_api = self.orig_todo_api
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _get(self, path: str):
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request("GET", path)
            resp = conn.getresponse()
            return resp.status, resp.read()

    def _post(self, path: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Content-Length": str(len(data))}
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request("POST", path, body=data, headers=headers)
            resp = conn.getresponse()
            return resp.status, resp.read()

    def test_get_empty_list(self):
        status, body = self._get("/api/todo")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data.get("items"), [])

    def test_add_and_fetch(self):
        status, body = self._post(
            "/api/todo/add",
            {"title": "Write tests", "due_date": "2024-10-10", "priority": "high", "people": ["Alex"]},
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("item", {}).get("title"), "Write tests")

        status2, body2 = self._get("/api/todo")
        self.assertEqual(status2, 200)
        items = json.loads(body2).get("items") or []
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("due_date"), "2024-10-10")

    def test_add_requires_title(self):
        status, body = self._post("/api/todo/add", {"note": "missing"})
        self.assertEqual(status, 400)
        data = json.loads(body)
        self.assertIn("error", data)

    def test_mark_done_endpoint(self):
        # create item
        status, body = self._post("/api/todo/add", {"title": "Finish", "done": False})
        self.assertEqual(status, 200)
        todo_id = json.loads(body)["item"]["id"]

        # mark done
        status2, body2 = self._post("/api/todo/mark", {"id": todo_id, "done": True})
        self.assertEqual(status2, 200)
        data2 = json.loads(body2)
        self.assertTrue(data2.get("ok"))
        self.assertTrue(data2.get("done"))

        # verify via GET
        status3, body3 = self._get("/api/todo")
        self.assertEqual(status3, 200)
        items = json.loads(body3).get("items") or []
        self.assertTrue(items[0].get("done"))


if __name__ == "__main__":
    unittest.main()
