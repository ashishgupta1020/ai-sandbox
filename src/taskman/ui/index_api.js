// API wrappers for index page modules.
/** Initialize API helpers for the index modules. */
(function () {
  const Taskman = window.Taskman = window.Taskman || {};
  const api = Taskman.utils.api;
  const jsonHeaders = { 'Content-Type': 'application/json' };

  /** POST a JSON payload to an API path. */
  function postJson(path, payload) {
    return api(path, {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify(payload || {})
    });
  }

  /** Fetch the list of project names. */
  const listProjects = () => api('/api/projects');
  /** Fetch highlighted tasks across projects. */
  const listHighlights = () => api('/api/highlights');
  /** Create or open a project. */
  const createProject = (name) => postJson('/api/projects/open', { name });
  /** Rename a project. */
  const renameProject = (oldName, newName) => postJson('/api/projects/edit-name', { old_name: oldName, new_name: newName });
  /** Delete a project and its data. */
  const deleteProject = (name) => postJson('/api/projects/delete', { name });
  /** Fetch tags for all projects. */
  const fetchAllProjectTags = () => api('/api/project-tags');
  /** Fetch tags for a single project. */
  const fetchProjectTags = (name) => api(`/api/projects/${encodeURIComponent(name)}/tags`);
  /** Add tags to a project. */
  const addProjectTags = (name, tags) => postJson(`/api/projects/${encodeURIComponent(name)}/tags/add`, { tags });
  /** Remove a tag from a project. */
  const removeProjectTag = (name, tag) => postJson(`/api/projects/${encodeURIComponent(name)}/tags/remove`, { tag });
  /** Fetch the list of assignees. */
  const listAssignees = () => api('/api/assignees');
  /** Fetch tasks for a list of assignees. */
  const listTasks = (assignees = []) => {
    const params = Array.isArray(assignees) && assignees.length
      ? `?${assignees.map((a) => `assignee=${encodeURIComponent(a)}`).join('&')}`
      : '';
    return api(`/api/tasks${params}`);
  };

  Taskman.api = {
    listProjects,
    listHighlights,
    createProject,
    renameProject,
    deleteProject,
    fetchAllProjectTags,
    fetchProjectTags,
    addProjectTags,
    removeProjectTag,
    listAssignees,
    listTasks
  };
})();
