// Lightweight reusable free-text filter with dropdown suggestions, add, and clear actions.
// Usage:
//   const control = window.createFreeTextFilter({
//     placeholder: 'Filter...',
//     getSuggestions: (text) => [...], // return array of strings
//     onAdd: (value) => {},            // called when user confirms with Enter/Add/click
//     onClear: () => {}                // called when Clear pressed
//   });
//   container.appendChild(control.root);
//   control.focus();
(function() {
  function createElement(tag, attrs = {}, ...children) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'class') n.className = v;
      else n.setAttribute(k, v);
    }
    for (const c of children) n.append(c);
    return n;
  }

  function createFreeTextFilter(opts = {}) {
    const {
      placeholder = 'Filter...',
      addLabel = 'Add',
      clearLabel = 'Clear',
      getSuggestions = () => [],
      onAdd = null,
      onClear = null
    } = opts;

    const root = createElement('div', { class: 'filter-row' });
    const wrapper = createElement('div', { class: 'filter-input-wrapper' });
    const input = createElement('input', {
      type: 'text',
      class: 'inline-input filter-input',
      placeholder,
      autocomplete: 'off',
      'aria-label': placeholder
    });
    const suggestionBox = createElement('div', { class: 'filter-suggestions', hidden: true });
    wrapper.append(input, suggestionBox);

    const addBtn = createElement('button', { type: 'button', class: 'btn btn-sm' }, addLabel);
    const clearBtn = createElement('button', { type: 'button', class: 'btn btn-sm btn-ghost' }, clearLabel);
    root.append(wrapper, addBtn, clearBtn);

    let suggestions = [];
    let highlightedIndex = -1;

    // Render dropdown; only show when the input is focused.
    const renderSuggestions = () => {
      const shouldShow = document.activeElement === input;
      suggestionBox.replaceChildren();
      if (!suggestions.length || !shouldShow) {
        suggestionBox.hidden = true;
        return;
      }
      suggestions.forEach((t, idx) => {
        const item = createElement('div', { class: `filter-suggestion${idx === highlightedIndex ? ' active' : ''}` }, t);
        item.addEventListener('mousedown', (evt) => {
          evt.preventDefault();
          highlightedIndex = idx;
          input.value = t;
        });
        item.addEventListener('click', (evt) => {
          evt.preventDefault();
          highlightedIndex = idx;
          input.value = t;
          commit();
        });
        suggestionBox.append(item);
      });
      suggestionBox.hidden = false;
    };

    // Recompute suggestions whenever text changes/focuses.
    const refresh = () => {
      suggestions = Array.isArray(getSuggestions(input.value)) ? getSuggestions(input.value) : [];
      highlightedIndex = suggestions.length ? 0 : -1;
      renderSuggestions();
    };

    // Confirm current value and reset UI.
    const commit = () => {
      const val = (input.value || '').trim();
      if (!val) return;
      if (typeof onAdd === 'function') onAdd(val);
      input.value = '';
      suggestions = [];
      highlightedIndex = -1;
      suggestionBox.hidden = true;
      input.blur();
    };

    addBtn.addEventListener('click', commit);
    clearBtn.addEventListener('click', () => {
      input.value = '';
      suggestions = [];
      highlightedIndex = -1;
      suggestionBox.hidden = true;
      if (typeof onClear === 'function') onClear();
    });

    input.addEventListener('focus', refresh);
    input.addEventListener('input', refresh);
    input.addEventListener('keydown', (evt) => {
      if (evt.key === 'Tab') {
        if (suggestions.length) {
          evt.preventDefault();
          input.value = suggestions[0];
          highlightedIndex = 0;
          renderSuggestions();
        }
        return;
      }
      if (evt.key === 'ArrowDown' || evt.key === 'ArrowUp') {
        suggestions = suggestions.length ? suggestions : (Array.isArray(getSuggestions(input.value)) ? getSuggestions(input.value) : []);
        if (!suggestions.length) return;
        evt.preventDefault();
        const delta = evt.key === 'ArrowDown' ? 1 : -1;
        const len = suggestions.length;
        if (highlightedIndex < 0) {
          highlightedIndex = delta === 1 ? 0 : len - 1;
        } else {
          highlightedIndex = (highlightedIndex + delta + len) % len;
        }
        input.value = suggestions[highlightedIndex];
        renderSuggestions();
        return;
      }
      if (evt.key === 'Enter') {
        evt.preventDefault();
        commit();
      }
      if (evt.key === 'Escape') {
        evt.preventDefault();
        input.value = '';
        suggestions = [];
        highlightedIndex = -1;
        suggestionBox.hidden = true;
      }
    });

    input.addEventListener('blur', () => {
      // Delay closing to allow click events on the suggestion items to fire.
      setTimeout(() => { suggestionBox.hidden = true; }, 100);
    });

    return {
      root,
      focus: () => input.focus(),
      getValue: () => input.value,
      setPlaceholder: (text) => { input.placeholder = text; },
      refresh
    };
  }

  window.createFreeTextFilter = createFreeTextFilter;
})();
