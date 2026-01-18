// Shared UI utilities and task-link helpers for index page modules.
/** Initialize shared utilities for index modules. */
(function () {
  const Taskman = window.Taskman = window.Taskman || {};
  const taskLinkIcon = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5l7 7-7 7M5 12h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  /** Fetch JSON and throw on HTTP failures. */
  async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch (_) {}
    if (!res.ok) {
      const msg = (data && data.error) ? data.error : `Request failed: ${res.status}`;
      throw new Error(msg);
    }
    return data;
  }

  /** Create a DOM element with attributes and children. */
  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (key === 'class') {
        node.className = value;
      } else if (key.startsWith('on') && typeof value === 'function') {
        node.addEventListener(key.slice(2), value);
      } else {
        node.setAttribute(key, value);
      }
    }
    for (const child of children) {
      node.append(child);
    }
    return node;
  }

  /** Render a basic table for non-Grid.js fallbacks. */
  function renderTable(columns, rows, emptyMessage) {
    const table = el('table', { class: 'table' });
    const thead = el('thead');
    const headerRow = el('tr');
    for (const col of columns) {
      headerRow.append(el('th', {}, col));
    }
    thead.append(headerRow);
    const tbody = el('tbody');
    if (!rows.length && emptyMessage) {
      const emptyRow = el('tr');
      emptyRow.append(el('td', { colspan: columns.length, class: 'muted' }, emptyMessage));
      tbody.append(emptyRow);
    } else {
      for (const row of rows) {
        const tr = el('tr');
        for (const cell of row) {
          tr.append(el('td', {}, cell ?? ''));
        }
        tbody.append(tr);
      }
    }
    table.append(thead, tbody);
    return table;
  }

  /** Check whether Grid.js is available on the page. */
  function gridAvailable() {
    return !!(window.gridjs && typeof gridjs.Grid === 'function');
  }

  /** Build a project task link for the summary tables. */
  function buildTaskLink(project, taskId) {
    if (!project) return '';
    const parsed = Number(taskId);
    if (!Number.isFinite(parsed)) return '';
    return `/project.html?name=${encodeURIComponent(project)}&taskId=${encodeURIComponent(parsed)}`;
  }

  /** Create an accessible label for a task link. */
  function taskLinkLabel(summary) {
    return summary ? `View task: ${summary}` : 'View task';
  }

  /** Build a Grid.js cell formatter for task links. */
  function makeTaskLinkFormatter(projectIdx, summaryIdx, idIdx) {
    return (_, row) => {
      const project = row?.cells?.[projectIdx]?.data || '';
      const summary = row?.cells?.[summaryIdx]?.data || '';
      const taskId = row?.cells?.[idIdx]?.data;
      const href = buildTaskLink(project, taskId);
      if (!href) return '';
      const label = taskLinkLabel(summary);
      return gridjs.h('a', {
        className: 'btn btn-icon',
        href,
        title: label,
        'aria-label': label
      }, gridjs.html(taskLinkIcon));
    };
  }

  Taskman.utils = { api, el, renderTable, gridAvailable };
  Taskman.links = { buildTaskLink, taskLinkLabel, makeTaskLinkFormatter };
})();
