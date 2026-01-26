// Assignee filter and People table rendering for the index page.
/** Initialize the People view for the index page. */
(function () {
  const Taskman = window.Taskman = window.Taskman || {};
  const { el, renderTable } = Taskman.utils;
  const grid = Taskman.grid || {};
  const api = Taskman.api;

  let availableAssignees = [];
  let selectedAssignees = [];
  const peopleColumns = ['Assignee', 'Project', 'Summary', 'Status', 'Priority'];
  let peopleGrid = null;
  let assigneesLoadPromise = null;
  const assigneeTasksCache = new Map();

  /** Render the assignee selection chips. */
  function renderAssigneeSelector() {
    const host = document.getElementById('assignee-options');
    const clearBtn = document.getElementById('btn-clear-assignees');
    if (!host) return;
    host.replaceChildren();
    const names = Array.isArray(availableAssignees) ? availableAssignees : [];
    if (!names.length) {
      host.append(el('span', { class: 'muted assignee-empty' }, 'No assignees yet.'));
      if (clearBtn) clearBtn.disabled = true;
      return;
    }
    for (const name of names) {
      const active = selectedAssignees.includes(name);
      const chip = el(
        'button',
        {
          type: 'button',
          class: `filter-chip assignee-chip${active ? ' active' : ''}`,
          'aria-pressed': String(active),
          'data-assignee': name
        },
        name
      );
      chip.addEventListener('click', () => toggleAssignee(name));
      host.append(chip);
    }
    if (clearBtn) clearBtn.disabled = selectedAssignees.length === 0;
  }

  /** Toggle an assignee selection and refresh the table. */
  function toggleAssignee(name) {
    const exists = selectedAssignees.includes(name);
    selectedAssignees = exists ? selectedAssignees.filter((n) => n !== name) : [...selectedAssignees, name];
    void refreshPeople();
  }

  /** Clear all assignee selections. */
  function clearAssigneeSelection() {
    selectedAssignees = [];
    void refreshPeople();
  }

  /** Wire assignee actions (clear button). */
  function wireAssigneeActions() {
    const clearAssigneesBtn = document.getElementById('btn-clear-assignees');
    if (!clearAssigneesBtn) return;
    clearAssigneesBtn.addEventListener('click', () => {
      clearAssigneeSelection();
    });
  }

  /** Ensure assignees are loaded, with a shared inflight promise. */
  async function ensureAssigneesLoaded() {
    if (Array.isArray(availableAssignees) && availableAssignees.length) return availableAssignees;
    if (assigneesLoadPromise) return assigneesLoadPromise;
    assigneesLoadPromise = api.listAssignees()
      .then((data) => {
        const names = Array.isArray(data.assignees) ? data.assignees.map((a) => String(a)).filter(Boolean) : [];
        if (names.length) availableAssignees = names;
        return availableAssignees;
      })
      .catch(() => {
        return availableAssignees;
      })
      .finally(() => { assigneesLoadPromise = null; });
    return assigneesLoadPromise;
  }

  /** Fetch tasks for assignees not yet cached. */
  async function ensureTasksForAssignees(names) {
    const target = Array.isArray(names) ? names : [];
    const missing = target.filter((n) => !assigneeTasksCache.has(n));
    if (!missing.length) return;
    const data = await api.listTasks(missing);
    const tasks = Array.isArray(data.tasks) ? data.tasks : [];
    const grouped = new Map();
    for (const t of tasks) {
      const assignee = (t.assignee || '').toString();
      if (!grouped.has(assignee)) grouped.set(assignee, []);
      grouped.get(assignee).push(t);
    }
    for (const name of missing) {
      assigneeTasksCache.set(name, grouped.get(name) || []);
    }
  }

  /** Refresh the People table based on selected assignees. */
  async function refreshPeople() {
    const box = document.getElementById('people');
    if (!box) return;
    try {
      await ensureAssigneesLoaded();
      renderAssigneeSelector();
      if (!availableAssignees.length) {
        box.replaceChildren();
        box.classList.add('muted');
        return;
      }
      await ensureTasksForAssignees(selectedAssignees);
      const filtered = selectedAssignees.length
        ? selectedAssignees.flatMap((name) => assigneeTasksCache.get(name) || [])
        : [];
      const gridRows = filtered.map((t) => [t.assignee || '', t.project || '', t.summary || '', t.status || '', t.priority || '', t.id]);
      const tableRows = filtered.map((t) => [t.assignee || '', t.project || '', t.summary || '', t.status || '', t.priority || '']);
      const emptyMessage = selectedAssignees.length ? 'No tasks for selected assignees yet.' : 'Select at least one assignee to see tasks.';
      if (!grid.available || !grid.available()) {
        if (peopleGrid && typeof peopleGrid.destroy === 'function') peopleGrid.destroy();
        peopleGrid = null;
        const table = renderTable(peopleColumns, tableRows, emptyMessage);
        box.replaceChildren(table);
        return;
      }
      const gridConfig = {
        columns: [...peopleColumns, { id: 'task_link', name: '', sort: false, formatter: grid.makeTaskLinkFormatter(1, 2, 5) }],
        data: gridRows,
        sort: true,
        search: true,
        pagination: { limit: 10 },
        style: { table: { tableLayout: 'auto' } },
        language: { noRecordsFound: emptyMessage }
      };
      peopleGrid = grid.renderGrid
        ? grid.renderGrid(box, peopleGrid, gridConfig, { resetOnEmpty: true, preserveHeight: true })
        : peopleGrid;

    } catch (e) {
      document.getElementById('people').textContent = `Error: ${e.message}`;
    }
  }

  Taskman.people = {
    refreshPeople,
    clearAssigneeSelection,
    wireAssigneeActions
  };
})();
