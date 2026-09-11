(() => {
  const state = __UPDATE_STATE__;
  const bar = document.querySelector('.topbar');
  if (!bar) return;
  const openUpdates = () => { location.href = 'skilldesk://updates'; };
  let updates = document.getElementById('app-updates');
  if (!updates) {
    updates = document.createElement('button');
    updates.id = 'app-updates';
    updates.className = 'button';
    updates.textContent = 'Updates';
    updates.onclick = openUpdates;
    bar.append(updates);
  }
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;
  let notice = document.getElementById('app-update-notice');
  if (!notice) {
    const style = document.createElement('style');
    style.textContent = `
      .sidebar .workflow { min-height:0; overflow-y:auto; }
      #app-update-notice { margin-top:auto; padding-top:20px; flex-shrink:0; }
      #app-update-notice[hidden] { display:none; }
      #app-update-notice:not([hidden]) ~ footer { margin-top:16px; padding-top:16px; }
      #app-update-ready { display:flex; align-items:center; gap:10px; width:100%;
        padding:10px 12px; border:1px solid var(--accent); border-radius:8px;
        background:var(--wash); color:var(--accent); text-align:left; }
      #app-update-ready:hover { background:var(--hover); }
      #app-update-ready .update-icon { display:grid; place-items:center; flex:none;
        width:28px; height:28px; border-radius:50%; background:var(--accent); color:var(--on-accent, white); }
      #app-update-ready svg { width:17px; height:17px; fill:none; stroke:currentColor;
        stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }
      #app-update-ready .update-label { font-size:12px; font-weight:650; line-height:1.4; }
      @media(max-width:760px) { #app-update-notice { padding-top:14px; } #app-update-ready { width:auto; } }
    `;
    document.head.append(style);
    notice = document.createElement('div');
    notice.id = 'app-update-notice';
    notice.hidden = true;
    notice.innerHTML = '<button id="app-update-ready" type="button"><span class="update-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 3v12m-5-5 5 5 5-5M5 17v4h14v-4"/></svg></span><span class="update-label" aria-live="polite"></span></button>';
    notice.querySelector('button').onclick = openUpdates;
    sidebar.insertBefore(notice, sidebar.querySelector('footer'));
  }
  const labels = { available: 'Update Ready', downloading: 'Downloading update', waiting: 'Update waiting', installing: 'Installing update' };
  if (state.phase === 'available') notice.dataset.version = state.version || '';
  if (state.phase === 'current' || state.phase === 'idle') delete notice.dataset.version;
  let label = labels[state.phase];
  // Keep a discovered update visible during a recheck or a retryable error.
  // A successful check reporting no update clears the notice.
  if ((state.phase === 'checking' || state.phase === 'error') && notice.dataset.version) label = labels.available;
  notice.hidden = !label;
  const text = notice.querySelector('.update-label');
  if (text.textContent !== (label || '')) text.textContent = label || '';
  notice.querySelector('button').title = notice.dataset.version
    ? `Version ${notice.dataset.version} available. Open Updates to review and install.`
    : 'Open Updates';
})();
