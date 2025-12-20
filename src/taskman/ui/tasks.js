// Task UI module: owns all task state, rendering, and task API calls.
let GRID = null;
let GRID_COLUMNS = null;
let DATA_ROWS = [];
const STATUS_OPTS = ['Not Started', 'In Progress', 'Completed'];
const PRIORITY_OPTS = ['Low', 'Medium', 'High'];
let CURRENT_PROJECT = null;

// Minimal JSON API with consistent error propagation.
async function api(path, opts = {}) {
  const { method, body } = opts || {};
  const fetchOpts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) fetchOpts.body = typeof body === 'string' ? body : JSON.stringify(body);
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
const apiCreateTask = (name, fields = {}) => api(`/api/projects/${encodeURIComponent(name)}/tasks/create`, { method: 'POST', body: fields || {} });
const apiUpdateTask = (name, taskId, fields) => api(`/api/projects/${encodeURIComponent(name)}/tasks/update`, { method: 'POST', body: { id: taskId, fields } });
const apiDeleteTask = (name, taskId) => api(`/api/projects/${encodeURIComponent(name)}/tasks/delete`, { method: 'POST', body: { id: taskId } });
const apiHighlightTask = (name, taskId, highlight) => api(
  `/api/projects/${encodeURIComponent(name)}/tasks/highlight`,
  { method: 'POST', body: { id: taskId, highlight: !!highlight } }
);

// Safe Markdown -> HTML using marked + DOMPurify.
function getRemarksHTML(src) {
  try {
    if (window.marked && window.DOMPurify) {
      if (typeof marked.setOptions === 'function') marked.setOptions({ breaks: true });
      const html = marked.parse(src ?? '');
      return `<div class="md">${DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })}</div>`;
    }
  } catch (_) {}
  return null;
}

// Lightweight Markdown editor with Preview toggle and Ctrl/Cmd+Enter to save.
function createMarkdownEditor(initialText, hooks = {}) {
  const wrapper = document.createElement('div');
  wrapper.className = 'md-editor';

  const toolbar = document.createElement('div');
  toolbar.className = 'md-toolbar';
  const btnPreview = document.createElement('button');
  btnPreview.type = 'button'; btnPreview.className = 'btn btn-sm'; btnPreview.textContent = 'Preview';
  toolbar.appendChild(btnPreview);
  if (typeof hooks.onSave === 'function') {
    const btnSave = document.createElement('button');
    btnSave.type = 'button'; btnSave.className = 'btn btn-sm'; btnSave.textContent = 'Save';
    btnSave.addEventListener('click', () => { hooks.onSave && hooks.onSave(textarea.value); });
    toolbar.appendChild(btnSave);
  }
  if (typeof hooks.onCancel === 'function') {
    const btnCancel = document.createElement('button');
    btnCancel.type = 'button'; btnCancel.className = 'btn btn-sm'; btnCancel.textContent = 'Cancel';
    btnCancel.addEventListener('click', () => { hooks.onCancel && hooks.onCancel(); });
    toolbar.appendChild(btnCancel);
  }

  const textarea = document.createElement('textarea');
  textarea.className = 'inline-input multiline';
  textarea.value = typeof initialText === 'string' ? initialText : '';
  
  // Keep editor compact; preview pane is toggled on demand.
  const preview = document.createElement('div');
  preview.className = 'md preview';
  preview.style.display = 'none';

  const updatePreview = () => {
    const html = getRemarksHTML(textarea.value);
    if (html) { preview.innerHTML = html; }
    else { preview.textContent = textarea.value || ''; }
  };

  let showingPreview = false;
  btnPreview.addEventListener('click', () => {
    showingPreview = !showingPreview;
    if (showingPreview) {
      updatePreview();
      textarea.style.display = 'none';
      preview.style.display = 'block';
      btnPreview.textContent = 'Edit';
    } else {
      textarea.style.display = '';
      preview.style.display = 'none';
      btnPreview.textContent = 'Preview';
      textarea.focus();
    }
  });

  textarea.addEventListener('keydown', (e) => {
    // Accessibility: quick save with Ctrl/Cmd+Enter, cancel with Esc.
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); if (hooks.onSave) hooks.onSave(textarea.value); }
    else if (e.key === 'Escape') { e.preventDefault(); if (hooks.onCancel) hooks.onCancel(); }
  });

  wrapper.appendChild(toolbar);
  wrapper.appendChild(textarea);
  wrapper.appendChild(preview);
  return wrapper;
}

function buildFieldEditor(type, options, currentValue, hooks = {}) {
  let editor;
  const commit = (value) => { if (hooks.onCommit) hooks.onCommit(value); };
  const cancel = () => { if (hooks.onCancel) hooks.onCancel(); };
  if (type === 'select') {
    // Simple select editor; in instantCommit mode we save on change/blur/Enter.
    const select = document.createElement('select');
    select.className = 'inline-input';
    for (const opt of (options || [])) {
      const o = document.createElement('option');
      o.value = opt; o.textContent = opt; select.appendChild(o);
    }
    select.value = currentValue || (options && options[0]) || '';
    if (hooks.instantCommit) {
      select.addEventListener('change', () => commit(select.value));
      select.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); commit(select.value); }
        else if (e.key === 'Escape') { e.preventDefault(); cancel(); }
      });
      select.addEventListener('blur', () => commit(select.value));
    }
    editor = select;
  } else if (type === 'markdown') {
    // Markdown is a composite widget; if instantCommit is on, Save/Cancel map to hooks.
    const mdHooks = hooks.instantCommit ? {
      onSave: () => { commit(editor.querySelector('textarea')?.value || ''); },
      onCancel: () => { cancel(); }
    } : {};
    editor = createMarkdownEditor(typeof currentValue === 'string' ? currentValue : '', mdHooks);
  } else {
    // Plain text input with Enter/blur to commit and Esc to cancel.
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'inline-input';
    input.value = currentValue || '';
    if (hooks.instantCommit) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); commit(input.value); }
        else if (e.key === 'Escape') { e.preventDefault(); cancel(); }
      });
      input.addEventListener('blur', () => commit(input.value));
    }
    editor = input;
  }
  return editor;
}

// Grid.js cell formatter that attaches inline editors; renders Markdown preview when applicable.
function editableFormatter(field, type, options) {
  return (cell, row) => {
    const h = gridjs.h;
    const idx0 = Number(row.cells[0].data);
    const tid = row.cells[1].data != null ? Number(row.cells[1].data) : null;
    if (type === 'markdown') {
      // Render Markdown preview (sanitized). Show placeholder when empty.
      const isEmpty = !cell || (typeof cell === 'string' && cell.trim() === '');
      const displayHTML = isEmpty ? null : getRemarksHTML(cell);
      const displayNode = isEmpty
        ? h('span', { className: 'placeholder' }, 'Click to add remarks...')
        : (displayHTML ? gridjs.html(displayHTML) : (cell || ''));
      return h('span', {
        className: 'editable',
        // Hover state via CSS class to hint editability.
        onMouseEnter: (ev) => ev.target.closest('td')?.classList.add('editable-cell'),
        onMouseLeave: (ev) => ev.target.closest('td')?.classList.remove('editable-cell'),
        onClick: (ev) => startInlineEditor(ev.target, idx0, field, type, options, cell, tid)
      }, displayNode);
    }
    return h('span', {
      className: 'editable',
      onMouseEnter: (ev) => ev.target.closest('td')?.classList.add('editable-cell'),
      onMouseLeave: (ev) => ev.target.closest('td')?.classList.remove('editable-cell'),
      onClick: (ev) => startInlineEditor(ev.target, idx0, field, type, options, cell, tid)
    }, cell);
  };
}

// Internal row model used by Grid.js (hidden index/id, then visible columns).
function buildRowFromTask(index0, task) {
  const i = Number(index0) || 0;
  const t = task || {};
  return [
    i,
    (typeof t.id === 'number' ? t.id : (t.id != null ? Number(t.id) : null)),
    i + 1,
    t.summary || '',
    t.assignee || '',
    t.status || '',
    t.priority || '',
    t.remarks || '',
    !!t.highlight
  ];
}

// Action cell formatter: highlight toggle + delete button.
function actionsFormatter() {
  return (_, row) => {
    const h = gridjs.h;
    const idx0 = Number(row.cells[0].data);
    const tid = row.cells[1].data != null ? Number(row.cells[1].data) : null;
    const isHighlighted = !!row.cells[8].data;

    const starIcon = isHighlighted
      ? '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" fill="gold"/></svg>'
      : '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M22 9.24 14.81 8.63 12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24zm-10 6.11-3.76 2.27 1-4.28L5.5 10.5l4.38-.38L12 6.1l2.12 4.01 4.38.38-3.73 3.84 1 4.28L12 15.35z" fill="currentColor"/></svg>';
    const deleteIcon = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6a1 1 0 0 1 1 1v1h4v2H4V5h4V4a1 1 0 0 1 1-1zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9z" fill="currentColor"/></svg>';

    const toggleHighlight = async () => {
      try {
        const resp = await apiHighlightTask(CURRENT_PROJECT, tid, !isHighlighted);
        if (resp && resp.ok && typeof resp.id === 'number') {
          const idx = findRowIndexById(resp.id);
          if (idx >= 0 && resp.task && updateRowFromTask(idx, resp.task)) {
            renderWithGrid(DATA_ROWS);
          } else {
            void loadTasks(CURRENT_PROJECT);
          }
        }
      } catch (e) {
        alert(e && e.message ? e.message : String(e));
      }
    };

    const deleteTask = async () => {
      const confirmed = window.confirm(`Delete task #${idx0 + 1}?`);
      if (!confirmed) return;
      try {
        const resp = await apiDeleteTask(CURRENT_PROJECT, tid);
        const remIdx = (resp && typeof resp.id === 'number') ? findRowIndexById(resp.id) : idx0;
        if (deleteRowAt(remIdx)) {
          if (DATA_ROWS.length === 0) { GRID = null; }
          renderWithGrid(DATA_ROWS);
        }
      } catch (e) {
        alert(e && e.message ? e.message : String(e));
      }
    };

    const starBtn = h('button', {
      className: 'btn btn-icon',
      title: isHighlighted ? `Remove highlight from task #${idx0 + 1}` : `Highlight task #${idx0 + 1}`,
      'aria-label': isHighlighted ? `Remove highlight from task ${idx0 + 1}` : `Highlight task ${idx0 + 1}`,
      style: 'margin-left:0',
      onClick: toggleHighlight
    }, gridjs.html(starIcon));

    const deleteBtn = h('button', {
      className: 'btn btn-icon',
      title: `Delete task #${idx0 + 1}`,
      'aria-label': `Delete task ${idx0 + 1}`,
      style: 'margin-left:8px',
      onClick: deleteTask
    }, gridjs.html(deleteIcon));

    return h('div', { style: 'display:flex;align-items:center;justify-content:center;' }, [
      starBtn,
      deleteBtn
    ]);
  };
}

function reindexFrom(start) {
  const s = Math.max(0, start | 0);
  for (let i = s; i < DATA_ROWS.length; i++) {
    // Keep hidden 0-based and visible 1-based indices consistent after insert/delete.
    DATA_ROWS[i][0] = i;
    DATA_ROWS[i][2] = i + 1;
  }
}

function insertRowFromTask(insertAt, task) {
  const idx = Math.max(0, Math.min(insertAt | 0, DATA_ROWS.length));
  const row = buildRowFromTask(idx, task);
  DATA_ROWS.splice(idx, 0, row);
  reindexFrom(idx);
  return row;
}

function updateRowFromTask(index0, task) {
  const i = Number(index0) || 0;
  if (!Array.isArray(DATA_ROWS) || i < 0 || i >= DATA_ROWS.length) return false;
  const row = buildRowFromTask(i, task);
  DATA_ROWS[i] = row;
  return true;
}

function deleteRowAt(index0) {
  const i = Number(index0);
  if (!Array.isArray(DATA_ROWS) || i < 0 || i >= DATA_ROWS.length) return false;
  DATA_ROWS.splice(i, 1);
  if (DATA_ROWS.length > 0) reindexFrom(i);
  return true;
}

function findRowIndexById(taskId) {
  if (!Array.isArray(DATA_ROWS)) return -1;
  const tid = Number(taskId);
  for (let i = 0; i < DATA_ROWS.length; i++) {
    if (Number(DATA_ROWS[i][1]) === tid) return i;
  }
  return -1;
}

// Inline editing for grid cells
function startInlineEditor(target, index0, field, type, options, currentValue, taskId) {
  const td = target.closest && target.closest('td') ? target.closest('td') : null;
  if (!td) return;
  // Avoid stacking multiple editors in the same cell.
  if (td.querySelector('.inline-input')) return;
  const commit = async (value) => {
    try {
      const resp = await apiUpdateTask(CURRENT_PROJECT, taskId, { [field]: value });
      if (resp && resp.ok && typeof resp.id === 'number') {
        const idx = findRowIndexById(resp.id);
        // Prefer server response as source of truth; update in-place if possible.
        if (idx >= 0 && resp.task && updateRowFromTask(idx, resp.task)) {
          renderWithGrid(DATA_ROWS);
        } else {
          void loadTasks(CURRENT_PROJECT);
        }
      } else {
        renderWithGrid(DATA_ROWS);
      }
    } catch (e) {
      td.textContent = currentValue || '';
      alert(`Failed to save: ${e && e.message ? e.message : e}`);
    }
  };
  const cancel = async () => {
    // Re-render to restore original cell content.
    renderWithGrid(DATA_ROWS);
  };
  const editor = buildFieldEditor(type, options, currentValue, { instantCommit: true, onCommit: commit, onCancel: cancel });
  td.replaceChildren(editor);
  const focusable = (editor && editor.querySelector) ? (editor.querySelector('textarea, input, select, [contenteditable="true"]') || editor) : editor;
  if (focusable && focusable.focus) focusable.focus();
  if (focusable && focusable.select) focusable.select();
}

// Render or update the Grid.js table. Keeps container height stable to reduce flicker.
function renderWithGrid(rows) {
  const box = document.getElementById('tasks');
  if (!rows.length) { box.textContent = 'No tasks found.'; return; }
  if (!GRID_COLUMNS) { // initialize columns once
    GRID_COLUMNS = [
      { name: '_idx0', hidden: true }, // hidden stable 0-based index
      { name: '_id', hidden: true },   // hidden task id (server truth)
      { name: 'Index', sort: true },
      { name: 'Summary',  sort: true, formatter: editableFormatter('summary',  'text') },
      { name: 'Assignee', sort: true, formatter: editableFormatter('assignee', 'text') },
      { name: 'Status',   sort: true, formatter: editableFormatter('status',   'select', STATUS_OPTS) },
      { name: 'Priority', sort: true, formatter: editableFormatter('priority', 'select', PRIORITY_OPTS) },
      { name: 'Remarks', sort: false, width: '30%', formatter: editableFormatter('remarks', 'markdown') },
      { name: '', sort: false, formatter: actionsFormatter() }
    ];
  }

  if (GRID) {
    const prevHeight = box.offsetHeight;
    // Preserve height during re-render to avoid layout shift/flicker.
    if (prevHeight > 0) box.style.minHeight = prevHeight + 'px';
    try {
      GRID.updateConfig({ data: rows }).forceRender();
    } finally {
      // Release after paint so the UI remains smooth.
      setTimeout(() => { box.style.minHeight = ''; }, 0);
    }
    return;
  }

  box.replaceChildren();
  GRID = new gridjs.Grid({
    columns: GRID_COLUMNS,
    data: rows,
    sort: true,
    search: true,
    pagination: { limit: 20 },
    style: { table: { tableLayout: 'auto' } }
  });
  GRID.render(box);
}

// Simple non-Grid.js fallback renderer (no sorting/filtering).
function renderFallbackTable(tasks) {
  const box = document.getElementById('tasks');
  if (!Array.isArray(tasks) || tasks.length === 0) { box.textContent = 'No tasks found.'; return; }
  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  const headers = ['Index', 'Summary', 'Assignee', 'Status', 'Priority', 'Remarks'];
  for (const h of headers) { const th = document.createElement('th'); th.textContent = h; trh.appendChild(th); }
  thead.appendChild(trh);
  const tbody = document.createElement('tbody');
  tasks.forEach((t, i) => {
    const tr = document.createElement('tr');
    const plain = [String(i + 1), t.summary || '', t.assignee || '', t.status || '', t.priority || ''];
    for (const c of plain) { const td = document.createElement('td'); td.textContent = c; tr.appendChild(td); }
    const remarksTd = document.createElement('td');
    remarksTd.style.textAlign = 'left';
    const src = t.remarks || '';
    const html = getRemarksHTML(src);
    if (html) {
      remarksTd.innerHTML = html;
    } else {
      const container = document.createElement('div');
      container.className = 'md';
      container.style.whiteSpace = 'pre-wrap';
      container.textContent = src;
      remarksTd.replaceChildren(container);
    }
    tr.appendChild(remarksTd);
    tbody.appendChild(tr);
  });
  table.appendChild(thead);
  table.appendChild(tbody);
  box.replaceChildren(table);
}

// Load tasks for a project and render. Grid.js receives raw text; Markdown is formatted via cell formatter.
async function loadTasks(name) {
  const box = document.getElementById('tasks');
  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(name)}/tasks`);
    const data = await res.json();
    const tasks = Array.isArray(data.tasks) ? data.tasks : [];
    if (window.gridjs && typeof gridjs.Grid === 'function') {
      const rows = tasks.map((t, i) => {
        // Keep raw strings in rows; Markdown cells render via formatter for security/speed.
        const idx = i + 1;
        const summary = t.summary || '';
        const assignee = t.assignee || '';
        const status = t.status || '';
        const priority = t.priority || '';
        const src = t.remarks || '';
        const id = (typeof t.id === 'number' ? t.id : (t.id != null ? Number(t.id) : null));
        const highlight = !!t.highlight;
        return [i, id, idx, summary, assignee, status, priority, src, highlight];
      });
      // Cache data for in-place edits/deletes without a full reload.
      DATA_ROWS = rows;
      renderWithGrid(DATA_ROWS);
    } else {
      renderFallbackTable(tasks);
    }
  } catch (e) {
    box.textContent = `Error loading tasks: ${e && e.message ? e.message : e}`;
  }
}

// Build and wire the Add Task inline panel.
function wireTasksUI() {
  const btnAddTask = document.getElementById('btn-add-task');
  if (!btnAddTask) return;

  btnAddTask.addEventListener('click', () => {
    const panel = document.getElementById('add-task-panel');
    if (!panel) return;
    // Toggle: close if already open; otherwise build a fresh panel.
    if (panel.getAttribute('data-open') === '1') { panel.style.display = 'none'; panel.setAttribute('data-open', '0'); panel.replaceChildren(); return; }

    // Build form fields using the same editor widgets
    panel.replaceChildren();
    panel.setAttribute('data-open', '1');
    panel.style.display = '';
    const grid = document.createElement('div');
    grid.className = 'form-grid';

    // Use the same field editors as inline grid editing for consistency.
    const fields = [
      { key: 'summary',  label: 'Summary',  type: 'text' },
      { key: 'assignee', label: 'Assignee', type: 'text' },
      { key: 'status',   label: 'Status',   type: 'select',  options: STATUS_OPTS, defaultValue: STATUS_OPTS[0] },
      { key: 'priority', label: 'Priority', type: 'select',  options: PRIORITY_OPTS, defaultValue: PRIORITY_OPTS[1] },
      { key: 'remarks',  label: 'Remarks',  type: 'markdown' }
    ];

    const editors = {};
    for (const f of fields) {
      const lab = document.createElement('div'); lab.className = 'label'; lab.textContent = f.label;
      const fieldBox = document.createElement('div'); fieldBox.className = 'field';
      const editor = buildFieldEditor(f.type, f.options, f.defaultValue || '', { instantCommit: false });
      fieldBox.appendChild(editor);
      grid.append(lab, fieldBox);
      editors[f.key] = editor;
    }
    panel.appendChild(grid);

    const actions = document.createElement('div');
    actions.className = 'add-task-actions';
    const btnSave = document.createElement('button'); btnSave.type = 'button'; btnSave.className = 'btn'; btnSave.textContent = 'Save';
    const btnCancel = document.createElement('button'); btnCancel.type = 'button'; btnCancel.className = 'btn'; btnCancel.textContent = 'Cancel';
    actions.append(btnSave, btnCancel);
    panel.appendChild(actions);

    const getValue = (ed) => {
      if (!ed) return '';
      if (ed.tagName === 'SELECT' || ed.tagName === 'INPUT') return ed.value || '';
      const ta = ed.querySelector && ed.querySelector('textarea');
      return ta ? (ta.value || '') : '';
    };

    btnSave.addEventListener('click', async () => {
      const payload = {
        summary: getValue(editors['summary']),
        assignee: getValue(editors['assignee']),
        status: getValue(editors['status']) || STATUS_OPTS[0],
        priority: getValue(editors['priority']) || PRIORITY_OPTS[1],
        remarks: getValue(editors['remarks'])
      };
      try {
        const resp = await apiCreateTask(CURRENT_PROJECT, payload);
        panel.style.display = 'none'; panel.setAttribute('data-open', '0'); panel.replaceChildren();
        // Append to in-memory rows and re-render
        if (resp && resp.ok && resp.task) {
          // Append to end (new tasks are appended server-side)
          insertRowFromTask(DATA_ROWS.length, resp.task);
          renderWithGrid(DATA_ROWS);
        } else {
          void loadTasks(CURRENT_PROJECT);
        }
      } catch (e) {
        alert(e && e.message ? e.message : String(e));
      }
    });

    btnCancel.addEventListener('click', () => {
      panel.style.display = 'none'; panel.setAttribute('data-open', '0'); panel.replaceChildren();
    });
  });
}

// Public init used by project.js to hand over
window.initTasksUI = async function(name) {
  CURRENT_PROJECT = name;
  wireTasksUI();
  void loadTasks(name);
};
