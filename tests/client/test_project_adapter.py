import os
import shutil
import threading
import time
import http.client
import tempfile
from contextlib import closing, redirect_stdout
from io import StringIO

from taskman.client.api_client import TaskmanApiClient
from taskman.client.project_adapter import ProjectAdapter
from taskman.project_manager import ProjectManager
from taskman.tasker_ui import start_ui
from taskman.task import Task


class _ServerThread:
    def __init__(self, host: str, port: int):
        self.thread = threading.Thread(target=start_ui, kwargs={"host": host, "port": port})
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
_ORIG_DIR = None
_ORIG_FILE = None
_SERVER = None


def setup_module():
    global _TMPDIR, _ORIG_DIR, _ORIG_FILE, _SERVER
    # ensure any existing server is stopped
    try:
        with closing(http.client.HTTPConnection("127.0.0.1", 8765, timeout=0.5)) as conn:
            conn.request("POST", "/api/exit", body=b"{}", headers={"Content-Type": "application/json"})
            _ = conn.getresponse()
            time.sleep(0.1)
    except Exception:
        pass
    _TMPDIR = tempfile.mkdtemp(prefix="taskman-client-adapter-")
    _ORIG_DIR = ProjectManager.PROJECTS_DIR
    _ORIG_FILE = ProjectManager.PROJECTS_FILE
    ProjectManager.PROJECTS_DIR = _TMPDIR
    ProjectManager.PROJECTS_FILE = os.path.join(_TMPDIR, "projects.json")
    _SERVER = _ServerThread("127.0.0.1", 8765)
    _SERVER.start()


def teardown_module():
    global _TMPDIR, _ORIG_DIR, _ORIG_FILE, _SERVER
    if _SERVER:
        _SERVER.stop()
        _SERVER = None
    if _ORIG_DIR is not None:
        ProjectManager.PROJECTS_DIR = _ORIG_DIR
    if _ORIG_FILE is not None:
        ProjectManager.PROJECTS_FILE = _ORIG_FILE
    if _TMPDIR and os.path.exists(_TMPDIR):
        shutil.rmtree(_TMPDIR, ignore_errors=True)
    _TMPDIR = None


def test_project_adapter_list_edit_export():
    api = TaskmanApiClient()
    name = "Demo Space"
    api.open_project(name)
    proj = ProjectAdapter(name, api)
    # Add a task and list
    proj.add_task(Task("S1", "A1", "R1", "In Progress", "Medium"))
    with StringIO() as buf, redirect_stdout(buf):
        proj.list_tasks()
        output = buf.getvalue()
    assert f"Tasks in project '{name}':" in output
    assert "S1" in output and "A1" in output

    # Edit task
    with StringIO() as buf, redirect_stdout(buf):
        proj.edit_task(1, Task("S2", "A2", "R2", "Completed", "High"))
        output2 = buf.getvalue()
    assert "Task updated successfully." in output2

    # Export
    md_path = ProjectManager.get_markdown_file_path(name)
    with StringIO() as buf, redirect_stdout(buf):
        proj.export_tasks_to_markdown_file()
        output3 = buf.getvalue()
    assert f"Tasks exported to Markdown file: '{md_path}'" in output3
    assert os.path.exists(md_path)
    with open(md_path, "r", encoding="utf-8") as f:
        md = f.read()
    assert "| Index | Summary | Assignee | Status | Priority | Remarks |" in md
    assert "S2" in md and "A2" in md
