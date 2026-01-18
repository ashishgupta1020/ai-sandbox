// Highlights table rendering for the index page.
/** Initialize highlights rendering for the index page. */
(function () {
  const Taskman = window.Taskman = window.Taskman || {};
  const { el, renderTable, gridAvailable } = Taskman.utils;
  const { makeTaskLinkFormatter } = Taskman.links;
  const api = Taskman.api;

  /** Fetch highlights and render the highlights table. */
  async function refreshHighlights() {
    try {
      const data = await api.listHighlights();
      const box = document.getElementById('highlights');
      const items = Array.isArray(data.highlights) ? data.highlights : [];
      if (items.length === 0) {
        box.textContent = 'No highlights yet.';
        return;
      }
      if (!gridAvailable()) {
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
      const grid = new gridjs.Grid({
        columns: ['Project', 'Summary', 'Assignee', 'Status', 'Priority', { name: '', sort: false, formatter: makeTaskLinkFormatter(0, 1, 5) }],
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

  Taskman.highlights = { refreshHighlights };
})();
