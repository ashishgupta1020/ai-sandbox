// Project list, editor, and tag filter logic for the index page.
/** Initialize project UI for the index page. */
(function () {
  const Taskman = window.Taskman = window.Taskman || {};
  const { el } = Taskman.utils;
  const api = Taskman.api;
  const tags = Taskman.tags;

  let allProjects = [];
  let selectedFilterTags = [];
  let tagFilterControl = null;

  /** Build the inline project editor (rename + tags) for a project card. */
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
    /** Render tag pills inside the editor panel. */
    const renderTags = (opts = {}) => tags.renderTagList(tagList, name, opts);
    renderTags({ loading: true });
    const tagInput = el('input', { type: 'text', class: 'inline-input tag-input', placeholder: 'Add tag and press Enter', 'aria-label': `Add tag for ${name}` });
    tagInput.addEventListener('keydown', async (evt) => {
      if (evt.key === 'Enter') {
        evt.preventDefault();
        if (!tagInput.value.trim()) return;
        const current = tags.getProjectTags(name);
        const val = tagInput.value.trim();
        if (!current.includes(val)) {
          tags.setProjectTags(name, [...current, val]);
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
          await api.renameProject(name, newName);
          tags.moveProjectTags(name, newName);
          targetName = newName;
        } catch (err) {
          alert(err.message || String(err));
          return;
        }
      }
      // Fetch latest tags from server, then apply diff against current client state.
      let serverTags = [];
      try {
        serverTags = await tags.fetchProjectTags(targetName, { store: false });
      } catch (err) {
        alert(err.message || String(err));
        return;
      }
      const baseline = new Set(serverTags);
      const desired = tags.getProjectTags(targetName);
      const additions = desired.filter((t) => !baseline.has(t));
      const removals = serverTags.filter((t) => !desired.includes(t));
      try {
        if (additions.length) {
          await api.addProjectTags(targetName, additions);
        }
        for (const tag of removals) {
          await api.removeProjectTag(targetName, tag);
        }
        tags.setProjectTags(targetName, desired);
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

  /** Render a project card with click-to-open navigation and inline edit toggle. */
  function buildProjectCard(name) {
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
    const deleteBtn = el('button', { type: 'button', class: 'btn btn-icon btn-icon-sm delete-btn', title: `Delete ${name}`, 'aria-label': `Delete ${name}`, 'data-name': name });
    const tplTrash = document.getElementById('tpl-icon-trash');
    if (tplTrash && 'content' in tplTrash) {
      deleteBtn.appendChild(tplTrash.content.firstElementChild.cloneNode(true));
    }
    rightCluster.append(tagRow, editBtn, deleteBtn);
    header.append(title, rightCluster);
    const editor = buildProjectEditor(name, refreshProjects);

    card.addEventListener('click', (evt) => {
      if (evt.target.closest('.edit-btn') || evt.target.closest('.delete-btn') || evt.target.closest('.project-editor')) return;
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

    deleteBtn.addEventListener('click', async (evt) => {
      evt.preventDefault();
      evt.stopPropagation();
      if (!confirm(`Are you sure you want to delete the project "${name}"? This will permanently delete all tasks and tags associated with this project.`)) {
        return;
      }
      try {
        await api.deleteProject(name);
        tags.deleteProjectTags(name);
        await Promise.all([
          refreshProjects(),
          Taskman.highlights.refreshHighlights(),
          Taskman.people.refreshPeople()
        ]);
      } catch (e) {
        alert(e.message || String(e));
      }
    });

    card.append(header, editor);
    if (editor.renderTags) editor.renderTags();
    tags.renderCardTags(tagRow, name);
    return card;
  }

  /** Render the project list container. */
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

  /** Render active tag filter chips. */
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

  /** Determine if a project matches the active tag filters. */
  function projectMatchesFilters(name) {
    if (!selectedFilterTags.length) return true;
    const tagsForProject = tags.getProjectTags(name);
    if (!tagsForProject || !tagsForProject.length) return false;
    const tagSet = new Set(tagsForProject.map(tags.normalizeTagValue));
    return selectedFilterTags.some((t) => tagSet.has(tags.normalizeTagValue(t)));
  }

  /** Render the project list filtered by tags. */
  function renderFilteredProjects() {
    const names = allProjects.filter((n) => projectMatchesFilters(n));
    renderProjectsList(names);
  }

  /** Add a new tag filter and rerender. */
  function addFilterTag(tagValue) {
    const raw = (tagValue || '').trim();
    if (!raw) return;
    const norm = tags.normalizeTagValue(raw);
    if (selectedFilterTags.some((t) => tags.normalizeTagValue(t) === norm)) return;
    selectedFilterTags = [...selectedFilterTags, raw];
    renderFilterChips();
    renderFilteredProjects();
  }

  /** Remove a tag filter and rerender. */
  function removeFilterTag(tagValue) {
    const norm = tags.normalizeTagValue(tagValue);
    selectedFilterTags = selectedFilterTags.filter((t) => tags.normalizeTagValue(t) !== norm);
    renderFilterChips();
    renderFilteredProjects();
  }

  /** Clear all tag filters and rerender. */
  function clearFilterTags() {
    if (!selectedFilterTags.length) return;
    selectedFilterTags = [];
    renderFilterChips();
    renderFilteredProjects();
  }

  /** Mount the free-text tag filter control and wire callbacks. */
  function wireFilterControls() {
    const host = document.getElementById('tag-filter-control');
    if (!host || typeof window.createFreeTextFilter !== 'function') return;

    /** Provide tag suggestions for the filter control. */
    const getSuggestions = (val) => {
      const q = tags.normalizeTagValue(val);
      const known = tags.getAllKnownTags();
      if (!q) return known;
      const starts = known.filter((t) => tags.normalizeTagValue(t).startsWith(q));
      if (starts.length) return starts;
      return known.filter((t) => tags.normalizeTagValue(t).includes(q));
    };

    const control = window.createFreeTextFilter({
      placeholder: 'Filter by tag...',
      getSuggestions,
      onAdd: (value) => addFilterTag(value),
      onClear: () => clearFilterTags()
    });
    tagFilterControl = control;
    host.replaceChildren(control.root);
  }

  /** Wire project-level actions (add project button). */
  function wireProjectActions() {
    const addProjectBtn = document.getElementById('btn-add');
    if (!addProjectBtn) return;
    addProjectBtn.addEventListener('click', async () => {
      try {
        const name = prompt('Enter new project name:');
        if (!name) return;
        await api.createProject(name);
        await Promise.all([
          refreshProjects(),
          Taskman.highlights.refreshHighlights(),
          Taskman.people.refreshPeople()
        ]);
      } catch (e) {
        alert(e.message);
      }
    });
  }

  /** Fetch projects and tags, then refresh the list UI. */
  async function refreshProjects() {
    try {
      const [projectsResponse] = await Promise.all([
        api.listProjects(),
        tags.fetchAllProjectTags().catch(() => ({ tagsByProject: {}, loaded: new Set() }))
      ]);
      allProjects = Array.isArray(projectsResponse.projects) ? projectsResponse.projects : [];
      renderFilterChips();
      renderFilteredProjects();
    } catch (e) {
      document.getElementById('projects').textContent = `Error: ${e.message}`;
    }
  }

  Taskman.projects = {
    refreshProjects,
    renderFilterChips,
    renderFilteredProjects,
    wireFilterControls,
    wireProjectActions,
    clearFilterTags
  };
})();
