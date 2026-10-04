let lastCatalog = '';
document.querySelector('.subtitle').textContent = 'YOUR SKILL LIBRARY';
async function syncCatalog() {
  try {
    const response = await fetch('/api/skills', { cache: 'no-store' });
    if (!response.ok) throw Error('Sync unavailable');
    const data = await response.json();
    const signature = JSON.stringify(data.skills);
    if (signature !== lastCatalog) {
      lastCatalog = signature;
      skills.splice(0, skills.length, ...data.skills);
      render();
    }
    const footer = document.querySelector('.sidebar footer');
    footer.textContent = data.status;
    if (data.errors.length) {
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = 'Sync errors';
      details.append(summary);
      const text = document.createElement('pre');
      text.style.whiteSpace = 'pre-wrap';
      text.textContent = data.errors.join('\\n');
      details.append(text);
      footer.append(details);
    }
  } catch (e) {
    document.querySelector('.sidebar footer').textContent =
      'Server disconnected. Showing last loaded skills.';
  }
}
syncCatalog();
const catalogEvents = new EventSource('/api/events');
catalogEvents.onmessage = () => {
  syncCatalog();
  window.dispatchEvent(new Event('skilldesk-change'));
};
