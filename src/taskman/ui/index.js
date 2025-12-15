// Client-side tag cache keyed by project name.
const projectTags = new Map(); // current known state per project (client cache)
let allProjects = [];
let selectedFilterTags = []; // active tag filters for project list (OR logic)
let tagFilterControl = null;
let availableAssignees = [];
let selectedAssignees = [];
const peopleColumns = ['Assignee', 'Project', 'Summary', 'Status', 'Priority'];
let peopleGrid = null; // reused Grid.js instance for the People table
let assigneesLoadPromise = null;
const assigneeTasksCache = new Map(); // assignee -> tasks array

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

function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') n.className = v; else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v); else n.setAttribute(k, v);
  }
  for (const c of children) n.append(c);
  return n;
}

// API wrappers
const apiProjects = () => api('/api/projects');
const apiHighlights = () => api('/api/highlights');
const apiCreateProject = (name) => api('/api/projects/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
const apiRenameProject = (oldName, newName) => api('/api/projects/edit-name', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ old_name: oldName, new_name: newName }) });
const apiFetchAllProjectTags = () => api('/api/project-tags');
const apiFetchProjectTags = (name) => api(`/api/projects/${encodeURIComponent(name)}/tags`);
const apiAddProjectTags = (name, tags) => api(`/api/projects/${encodeURIComponent(name)}/tags/add`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ tags })
});
const apiRemoveProjectTag = (name, tag) => api(`/api/projects/${encodeURIComponent(name)}/tags/remove`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ tag })
});
const apiAssignees = () => api('/api/assignees');
const apiTasks = (assignees = []) => {
  const params = Array.isArray(assignees) && assignees.length
    ? `?${assignees.map((a) => `assignee=${encodeURIComponent(a)}`).join('&')}`
    : '';
  return api(`/api/tasks${params}`);
};

const tagColorMap = new Map();
const tagPalette = ['#c7d2fe', '#bbf7d0', '#fde68a', '#fbcfe8', '#bae6fd', '#fecdd3', '#a7f3d0', '#fef9c3', '#ddd6fe'];

function colorForTag(tag) {
  if (tagColorMap.has(tag)) return tagColorMap.get(tag);
  let hash = 0;
  for (let i = 0; i < tag.length; i++) {
    hash = (hash * 31 + tag.charCodeAt(i)) >>> 0;
  }
  const color = tagPalette[hash % tagPalette.length];
  tagColorMap.set(tag, color);
  return color;
}

function getProjectTags(name) {
  return projectTags.get(name) || [];
}

function setProjectTags(name, tags) {
  const arr = Array.isArray(tags) ? tags.map((t) => String(t)) : [];
  projectTags.set(name, arr);
}

function applyTagsByProject(tagsByProject) {
  const loaded = new Set();
  if (!tagsByProject || typeof tagsByProject !== 'object') return loaded;
  for (const [name, tags] of Object.entries(tagsByProject)) {
    loaded.add(name);
    setProjectTags(name, tags);
  }
  return loaded;
}

function normalizeTagValue(tag) {
  return String(tag || '').trim().toLowerCase();
}

function getAllKnownTags() {
  const seen = new Map();
  for (const tags of projectTags.values()) {
    for (const t of tags) {
      const norm = normalizeTagValue(t);
      if (norm && !seen.has(norm)) seen.set(norm, t);
    }
  }
  return Array.from(seen.values()).sort((a, b) => a.localeCompare(b));
}

function renderTagList(container, name, opts = {}) {
  if (opts.loading) {
    container.replaceChildren(el('span', { class: 'muted tag-placeholder' }, 'Loading tags…'));
    return;
  }
  container.replaceChildren();
  const tags = getProjectTags(name);
  if (!tags.length) {
    container.append(el('span', { class: 'muted tag-placeholder' }, 'No tags yet.'));
    return;
  }
  for (const tag of tags) {
    const pill = el('span', { class: 'tag-pill' }, tag);
    pill.style.backgroundColor = colorForTag(tag);
    const removeBtn = el('button', { type: 'button', class: 'tag-remove', 'aria-label': `Remove tag ${tag}` }, '×');
    removeBtn.addEventListener('click', (evt) => {
      evt.stopPropagation();
      const next = getProjectTags(name).filter((t) => t !== tag);
      setProjectTags(name, next);
      renderTagList(container, name);
    });
    pill.append(removeBtn);
    container.append(pill);
  }
}

async function fetchProjectTags(name, { store = true } = {}) {
  const data = await apiFetchProjectTags(name);
  const tags = Array.isArray(data.tags) ? data.tags.map((t) => String(t)) : [];
  if (store) {
    setProjectTags(name, tags);
  }
  return tags;
}

async function fetchAllProjectTags() {
  const data = await apiFetchAllProjectTags();
  const tagsByProject = (data && typeof data.tagsByProject === 'object') ? data.tagsByProject : {};
  const loaded = applyTagsByProject(tagsByProject);
  return { tagsByProject, loaded };
}

function renderCardTags(container, name) {
  container.replaceChildren();
  const tags = getProjectTags(name);
  if (!tags.length) return;
  for (const tag of tags) {
    const pill = el('span', { class: 'tag-pill tag-pill-small' }, tag);
    pill.style.backgroundColor = colorForTag(tag);
    container.append(pill);
  }
}

// Build the inline project editor (rename + tags) for a project card.
function buildProjectEditor(name, refreshFn) {
  const editor = el('div', { class: 'project-editor', hidden: true });
  const form = el('form', { class: 'project-editor-form' });

  const nameRow = el('div', { class: 'project-editor-row' });
  const nameLabel = el('div', { class: 'project-editor-label' }, 'Name');
  const nameInput = el('input', { type: 'text', class: 'inline-input project-name-input', value: name, 'aria-label': `Rename ${name}` });
  nameRow.append(nameLabel, nameInput);

  const tagsRow = el('div', { class: 'project-editor-row tags-row' });
  const tagsLabel = el('div', { class: 'project-editor-label' }, 'Tags');
  const tagArea = el('div', { class: 'tag-editor' });
  const tagList = el('div', { class: 'tag-list' });
  const renderTags = (opts = {}) => renderTagList(tagList, name, opts);
  renderTags({ loading: true });
  const tagInput = el('input', { type: 'text', class: 'inline-input tag-input', placeholder: 'Add tag and press Enter', 'aria-label': `Add tag for ${name}` });
  tagInput.addEventListener('keydown', async (evt) => {
    if (evt.key === 'Enter') {
      evt.preventDefault();
      if (!tagInput.value.trim()) return;
      const current = getProjectTags(name);
      const val = tagInput.value.trim();
      if (!current.includes(val)) {
        setProjectTags(name, [...current, val]);
        renderTags();
      }
      tagInput.value = '';
    }
  });
  tagArea.append(tagList, tagInput, el('div', { class: 'muted tag-note' }, 'Tags apply when you save.'));
  tagsRow.append(tagsLabel, tagArea);

  const actions = el('div', { class: 'project-editor-actions' });
  const saveBtn = el('button', { type: 'submit', class: 'btn btn-sm' }, 'Save');
  const closeBtn = el('button', { type: 'button', class: 'btn btn-sm btn-ghost' }, 'Close');
  actions.append(saveBtn, closeBtn);

  form.append(nameRow, tagsRow, actions);

  form.addEventListener('submit', async (evt) => {
    evt.preventDefault();
    const newName = nameInput.value.trim();
    if (!newName) {
      alert('Project name cannot be empty.');
      return;
    }
    let targetName = name;
    if (newName !== name) {
      try {
        await apiRenameProject(name, newName);
        if (projectTags.has(name)) {
          projectTags.set(newName, projectTags.get(name) || []);
          projectTags.delete(name);
        }
        targetName = newName;
      } catch (err) {
        alert(err.message || String(err));
        return;
      }
    }
    // Fetch latest tags from server, then apply diff against current client state
    let serverTags = [];
    try {
      serverTags = await fetchProjectTags(targetName, { store: false });
    } catch (err) {
      alert(err.message || String(err));
      return;
    }
    const baseline = new Set(serverTags);
    const desired = getProjectTags(targetName);
    const additions = desired.filter((t) => !baseline.has(t));
    const removals = serverTags.filter((t) => !desired.includes(t));
    try {
      if (additions.length) {
        await apiAddProjectTags(targetName, additions);
      }
      for (const tag of removals) {
        await apiRemoveProjectTag(targetName, tag);
      }
      setProjectTags(targetName, desired);
    } catch (err) {
      alert(err.message || String(err));
      return;
    }
    editor.hidden = true;
    await refreshFn();
  });

  closeBtn.addEventListener('click', async (evt) => {
    evt.preventDefault();
    editor.hidden = true;
    await refreshFn();
  });

  editor.append(form);
  editor.focusEditor = () => nameInput.focus();
  editor.renderTags = renderTags;
  return editor;
}

// Render a project card with click-to-open navigation, inline edit toggle, and tag pills.
function buildProjectCard(name) {
  // Card acts as a link; clicking edit toggles inline editor without navigation.
  const card = el('div', { class: 'project-card', tabindex: 0, role: 'link', 'data-href': `/project.html?name=${encodeURIComponent(name)}`, 'data-name': name });
  const header = el('div', { class: 'project-card-header' });
  const title = el('div', { class: 'project-name' }, name);
  const tagRow = el('div', { class: 'project-card-tags' });
  const rightCluster = el('div', { class: 'project-card-right' });
  const editBtn = el('button', { type: 'button', class: 'btn btn-icon btn-icon-sm edit-btn', title: `Edit ${name}`, 'aria-label': `Edit ${name}`, 'data-name': name });
  const tpl = document.getElementById('tpl-icon-pencil');
  if (tpl && 'content' in tpl) {
    editBtn.appendChild(tpl.content.firstElementChild.cloneNode(true));
  }
  rightCluster.append(tagRow, editBtn);
  header.append(title, rightCluster);
  const editor = buildProjectEditor(name, refreshProjects);

  card.addEventListener('click', (evt) => {
    if (evt.target.closest('.edit-btn') || evt.target.closest('.project-editor')) return;
    window.location.href = card.getAttribute('data-href');
  });
  card.addEventListener('keydown', (evt) => {
    if (evt.target.closest('.project-editor')) return;
    if (evt.key === 'Enter' || evt.key === ' ') {
      evt.preventDefault();
      window.location.href = card.getAttribute('data-href');
    }
  });

  editBtn.addEventListener('click', (evt) => {
    evt.preventDefault();
    evt.stopPropagation();
    editor.hidden = !editor.hidden;
    if (!editor.hidden && editor.focusEditor) editor.focusEditor();
  });

  card.append(header, editor);
  if (editor.renderTags) editor.renderTags();
  renderCardTags(tagRow, name);
  return card;
}

function renderProjectsList(projectNames) {
  const box = document.getElementById('projects');
  const names = Array.isArray(projectNames) ? projectNames : [];
  if (names.length === 0) {
    box.textContent = selectedFilterTags.length ? 'No projects match selected tags.' : 'No projects found.';
    return;
  }
  const list = el('div', { class: 'project-list' });
  for (const name of names) {
    list.appendChild(buildProjectCard(name));
  }
  box.replaceChildren(list);
}

function renderFilterChips() {
  const box = document.getElementById('tag-filter-chips');
  if (!box) return;
  box.replaceChildren();
  if (!selectedFilterTags.length) {
    // Empty state so the filter area doesn't collapse.
    box.append(el('span', { class: 'muted small' }, 'Showing all projects.'));
    return;
  }
  for (const tag of selectedFilterTags) {
    const removeBtn = el('button', { type: 'button', 'aria-label': `Remove filter tag ${tag}` }, '×');
    removeBtn.addEventListener('click', () => removeFilterTag(tag));
    const pill = el('span', { class: 'filter-chip' }, tag);
    pill.append(removeBtn);
    box.append(pill);
  }
}

function projectMatchesFilters(name) {
  if (!selectedFilterTags.length) return true;
  const tags = getProjectTags(name);
  if (!tags || !tags.length) return false;
  const tagSet = new Set(tags.map(normalizeTagValue));
  return selectedFilterTags.some((t) => tagSet.has(normalizeTagValue(t)));
}

function renderFilteredProjects() {
  const names = allProjects.filter((n) => projectMatchesFilters(n));
  renderProjectsList(names);
}

function addFilterTag(tagValue) {
  const raw = (tagValue || '').trim();
  if (!raw) return;
  const norm = normalizeTagValue(raw);
  if (selectedFilterTags.some((t) => normalizeTagValue(t) === norm)) return;
  selectedFilterTags = [...selectedFilterTags, raw];
  renderFilterChips();
  renderFilteredProjects();
}

function removeFilterTag(tagValue) {
  const norm = normalizeTagValue(tagValue);
  selectedFilterTags = selectedFilterTags.filter((t) => normalizeTagValue(t) !== norm);
  renderFilterChips();
  renderFilteredProjects();
}

function clearFilterTags() {
  if (!selectedFilterTags.length) return;
  selectedFilterTags = [];
  renderFilterChips();
  renderFilteredProjects();
}

// Mount the reusable free-text filter control for project tags and wire callbacks.
function wireFilterControls() {
  const host = document.getElementById('tag-filter-control');
  if (!host || typeof window.createFreeTextFilter !== 'function') return;

  const getSuggestions = (val) => {
    const q = normalizeTagValue(val);
    const tags = getAllKnownTags();
    if (!q) return tags;
    const starts = tags.filter((t) => normalizeTagValue(t).startsWith(q));
    if (starts.length) return starts;
    return tags.filter((t) => normalizeTagValue(t).includes(q));
  };

  const control = window.createFreeTextFilter({
    placeholder: 'Filter by tag...',
    getSuggestions,
    onAdd: (value) => addFilterTag(value),
    onClear: () => clearFilterTags()
  });
  tagFilterControl = control;
  host.replaceChildren(control.root); // mount the reusable filter UI
}

async function refreshProjects() {
  try {
    const p = await apiProjects();
    allProjects = Array.isArray(p.projects) ? p.projects : [];
    if (allProjects.length === 0) {
      renderProjectsList([]);
      return;
    }
    let loadedProjects = new Set();
    try {
      const res = await fetchAllProjectTags();
      loadedProjects = res.loaded || new Set();
    } catch (err) {
      loadedProjects = new Set();
    }
    const missing = allProjects.filter((name) => !loadedProjects.has(name));
    if (missing.length) {
      await Promise.all(missing.map((name) => fetchProjectTags(name).catch(() => { setProjectTags(name, []); })));
    }
    renderFilterChips();
    renderFilteredProjects();
  } catch (e) {
    document.getElementById('projects').textContent = `Error: ${e.message}`;
  }
}

async function refreshHighlights() {
  try {
    const data = await apiHighlights();
    const box = document.getElementById('highlights');
    const items = Array.isArray(data.highlights) ? data.highlights : [];
    if (items.length === 0) {
      box.textContent = 'No highlights yet.';
      return;
    }
    // Use Grid.js for consistency with tasks table
    if (!window.gridjs || typeof gridjs.Grid !== 'function') {
      const table = el('table', { class: 'table' });
      const thead = el('thead');
      thead.append(
        el('tr', {},
          el('th', {}, 'Project'),
          el('th', {}, 'Summary'),
          el('th', {}, 'Assignee'),
          el('th', {}, 'Status'),
          el('th', {}, 'Priority')
        )
      );
      const tbody = el('tbody');
      for (const hItem of items) {
        const row = el('tr');
        row.append(
          el('td', {}, hItem.project || ''),
          el('td', {}, hItem.summary || ''),
          el('td', {}, hItem.assignee || ''),
          el('td', {}, hItem.status || ''),
          el('td', {}, hItem.priority || '')
        );
        tbody.append(row);
      }
      table.append(thead, tbody);
      box.replaceChildren(table);
      return;
    }
    const rows = items.map((h) => [
      h.project || '',
      h.summary || '',
      h.assignee || '',
      h.status || '',
      h.priority || ''
    ]);
    const grid = new gridjs.Grid({
      columns: ['Project', 'Summary', 'Assignee', 'Status', 'Priority'],
      data: rows,
      sort: true,
      search: true,
      pagination: { limit: 10 },
      style: { table: { tableLayout: 'auto' } }
    });
    box.replaceChildren();
    grid.render(box);
  } catch (e) {
    document.getElementById('highlights').textContent = `Error: ${e.message}`;
  }
}

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

function toggleAssignee(name) {
  const exists = selectedAssignees.includes(name);
  selectedAssignees = exists ? selectedAssignees.filter((n) => n !== name) : [...selectedAssignees, name];
  refreshPeople();
}

function clearAssigneeSelection() {
  selectedAssignees = [];
  refreshPeople();
}

async function ensureAssigneesLoaded() {
  if (Array.isArray(availableAssignees) && availableAssignees.length) return availableAssignees;
  if (assigneesLoadPromise) return assigneesLoadPromise;
  assigneesLoadPromise = apiAssignees()
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

async function ensureTasksForAssignees(names) {
  const target = Array.isArray(names) ? names : [];
  const missing = target.filter((n) => !assigneeTasksCache.has(n));
  if (!missing.length) return;
  const data = await apiTasks(missing);
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

async function refreshPeople() {
  const box = document.getElementById('people');
  if (!box) return;
  try {
    await ensureAssigneesLoaded();
    renderAssigneeSelector();
    if (!availableAssignees.length) {
      box.textContent = 'No assignees yet.';
      return;
    }
    await ensureTasksForAssignees(selectedAssignees);
    const filtered = selectedAssignees.length
      ? selectedAssignees.flatMap((name) => assigneeTasksCache.get(name) || [])
      : [];
    const rows = filtered.map((t) => [t.assignee || '', t.project || '', t.summary || '', t.status || '', t.priority || '']);
    const emptyMessage = selectedAssignees.length ? 'No tasks for selected assignees yet.' : 'Select at least one assignee to see tasks.';
    box.classList.toggle('muted', rows.length === 0);
    if (!window.gridjs || typeof gridjs.Grid !== 'function') {
      const table = el('table', { class: 'table' });
      const thead = el('thead');
      const headerRow = el('tr');
      for (const col of peopleColumns) {
        headerRow.append(el('th', {}, col));
      }
      thead.append(headerRow);
      const tbody = el('tbody');
      if (rows.length === 0) {
        const emptyRow = el('tr');
        emptyRow.append(el('td', { colspan: peopleColumns.length, class: 'muted' }, emptyMessage));
        tbody.append(emptyRow);
      } else {
        for (const r of rows) {
          const tr = el('tr');
          for (const cell of r) {
            tr.append(el('td', {}, cell));
          }
          tbody.append(tr);
        }
      }
      table.append(thead, tbody);
      box.replaceChildren(table);
      return;
    }
    const gridConfig = {
      columns: peopleColumns,
      data: rows,
      sort: true,
      search: true,
      pagination: { limit: 10 },
      style: { table: { tableLayout: 'auto' } },
      language: { noRecordsFound: emptyMessage }
    };
    // Reuse a single Grid.js instance and forceRender to refresh rows.
    if (peopleGrid) {
      const prevHeight = box.offsetHeight;
      if (prevHeight > 0) box.style.minHeight = `${prevHeight}px`;
      peopleGrid.updateConfig(gridConfig).forceRender(box);
      setTimeout(() => { box.style.minHeight = ''; }, 0);
    } else {
      peopleGrid = new gridjs.Grid(gridConfig);
      box.replaceChildren();
      peopleGrid.render(box);
    }

  } catch (e) {
    document.getElementById('people').textContent = `Error: ${e.message}`;
  }
}

// Initial load
(async function init() {
  wireFilterControls();
  renderFilterChips();
  await Promise.all([refreshProjects(), refreshHighlights(), refreshPeople()]);
  // Wire up actions
  const clearAssigneesBtn = document.getElementById('btn-clear-assignees');
  if (clearAssigneesBtn) {
    clearAssigneesBtn.addEventListener('click', () => {
      clearAssigneeSelection();
    });
  }
  document.getElementById('btn-add').addEventListener('click', async () => {
    try {
      const name = prompt('Enter new project name:');
      if (!name) return;
      await apiCreateProject(name);
      await Promise.all([refreshProjects(), refreshHighlights(), refreshPeople()]);
    } catch (e) {
      alert(e.message);
    }
  });
})();
