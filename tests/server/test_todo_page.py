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

    def _get_json(self, path: str):
        status, body = self._get(path)
        return status, json.loads(body)

    def _post_json(self, path: str, payload: dict):
        status, body = self._post(path, payload)
        return status, json.loads(body)

    def test_get_empty_list(self):
        status, body = self._get("/api/todo")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data.get("items"), [])

    def test_todo_flow_endpoints(self):
        # add
        status, data = self._post_json("/api/todo/add", {"title": "Write tests", "priority": "low"})
        self.assertEqual(status, 200)
        todo_id = data["item"]["id"]
        # list
        status2, data2 = self._get_json("/api/todo")
        self.assertEqual(status2, 200)
        self.assertEqual(len(data2.get("items") or []), 1)
        self.assertFalse(data2["items"][0].get("done"))
        # mark done
        status3, data3 = self._post_json("/api/todo/mark", {"id": todo_id, "done": True})
        self.assertEqual(status3, 200)
        self.assertTrue(data3.get("done"))
        # edit
        status4, data4 = self._post_json("/api/todo/edit", {"id": todo_id, "title": "After", "priority": "high"})
        self.assertEqual(status4, 200)
        self.assertEqual(data4["item"]["priority"], "high")
        # final list
        status5, data5 = self._get_json("/api/todo")
        self.assertEqual(status5, 200)
        items = data5.get("items") or []
        self.assertEqual(items[0]["title"], "After")
        self.assertTrue(items[0]["done"])


if __name__ == "__main__":
    unittest.main()
