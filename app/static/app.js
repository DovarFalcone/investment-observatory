document.querySelectorAll('[data-dialog-open]').forEach((button) => {
  button.addEventListener('click', () => document.getElementById(button.dataset.dialogOpen)?.showModal());
});

document.querySelectorAll('dialog').forEach((dialog) => {
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });
});

const searchForm = document.querySelector('[data-search-form]');
const results = document.querySelector('[data-search-results]');
if (searchForm && results) {
  searchForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const query = new FormData(searchForm).get('q');
    results.innerHTML = '<p class="muted">Searching…</p>';
    try {
      const response = await fetch(`/api/securities/search?q=${encodeURIComponent(query)}`);
      const candidates = await response.json();
      results.innerHTML = candidates.length ? candidates.map((candidate) => `
        <form method="post" action="/items" class="candidate">
          <input type="hidden" name="symbol" value="${escapeHtml(candidate.symbol)}">
          <input type="hidden" name="name" value="${escapeHtml(candidate.name)}">
          <input type="hidden" name="asset_type" value="${escapeHtml(candidate.asset_type)}">
          <input type="hidden" name="exchange" value="${escapeHtml(candidate.exchange || '')}">
          <input type="hidden" name="currency" value="${escapeHtml(candidate.currency || '')}">
          <input type="hidden" name="provider_symbol" value="${escapeHtml(candidate.provider_symbol)}">
          <div><strong>${escapeHtml(candidate.symbol)}</strong><small>${escapeHtml(candidate.name)} · ${escapeHtml(candidate.asset_type.replace('_', ' '))}${candidate.exchange ? ` · ${escapeHtml(candidate.exchange)}` : ''}</small></div>
          <select name="kind" aria-label="List for ${escapeHtml(candidate.symbol)}"><option value="watchlist">Watchlist</option><option value="holdings">Holdings</option></select>
          <button class="button button-small" type="submit">Add</button>
        </form>`).join('') : '<p class="muted">No confident matches. Try a ticker symbol.</p>';
    } catch (_) {
      results.innerHTML = '<p class="error-text">Search is unavailable. Try again later.</p>';
    }
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;'}[character]));
}
