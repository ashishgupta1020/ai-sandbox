// Tag cache and tag UI helpers shared by the projects view.
/** Initialize tag helpers for the projects view. */
(function () {
  const Taskman = window.Taskman = window.Taskman || {};
  const { el } = Taskman.utils;
  const api = Taskman.api;

  const projectTags = new Map();
  const tagColorMap = new Map();
  const tagPalette = ['#c7d2fe', '#bbf7d0', '#fde68a', '#fbcfe8', '#bae6fd', '#fecdd3', '#a7f3d0', '#fef9c3', '#ddd6fe'];

  /** Assign a stable color for a tag label. */
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

  /** Return cached tags for a project. */
  function getProjectTags(name) {
    return projectTags.get(name) || [];
  }

  /** Update the cached tags for a project. */
  function setProjectTags(name, tags) {
    const arr = Array.isArray(tags) ? tags.map((t) => String(t)) : [];
    projectTags.set(name, arr);
  }

  /** Move cached tags when a project is renamed. */
  function moveProjectTags(oldName, newName) {
    if (!projectTags.has(oldName)) return;
    projectTags.set(newName, projectTags.get(oldName) || []);
    projectTags.delete(oldName);
  }

  /** Remove cached tags for a deleted project. */
  function deleteProjectTags(name) {
    projectTags.delete(name);
  }

  /** Apply the server tag map into local cache. */
  function applyTagsByProject(tagsByProject) {
    const loaded = new Set();
    if (!tagsByProject || typeof tagsByProject !== 'object') return loaded;
    for (const [name, tags] of Object.entries(tagsByProject)) {
      loaded.add(name);
      setProjectTags(name, tags);
    }
    return loaded;
  }

  /** Normalize a tag for comparisons. */
  function normalizeTagValue(tag) {
    return String(tag || '').trim().toLowerCase();
  }

  /** Return a sorted list of known tags across projects. */
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

  /** Render tags for the inline project editor. */
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

  /** Fetch tags for a project and optionally store them. */
  async function fetchProjectTags(name, { store = true } = {}) {
    const data = await api.fetchProjectTags(name);
    const tags = Array.isArray(data.tags) ? data.tags.map((t) => String(t)) : [];
    if (store) {
      setProjectTags(name, tags);
    }
    return tags;
  }

  /** Fetch tags for all projects and merge into cache. */
  async function fetchAllProjectTags() {
    const data = await api.fetchAllProjectTags();
    const tagsByProject = (data && typeof data.tagsByProject === 'object') ? data.tagsByProject : {};
    const loaded = applyTagsByProject(tagsByProject);
    return { tagsByProject, loaded };
  }

  /** Render tag pills in the project card header. */
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

  Taskman.tags = {
    getProjectTags,
    setProjectTags,
    moveProjectTags,
    deleteProjectTags,
    applyTagsByProject,
    normalizeTagValue,
    getAllKnownTags,
    renderTagList,
    fetchProjectTags,
    fetchAllProjectTags,
    renderCardTags
  };
})();
