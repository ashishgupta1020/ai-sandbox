// Shared UI utilities and task-link helpers.
/** Initialize shared utilities for UI modules. */
(function () {
  const Taskman = window.Taskman = window.Taskman || {};
  const taskLinkIcon = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5l7 7-7 7M5 12h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  /** Read a query parameter from the current URL. */
  function getQueryParam(name) {
    const url = new URL(window.location.href);
    return url.searchParams.get(name);
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

  /** Convert Markdown into safe HTML when marked + DOMPurify are available. */
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

  /** Create a Markdown editor with optional save/cancel hooks. */
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

  /** Build an inline field editor element for the requested type. */
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

  Taskman.utils = { getQueryParam, el, renderTable, getRemarksHTML, createMarkdownEditor, buildFieldEditor };
  Taskman.links = { buildTaskLink, taskLinkLabel, taskLinkIcon };
})();
