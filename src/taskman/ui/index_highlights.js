// Highlights table rendering for the index page.
/** Initialize highlights rendering for the index page. */
(function () {
  const Taskman = window.Taskman = window.Taskman || {};
  const { renderTable } = Taskman.utils;
  const grid = Taskman.grid || {};
  const api = Taskman.api;
  let highlightsGrid = null;

  /** Fetch highlights and render the highlights table. */
  async function refreshHighlights() {
    try {
      const data = await api.listHighlights();
      const box = document.getElementById('highlights');
      const items = Array.isArray(data.highlights) ? data.highlights : [];
      if (items.length === 0) {
        box.textContent = 'No highlights yet.';
        if (highlightsGrid && typeof highlightsGrid.destroy === 'function') highlightsGrid.destroy();
        highlightsGrid = null;
        return;
      }
      if (!grid.available || !grid.available()) {
        if (highlightsGrid && typeof highlightsGrid.destroy === 'function') highlightsGrid.destroy();
        highlightsGrid = null;
        const rows = items.map((h) => [
          h.project || '',
          h.summary || '',
          h.assignee || '',
          h.status || '',
          h.priority || ''
        ]);
        const table = renderTable(['Project', 'Summary', 'Assignee', 'Status', 'Priority'], rows);
        box.replaceChildren(table);
        return;
      }
      const rows = items.map((h) => ([
        h.project || '',
        h.summary || '',
        h.assignee || '',
        h.status || '',
        h.priority || '',
        h.id
      ]));
      const gridConfig = {
        columns: ['Project', 'Summary', 'Assignee', 'Status', 'Priority', { id: 'task_link', name: '', sort: false, formatter: grid.makeTaskLinkFormatter(0, 1, 5) }],
        data: rows,
        sort: true,
        search: true,
        pagination: { limit: 10 },
        style: { table: { tableLayout: 'auto' } }
      };
      highlightsGrid = grid.renderGrid ? grid.renderGrid(box, highlightsGrid, gridConfig, { preserveHeight: true }) : highlightsGrid;
    } catch (e) {
      document.getElementById('highlights').textContent = `Error: ${e.message}`;
    }
  }

  Taskman.highlights = { refreshHighlights };
})();
