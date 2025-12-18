from __future__ import annotations

import http.client
import json
from contextlib import closing
from typing import Any, Dict, List
from urllib.parse import quote


class TaskmanApiClient:
    """
    Minimal REST client for the taskman server.

    Defaults to connecting to 127.0.0.1:8765, matching start_server().
    All methods return parsed JSON objects or raise on connection errors.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765, timeout: float = 2.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    # ----- Low-level helpers -----
    def _conn(self) -> http.client.HTTPConnection:
        return http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)

    def _get_json(self, path: str) -> Dict[str, Any]:
        with closing(self._conn()) as conn:
            conn.request("GET", path)
            resp = conn.getresponse()
            data = resp.read()
            if resp.status < 200 or resp.status >= 300:
                raise RuntimeError(f"GET {path} failed: {resp.status}")
            try:
                return json.loads(data or b"{}")
            except json.JSONDecodeError:
                return {}

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload or {}).encode("utf-8")
        headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
        with closing(self._conn()) as conn:
            conn.request("POST", path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            if resp.status < 200 or resp.status >= 300:
                # Try to return any error payload if present
                try:
                    obj = json.loads(data or b"{}")
                except json.JSONDecodeError:
                    obj = {}
                raise RuntimeError(obj.get("error") or f"POST {path} failed: {resp.status}")
            try:
                return json.loads(data or b"{}")
            except json.JSONDecodeError:
                return {}

    # ----- Availability -----
    def is_available(self) -> bool:
        try:
            _ = self._get_json("/health")
            return True
        except Exception:
            return False

    # ----- Project operations -----
    def list_projects(self) -> Dict[str, Any]:
        return self._get_json("/api/projects")

    def open_project(self, name: str) -> Dict[str, Any]:
        return self._post_json("/api/projects/open", {"name": name})

    def rename_project(self, old_name: str, new_name: str) -> Dict[str, Any]:
        return self._post_json("/api/projects/edit-name", {"old_name": old_name, "new_name": new_name})

    # ----- Task operations -----
    def get_tasks(self, project: str) -> List[Dict[str, Any]]:
        name = quote(project, safe="")
        obj = self._get_json(f"/api/projects/{name}/tasks")
        tasks = obj.get("tasks", [])
        return tasks if isinstance(tasks, list) else []

    def create_task(self, project: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        name = quote(project, safe="")
        return self._post_json(f"/api/projects/{name}/tasks/create", fields)

    def update_task(self, project: str, task_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        name = quote(project, safe="")
        return self._post_json(f"/api/projects/{name}/tasks/update", {"id": task_id, "fields": fields})

    def delete_task(self, project: str, task_id: int) -> Dict[str, Any]:
        name = quote(project, safe="")
        return self._post_json(f"/api/projects/{name}/tasks/delete", {"id": task_id})
