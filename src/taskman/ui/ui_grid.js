// Shared Grid.js helpers for UI modules.
/** Initialize Grid.js utilities for UI modules. */
(function () {
  const Taskman = window.Taskman = window.Taskman || {};
  const links = Taskman.links || {};

  /** Check whether Grid.js is available on the page. */
  function gridAvailable() {
    return !!(window.gridjs && typeof gridjs.Grid === 'function');
  }

  /** Render or update a Grid.js instance with optional height preservation. */
  function renderGrid(box, grid, gridConfig, opts = {}) {
    if (!box || !gridConfig) return grid;
    const preserveHeight = opts.preserveHeight !== false;
    const resetOnEmpty = opts.resetOnEmpty === true;
    const prevHeight = (grid && preserveHeight) ? box.offsetHeight : 0;
    if (prevHeight > 0) box.style.minHeight = `${prevHeight}px`;
    const dataLen = Array.isArray(gridConfig.data) ? gridConfig.data.length : 0;
    if (resetOnEmpty && grid && dataLen === 0) {
      if (typeof grid.destroy === 'function') grid.destroy();
      grid = null;
    }
    if (grid) {
      grid.updateConfig(gridConfig).forceRender(box);
    } else {
      grid = new gridjs.Grid(gridConfig);
      box.replaceChildren();
      grid.render(box);
    }
    if (prevHeight > 0) setTimeout(() => { box.style.minHeight = ''; }, 0);
    return grid;
  }

  /** Focus a Grid.js row by zero-based index with pagination awareness. */
  function focusGridRow(box, grid, rowIndex, opts = {}) {
    if (!box || rowIndex == null) return;
    const idx = Number(rowIndex);
    if (!Number.isFinite(idx) || idx < 0) return;
    const limit = (grid && grid.config && grid.config.pagination && grid.config.pagination.limit)
      ? Number(grid.config.pagination.limit)
      : null;
    const delayMs = Number.isFinite(opts.delayMs) ? opts.delayMs : 80;
    const maxAttempts = Number.isFinite(opts.maxAttempts) ? opts.maxAttempts : 8;
    const pageSize = Number.isFinite(opts.pageSize)
      ? opts.pageSize
      : (Number.isFinite(limit) && limit > 0 ? limit : 20);
    const targetPage = Math.floor(idx / pageSize) + 1;
    const rowInPage = idx % pageSize;
    console.log('[Taskman.grid] focusGridRow', {
      rowIndex: idx,
      pageSize,
      targetPage,
      rowInPage
    });

    /** Get the current page number from the pagination UI. */
    const getCurrentPage = () => {
      const currentBtn = box.querySelector('.gridjs-pages button[aria-current="true"], .gridjs-pages button.active');
      if (!currentBtn) return 1;
      const attr = currentBtn.getAttribute('data-page');
      const raw = attr ? attr : currentBtn.textContent.trim();
      const page = Number(raw);
      return Number.isFinite(page) && page > 0 ? page : 1;
    };

    /** Click the pagination button for the given page number. */
    const clickPageButton = (page) => {
      const pages = box.querySelector('.gridjs-pages');
      if (!pages) {
        console.log('[Taskman.grid] focusGridRow: pagination container not found');
        return false;
      }
      const buttons = Array.from(pages.querySelectorAll('button'));
      const targetBtn = buttons.find((btn) => {
        const attr = btn.getAttribute('data-page');
        const raw = attr ? attr : btn.textContent.trim();
        const num = Number(raw);
        return Number.isFinite(num) && num === page;
      });
      if (targetBtn && !targetBtn.disabled) {
        console.log('[Taskman.grid] focusGridRow: clicking page button', { page });
        targetBtn.click();
        return true;
      }
      console.log('[Taskman.grid] focusGridRow: page button missing or disabled', { page });
      return false;
    };

    /** Attempt to scroll to the target row in the current page. */
    const tryScrollToTargetRow = () => {
      const rows = box.querySelectorAll('table.gridjs-table tbody tr');
      const row = rows && rows.length ? rows[rowInPage] : null;
      if (row) {
        console.log('[Taskman.grid] focusGridRow: scrolling to row', { rowInPage, rows: rows.length });
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return true;
      }
      console.log('[Taskman.grid] focusGridRow: row not found on page', { rowInPage, rows: rows.length });
      return false;
    };

    /** Retry focusing until the page renders or attempts are exhausted. */
    const attemptFocus = (attempt) => {
      const currentPage = getCurrentPage();
      console.log('[Taskman.grid] focusGridRow: attempt', { attempt, currentPage, targetPage });
      let onTargetPage = true;
      if (currentPage !== targetPage) {
        onTargetPage = clickPageButton(targetPage);
        if (onTargetPage) {
          console.log('[Taskman.grid] focusGridRow: waiting for page render', { delayMs });
        } else {
          console.log('[Taskman.grid] focusGridRow: retrying page click', { delayMs });
        }
      }
      if (onTargetPage && setTimeout(() => { tryScrollToTargetRow() }, delayMs)) {
        if (typeof opts.onDone === 'function') opts.onDone();
        return;
      }
      if (attempt < maxAttempts) {
        setTimeout(() => attemptFocus(attempt + 1), delayMs);
        return;
      }
    };

    attemptFocus(0);

  }

  /** Build a Grid.js cell formatter for task links. */
  function makeTaskLinkFormatter(projectIdx, summaryIdx, idIdx) {
    return (_, row) => {
      const project = row?.cells?.[projectIdx]?.data || '';
      const summary = row?.cells?.[summaryIdx]?.data || '';
      const taskId = row?.cells?.[idIdx]?.data;
      const href = typeof links.buildTaskLink === 'function' ? links.buildTaskLink(project, taskId) : '';
      if (!href) return '';
      const label = typeof links.taskLinkLabel === 'function' ? links.taskLinkLabel(summary) : 'View task';
      const icon = links.taskLinkIcon || '';
      return gridjs.h('a', {
        className: 'btn btn-icon',
        href,
        title: label,
        'aria-label': label
      }, icon ? gridjs.html(icon) : label);
    };
  }

  Taskman.grid = { available: gridAvailable, renderGrid, focusGridRow, makeTaskLinkFormatter };
})();
