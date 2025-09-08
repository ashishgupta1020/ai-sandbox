// Utils
function getParam(name) {
  const url = new URL(window.location.href);
  return url.searchParams.get(name);
}

// Minimal JSON API helper for POST/GET returning parsed JSON or throwing on error
async function api(path, opts = {}) {
  const { method, body } = opts || {};
  const fetchOpts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) fetchOpts.body = typeof body === 'string' ? body : JSON.stringify(body);
  const res = await fetch(path, fetchOpts);
  const text = await res.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
  if (!res.ok || (data && data.error)) {
    const msg = (data && data.error) ? data.error : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

// API wrapper (project open only)
async function openProject(name) {
  return api('/api/projects/open', { method: 'POST', body: { name } });
}

// Project.js only opens a project and hands control to tasks.js

// Init
(async function init() {
  const name = getParam('name');
  const title = document.getElementById('title');
  const status = document.getElementById('status');
  if (!name) {
    title.textContent = 'Project (missing name)';
    status.textContent = 'No project specified.';
    return;
  }
  title.textContent = `Project: ${name}`;
  try {
    const result = await openProject(name);
    const projName = (result && result.currentProject) ? result.currentProject : name;
    title.textContent = `Project: ${projName}`;
    if (!(result && result.ok)) {
      status.textContent = 'Failed to open project.';
    } else {
      status.textContent = '';
    }
    if (typeof window.initTasksUI === 'function') {
      await window.initTasksUI(projName);
    }
  } catch (e) {
    status.textContent = `Error: ${e.message}`;
  }
})();
