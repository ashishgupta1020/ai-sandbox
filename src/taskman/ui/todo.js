(function () {
  const list = document.querySelector('.checklist');
  if (!list) return;

  // Minimal JSON helper for todo endpoints
  const api = async (path, opts = {}) => {
    const res = await fetch(path, opts);
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch (_) {}
    if (!res.ok || (data && data.error)) {
      const msg = (data && data.error) ? data.error : `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  };
  const apiListTodos = () => api('/api/todo');
  const apiAddTodo = (payload) => api('/api/todo/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {})
  });
  const apiMarkTodo = (payload) => api('/api/todo/mark', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {})
  });

  const formatDueDisplay = (val) => {
    if (!val) return '';
    const m = String(val).trim().match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return '';
    return `${m[3]}/${m[2]}`;
  };

  const dueNumeric = (val) => {
    if (!val) return Number.POSITIVE_INFINITY;
    const m = String(val).trim().match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return Number.POSITIVE_INFINITY;
    return Number(`${m[1]}${m[2]}${m[3]}`);
  };

  const syncState = (input) => {
    const li = input.closest('li');
    if (!li) return;
    li.classList.toggle('done', input.checked);
    li.dataset.done = input.checked ? '1' : '0';
  };

  const sortList = () => {
    const items = Array.from(list.querySelectorAll('li.todo-item'));
    items.forEach((li) => {
      const input = li.querySelector('input[type="checkbox"]');
      if (input) syncState(input);
    });
    items.sort((a, b) => {
      const aDone = a.dataset.done === '1' ? 1 : 0;
      const bDone = b.dataset.done === '1' ? 1 : 0;
      if (aDone !== bDone) return aDone - bDone; // unchecked first
      const aDue = Number(a.dataset.dueValue || Number.POSITIVE_INFINITY);
      const bDue = Number(b.dataset.dueValue || Number.POSITIVE_INFINITY);
      return aDue - bDue;
    });
    items.forEach((li) => list.appendChild(li));
  };

  const attachCheckboxHandler = (input, todoId) => {
    input.addEventListener('change', async () => {
      const checked = input.checked;
      try {
        await apiMarkTodo({ id: todoId, done: checked });
      } catch (err) {
        // Revert on failure and surface error
        input.checked = !checked;
        alert(err && err.message ? err.message : 'Failed to update todo.');
        return;
      }
      sortList();
    });
  };

  const buildPill = (text, className) => {
    const span = document.createElement('span');
    span.className = `pill ${className}`.trim();
    span.textContent = text;
    return span;
  };

  const buildAddNew = (onAdd) => {
    const li = document.createElement('li');
    li.className = 'checklist-add';

    const collapsed = document.createElement('div');
    collapsed.className = 'checklist-item';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.disabled = true;
    checkbox.className = 'muted';
    const text = document.createElement('div');
    text.className = 'checklist-title muted';
    text.textContent = 'Add new…';
    collapsed.append(checkbox, text);

    const form = document.createElement('div');
    form.className = 'todo-add-form';
    form.style.display = 'none';

    const titleInput = document.createElement('input');
    titleInput.type = 'text';
    titleInput.className = 'inline-input';
    titleInput.placeholder = 'Todo title (required)';

    const noteInput = document.createElement('textarea');
    noteInput.className = 'inline-input multiline';
    noteInput.rows = 2;
    noteInput.placeholder = 'Add note (optional)';

    const row = document.createElement('div');
    row.className = 'todo-add-row';
    const dueInput = document.createElement('input');
    dueInput.type = 'date';
    dueInput.className = 'inline-input';
    dueInput.placeholder = 'Due date';
    const prioSelect = document.createElement('select');
    prioSelect.className = 'inline-input';
    ['low', 'medium', 'high', 'urgent'].forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p;
      opt.textContent = p.charAt(0).toUpperCase() + p.slice(1);
      if (p === 'medium') opt.selected = true;
      prioSelect.appendChild(opt);
    });
    row.append(dueInput, prioSelect);

    const peopleInput = document.createElement('input');
    peopleInput.type = 'text';
    peopleInput.className = 'inline-input';
    peopleInput.placeholder = 'People (comma-separated)';

    const actions = document.createElement('div');
    actions.className = 'todo-add-actions';
    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'btn btn-sm';
    saveBtn.textContent = 'Save';
    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn btn-sm btn-ghost';
    cancelBtn.textContent = 'Cancel';
    actions.append(saveBtn, cancelBtn);

    form.append(titleInput, noteInput, row, peopleInput, actions);

    const hideForm = () => {
      form.style.display = 'none';
    };
    const showForm = () => {
      form.style.display = '';
      titleInput.focus();
    };

    const resetForm = () => {
      hideForm();
      titleInput.value = '';
      noteInput.value = '';
      dueInput.value = '';
      prioSelect.value = 'medium';
      peopleInput.value = '';
    };

    const handleSave = async () => {
      const title = titleInput.value.trim();
      if (!title) {
        titleInput.focus();
        return;
      }
      const payload = {
        title,
        note: noteInput.value.trim(),
        due_date: dueInput.value || '',
        priority: prioSelect.value,
        people: peopleInput.value.trim(),
      };
      if (typeof onAdd === 'function') {
        await onAdd(payload);
      }
      resetForm();
    };

    collapsed.addEventListener('click', (e) => { e.preventDefault(); showForm(); });
    saveBtn.addEventListener('click', handleSave);
    cancelBtn.addEventListener('click', (e) => { e.preventDefault(); resetForm(); });
    [titleInput, noteInput, dueInput, prioSelect, peopleInput].forEach((el) => {
      el.addEventListener('keydown', (evt) => {
        if (evt.key === 'Escape') {
          evt.preventDefault();
          resetForm();
        }
      });
    });

    li.append(collapsed, form);
    return li;
  };

  const buildItem = (todo) => {
    const li = document.createElement('li');
    li.className = 'todo-item';
    const label = document.createElement('div');
    label.className = 'checklist-item';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = !!todo.done;

    const textWrap = document.createElement('div');
    textWrap.className = 'checklist-text';

    const title = document.createElement('div');
    title.className = 'checklist-title';
    title.textContent = todo.title || '';

    const note = document.createElement('div');
    note.className = 'checklist-note muted';
    note.textContent = todo.note || '';

    const meta = document.createElement('div');
    meta.className = 'checklist-meta';
    const dueIso = todo.due_date || '';
    const dueDisplay = formatDueDisplay(dueIso);
    if (dueDisplay) meta.appendChild(buildPill(`Due ${dueDisplay}`, 'due'));
    const prio = (todo.priority || 'medium').toLowerCase();
    meta.appendChild(buildPill(prio.charAt(0).toUpperCase() + prio.slice(1), `priority priority-${prio}`));
    (todo.people || []).forEach((p) => {
      if (!p) return;
      meta.appendChild(buildPill(p, 'people'));
    });

    textWrap.append(title, note, meta);
    label.append(checkbox, textWrap);
    li.append(label);

    li.dataset.dueValue = String(dueNumeric(dueIso));
    li.dataset.done = checkbox.checked ? '1' : '0';
    li.classList.toggle('done', checkbox.checked);

    attachCheckboxHandler(checkbox, todo.id);
    return li;
  };

  const renderList = (items) => {
    list.replaceChildren();
    const addRow = buildAddNew(async (payload) => {
      try {
        await apiAddTodo(payload);
        await loadTodos();
      } catch (err) {
        alert(err && err.message ? err.message : 'Failed to add todo.');
      }
    });
    list.appendChild(addRow);
    if (!items || !items.length) {
      const li = document.createElement('li');
      li.className = 'muted';
      li.textContent = 'No todos yet.';
      list.appendChild(li);
      return;
    }
    items.forEach((item) => list.appendChild(buildItem(item)));
    sortList();
  };

  const showError = (message) => {
    list.replaceChildren();
    const li = document.createElement('li');
    li.className = 'muted';
    li.textContent = message;
    list.appendChild(li);
  };

  const loadTodos = async () => {
    try {
      const data = await apiListTodos();
      renderList(Array.isArray(data.items) ? data.items : []);
    } catch (err) {
      showError(err && err.message ? err.message : 'Failed to load todos.');
    }
  };

  // Initial render from API
  loadTodos();
})();
