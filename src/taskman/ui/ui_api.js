// API wrappers for UI modules.
/** Initialize API helpers for UI modules. */
(function () {
  const Taskman = window.Taskman = window.Taskman || {};

  /** Fetch JSON and throw on HTTP or API errors. */
  async function requestJson(path, opts = {}) {
    const { method, body, headers } = opts || {};
    const fetchOpts = { method: method || 'GET', headers: { ...(headers || {}) } };
    if (body !== undefined) {
      if (!fetchOpts.headers['Content-Type']) fetchOpts.headers['Content-Type'] = 'application/json';
      fetchOpts.body = typeof body === 'string' ? body : JSON.stringify(body);
    }
    const res = await fetch(path, fetchOpts);
    const text = await res.text();
    let data = {};
    // Be tolerant: some endpoints may return empty body or non-JSON error pages.
    try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
    if (!res.ok || (data && data.error)) {
      const msg = (data && data.error) ? data.error : `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  }

  /** POST a JSON payload to an API path. */
  function postJson(path, payload) {
    return requestJson(path, { method: 'POST', body: payload || {} });
  }

  /** Fetch the list of project names. */
  const listProjects = () => requestJson('/api/projects');
  /** Fetch highlighted tasks across projects. */
  const listHighlights = () => requestJson('/api/highlights');
  /** Create or open a project. */
  const openProject = (name) => postJson('/api/projects/open', { name });
  /** Create or open a project (legacy alias). */
  const createProject = (name) => openProject(name);
  /** Rename a project. */
  const renameProject = (oldName, newName) => postJson('/api/projects/edit-name', { old_name: oldName, new_name: newName });
  /** Delete a project and its data. */
  const deleteProject = (name) => postJson('/api/projects/delete', { name });
  /** Fetch tags for all projects. */
  const fetchAllProjectTags = () => requestJson('/api/project-tags');
  /** Fetch tags for a single project. */
  const fetchProjectTags = (name) => requestJson(`/api/projects/${encodeURIComponent(name)}/tags`);
  /** Add tags to a project. */
  const addProjectTags = (name, tags) => postJson(`/api/projects/${encodeURIComponent(name)}/tags/add`, { tags });
  /** Remove a tag from a project. */
  const removeProjectTag = (name, tag) => postJson(`/api/projects/${encodeURIComponent(name)}/tags/remove`, { tag });
  /** Fetch the list of assignees. */
  const listAssignees = () => requestJson('/api/assignees');
  /** Fetch tasks for a list of assignees. */
  const listTasks = (assignees = []) => {
    const params = Array.isArray(assignees) && assignees.length
      ? `?${assignees.map((a) => `assignee=${encodeURIComponent(a)}`).join('&')}`
      : '';
    return requestJson(`/api/tasks${params}`);
  };
  /** Fetch tasks for a single project. */
  const listProjectTasks = (name) => requestJson(`/api/projects/${encodeURIComponent(name)}/tasks`);
  /** Create a task for a project. */
  const createTask = (name, fields = {}) => postJson(`/api/projects/${encodeURIComponent(name)}/tasks/create`, fields || {});
  /** Update a task for a project. */
  const updateTask = (name, taskId, fields) => postJson(`/api/projects/${encodeURIComponent(name)}/tasks/update`, { id: taskId, fields });
  /** Delete a task for a project. */
  const deleteTask = (name, taskId) => postJson(`/api/projects/${encodeURIComponent(name)}/tasks/delete`, { id: taskId });
  /** Toggle highlight for a task. */
  const highlightTask = (name, taskId, highlight) => postJson(
    `/api/projects/${encodeURIComponent(name)}/tasks/highlight`,
    { id: taskId, highlight: !!highlight }
  );

  Taskman.api = {
    requestJson,
    listProjects,
    listHighlights,
    createProject,
    openProject,
    renameProject,
    deleteProject,
    fetchAllProjectTags,
    fetchProjectTags,
    addProjectTags,
    removeProjectTag,
    listAssignees,
    listTasks,
    listProjectTasks,
    createTask,
    updateTask,
    deleteTask,
    highlightTask
  };
})();
