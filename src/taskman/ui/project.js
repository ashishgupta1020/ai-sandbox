(function () {
  const Taskman = window.Taskman = window.Taskman || {};
  const utils = Taskman.utils || {};
  const api = Taskman.api || {};

  // Project.js only opens a project and hands control to tasks.js

  // Init
  (async function init() {
    const name = utils.getQueryParam ? utils.getQueryParam('name') : null;
    const title = document.getElementById('title');
    const status = document.getElementById('status');
    if (!name) {
      title.textContent = 'Project (missing name)';
      status.textContent = 'No project specified.';
      return;
    }
    title.textContent = `Project: ${name}`;
    try {
      const result = await api.openProject(name);
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
})();
