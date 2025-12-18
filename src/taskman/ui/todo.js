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
  const apiEditTodo = (payload) => api('/api/todo/edit', {
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

  const priorityRank = (val) => {
    const key = String(val || 'medium').toLowerCase();
    if (key === 'urgent') return 0;
    if (key === 'high') return 1;
    if (key === 'medium') return 2;
    if (key === 'low') return 3;
    return 2;
  };

  const isOverdue = (isoDate) => {
    const m = String(isoDate || '').trim().match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return false;
    const today = new Date();
    const todayNum = Number(
      `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`,
    );
    const dateNum = Number(`${m[1]}${m[2]}${m[3]}`);
    return dateNum < todayNum;
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
      if (aDue !== bDue) return aDue - bDue;
      const aPriority = Number(a.dataset.priorityValue || Number.POSITIVE_INFINITY);
      const bPriority = Number(b.dataset.priorityValue || Number.POSITIVE_INFINITY);
      return aPriority - bPriority;
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

  const createTodoForm = ({ submitLabel = 'Save', onSubmit, onCancel } = {}) => {
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

    const baseSubmitLabel = submitLabel;
    const setSubmitLabel = (label) => {
      saveBtn.textContent = label || baseSubmitLabel;
    };
    const resetFields = () => {
      setSubmitLabel(baseSubmitLabel);
      titleInput.value = '';
      noteInput.value = '';
      dueInput.value = '';
      prioSelect.value = 'medium';
      peopleInput.value = '';
    };

    const hide = () => {
      form.style.display = 'none';
    };

    const show = () => {
      form.style.display = '';
      titleInput.focus();
    };

    const setValues = (todo, labelOverride) => {
      setSubmitLabel(labelOverride || baseSubmitLabel);
      titleInput.value = todo.title || '';
      noteInput.value = todo.note || '';
      dueInput.value = todo.due_date || '';
      prioSelect.value = (todo.priority || 'medium').toLowerCase();
      peopleInput.value = (todo.people || []).join(', ');
    };

    const close = () => {
      hide();
      resetFields();
      if (typeof onCancel === 'function') onCancel();
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
      if (typeof onSubmit === 'function') {
        try {
          await onSubmit(payload);
          close();
        } catch (err) {
          alert(err && err.message ? err.message : 'Failed to save todo.');
        }
      }
    };

    saveBtn.addEventListener('click', handleSave);
    cancelBtn.addEventListener('click', (e) => { e.preventDefault(); close(); });
    [titleInput, noteInput, dueInput, prioSelect, peopleInput].forEach((el) => {
      el.addEventListener('keydown', (evt) => {
        if (evt.key === 'Escape') {
          evt.preventDefault();
          close();
        }
      });
    });

    return { element: form, show, hide, reset: resetFields, setValues, setSubmitLabel, close };
  };

  const renderList = (items) => {
    list.replaceChildren();
    const addRow = document.createElement('li');
    addRow.className = 'checklist-add';
    const collapsed = document.createElement('div');
    collapsed.className = 'checklist-item';
    const addCheckbox = document.createElement('input');
    addCheckbox.type = 'checkbox';
    addCheckbox.disabled = true;
    addCheckbox.className = 'muted';
    const addText = document.createElement('div');
    addText.className = 'checklist-title muted todo-add-label';
    addText.textContent = 'Add new…';
    collapsed.append(addCheckbox, addText);
    const addForm = createTodoForm({
      submitLabel: 'Save',
      onSubmit: async (payload) => {
        await apiAddTodo(payload);
        await loadTodos();
      },
    });
    addRow.append(collapsed, addForm.element);
    collapsed.addEventListener('click', (e) => { e.preventDefault(); addForm.reset(); addForm.show(); });
    list.appendChild(addRow);
    if (!items || !items.length) {
      const li = document.createElement('li');
      li.className = 'muted';
      li.textContent = 'No todos yet.';
      list.appendChild(li);
      return;
    }
    items.forEach((item) => {
      const li = document.createElement('li');
      li.className = 'todo-item';

      const label = document.createElement('div');
      label.className = 'checklist-item';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = !!item.done;
      const textWrap = document.createElement('div');
      textWrap.className = 'checklist-text';
      const title = document.createElement('div');
      title.className = 'checklist-title';
      title.textContent = item.title || '';
      const note = document.createElement('div');
      note.className = 'checklist-note muted';
      note.textContent = item.note || '';
      const meta = document.createElement('div');
      meta.className = 'checklist-meta';
      const dueIso = item.due_date || '';
      const dueDisplay = formatDueDisplay(dueIso);
    if (dueDisplay) {
      const overdueClass = isOverdue(dueIso) ? 'due-over' : '';
      meta.appendChild(buildPill(`Due ${dueDisplay}`, `due ${overdueClass}`));
    }
      const prio = (item.priority || 'medium').toLowerCase();
      meta.appendChild(buildPill(prio.charAt(0).toUpperCase() + prio.slice(1), `priority priority-${prio}`));
      (item.people || []).forEach((p) => {
        if (!p) return;
        meta.appendChild(buildPill(p, 'people'));
      });
      textWrap.append(title, note, meta);
      label.append(checkbox, textWrap);

      const editForm = createTodoForm({
        submitLabel: 'Update',
        onSubmit: async (payload) => {
          await apiEditTodo({ id: item.id, ...payload });
          await loadTodos();
        },
        onCancel: () => { li.classList.remove('editing'); },
      });
      editForm.hide();

      textWrap.addEventListener('click', (evt) => {
        evt.preventDefault();
        editForm.setValues(item, 'Update');
        li.classList.add('editing');
        editForm.show();
      });

      li.append(label, editForm.element);
      li.dataset.dueValue = String(dueNumeric(dueIso));
      li.dataset.priorityValue = String(priorityRank(prio));
      li.dataset.done = checkbox.checked ? '1' : '0';
      li.classList.toggle('done', checkbox.checked);
      attachCheckboxHandler(checkbox, item.id);
      list.appendChild(li);
    });
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
