import os
import shutil
import threading
import time
import http.client
import tempfile
from pathlib import Path
from contextlib import closing

from taskman.client.api_client import TaskmanApiClient
from taskman.server.project_manager import ProjectManager
from taskman.server.tasker_server import start_server
from taskman.config import get_data_store_dir, set_data_store_dir


class _ServerThread:
    def __init__(self, host: str, port: int):
        self.thread = threading.Thread(target=start_server, kwargs={"host": host, "port": port})
        self.thread.daemon = True
        self.host = host
        self.port = port

    def start(self):
        self.thread.start()
        deadline = time.time() + 3.0
        while time.time() < deadline:
            try:
                with closing(http.client.HTTPConnection(self.host, self.port, timeout=0.25)) as conn:
                    conn.request("GET", "/health")
                    resp = conn.getresponse()
                    _ = resp.read()
                    if resp.status == 200:
                        return
            except Exception:
                time.sleep(0.05)
        raise RuntimeError("UI server did not start in time")

    def stop(self):
        try:
            with closing(http.client.HTTPConnection(self.host, self.port, timeout=1)) as conn:
                conn.request("POST", "/api/exit", body=b"{}", headers={"Content-Type": "application/json"})
                _ = conn.getresponse()
        except Exception:
            pass
        self.thread.join(timeout=2)


# Module-level setup/teardown using default host/port
_TMPDIR = None
_ORIG_DATA_DIR = None
_SERVER = None


def setup_module():
    global _TMPDIR, _ORIG_DATA_DIR, _SERVER
    # ensure any existing server is stopped
    try:
        with closing(http.client.HTTPConnection("127.0.0.1", 8765, timeout=0.5)) as conn:
            conn.request("POST", "/api/exit", body=b"{}", headers={"Content-Type": "application/json"})
            _ = conn.getresponse()
            time.sleep(0.1)
    except Exception:
        pass
    _TMPDIR = tempfile.mkdtemp(prefix="taskman-client-api-")
    _ORIG_DATA_DIR = get_data_store_dir()
    set_data_store_dir(Path(_TMPDIR))
    _SERVER = _ServerThread("127.0.0.1", 8765)
    _SERVER.start()


def teardown_module():
    global _TMPDIR, _ORIG_DATA_DIR, _SERVER
    if _SERVER:
        _SERVER.stop()
        _SERVER = None
    if _ORIG_DATA_DIR is not None:
        set_data_store_dir(_ORIG_DATA_DIR)
    if _TMPDIR and os.path.exists(_TMPDIR):
        shutil.rmtree(_TMPDIR, ignore_errors=True)
    _TMPDIR = None


def test_api_client_basic_crud():
    api = TaskmanApiClient()
    assert api.is_available()

    # Initially empty
    obj = api.list_projects()
    assert obj.get("projects") == []

    # Open project
    name = "Alpha Beta"
    resp = api.open_project(name)
    assert resp.get("ok")
    assert resp.get("currentProject") == name

    # List shows it
    obj2 = api.list_projects()
    assert obj2.get("projects") == [name]

    # Tasks empty
    assert api.get_tasks(name) == []

    # Create task
    c = api.create_task(name, {"summary": "S1", "assignee": "A1", "remarks": "R1", "status": "Not Started", "priority": "Low"})
    assert c.get("ok")
    tasks = api.get_tasks(name)
    assert len(tasks) == 1 and tasks[0]["summary"] == "S1"

    # Update
    u = api.update_task(name, 0, {"summary": "S2"})
    assert u.get("ok")
    assert api.get_tasks(name)[0]["summary"] == "S2"

    # Delete
    d = api.delete_task(name, 0)
    assert d.get("ok")
    assert api.get_tasks(name) == []


def test_api_client_error_paths_and_state():
    # Unavailable server should report False (use high port)
    dead = TaskmanApiClient(host="127.0.0.1", port=6553, timeout=0.1)
    assert dead.is_available() is False

    api = TaskmanApiClient()
    # state endpoint
    st = api.get_state()
    assert "currentProject" in st

    # GET JSON decode error path: hitting '/'
    obj = api._get_json("/")  # type: ignore[attr-defined]
    assert isinstance(obj, dict)
    assert obj == {}

    # GET non-2xx -> raises
    import pytest
    with pytest.raises(RuntimeError):
        api._get_json("/api/does-not-exist")  # type: ignore[attr-defined]

    # POST 4xx -> raises
    with pytest.raises(RuntimeError):
        api._post_json("/api/projects/open", {})  # type: ignore[attr-defined]
