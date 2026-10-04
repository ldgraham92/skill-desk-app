'use strict';
const skills = JSON.parse(document.getElementById('skill-data').textContent),
  $ = (s) => document.querySelector(s),
  esc = (s) =>
    String(s ?? '').replace(
      /[&<>"']/g,
      (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
    );
let saved = window.skillDeskSaved || [];
let view = 'all',
  category = '',
  selected = skills.some((s) => s.id === location.hash.slice(1))
    ? location.hash.slice(1)
    : 'diagnosing-bugs',
  query = '',
  timer;
const cats = ['Understand', 'Design', 'Build', 'Verify', 'Write', 'Continue'];
$('#categories').innerHTML = cats.map((c) => `<button data-category="${c}">${c}</button>`).join('');
const list = (a) => `<ul>${(a || []).map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`;
function toast(t) {
  $('#toast').textContent = t;
  clearTimeout(timer);
  timer = setTimeout(() => ($('#toast').textContent = ''), 3200);
}
function filtered() {
  let terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  return skills.filter(
    (s) =>
      (!category || s.category === category) &&
      (view !== 'saved' || saved.includes(s.id)) &&
      terms.every((t) => JSON.stringify(s).toLowerCase().includes(t)),
  );
}
function select(id) {
  selected = id;
  try {
    history.replaceState(null, '', '#' + id);
  } catch {
    location.hash = id;
  }
  render();
  $('.detail')?.scrollIntoView({ block: 'start' });
}
function detail(s) {
  return `<article class="detail"><div class="detail-top"><span class="eyebrow">${esc(s.category)} / SKILL</span><span class="source">${esc(s.source)}</span></div><h1>${esc(s.id)}</h1><p class="lead">${esc(s.summary)}</p><div><span class="tag">${esc(s.invocationLabel)}</span><button class="button" id="save" aria-pressed="${saved.includes(s.id)}">${saved.includes(s.id) ? 'Saved ✓' : 'Save skill'}</button></div><div class="columns"><section><h2>When to use</h2>${list(s.when)}</section><section><h2>What you'll notice</h2>${list(s.notice)}</section></div><div class="prompt"><div class="prompt-head"><span>Try this in Codex</span><button class="button primary" data-copy="${esc(s.id)}">Copy prompt</button></div><pre>${esc(skillPrompt(s))}</pre></div><div class="columns"><section><h2>What it does</h2><ol>${(s.steps || []).map((x) => `<li>${esc(x)}</li>`).join('')}</ol></section><section><h2>What you get</h2><p>${esc(s.output)}</p><h3>How it starts</h3><p>${esc(s.invocationText)}</p></section></div><div class="bottom"><h2>Limits to keep in mind</h2>${list(s.limits)}<details><summary>Source and local adaptations</summary><p>${esc(s.adaptation)}</p><div class="source-links"><a href="${esc(s.sourceUrl)}" target="_blank" rel="noopener">Read installed source</a> · <a href="${esc(s.localUrl)}">Open installed instructions</a></div></details><h3>Related skills</h3><div class="related">${(
    s.related || []
  )
    .filter((id) => skills.some((x) => x.id === id))
    .map((id) => `<button class="button" data-skill="${esc(id)}">${esc(id)}</button>`)
    .join('')}</div></div></article>`;
}
function skillName(s) {
  return s.name || s.id;
}
function promptProvider(s) {
  return typeof harnessFilter !== 'undefined' && harnessFilter !== 'all'
    ? harnessFilter
    : (s.harnesses || ['codex'])[0];
}
function skillInvocation(s) {
  return (
    (promptProvider(s) === 'opencode'
      ? 'Use the '
      : ['claude', 'cursor'].includes(promptProvider(s))
        ? '/'
        : '$') +
    skillName(s) +
    (promptProvider(s) === 'opencode' ? ' skill.' : '')
  );
}
function skillPrompt(s) {
  const name = skillName(s);
  const prompt = String(s.prompt || '').replace(
    new RegExp(
      '(^|[\\s`(])[$/]' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?=$|[\\s`,;!?)])',
      'g',
    ),
    (_, before) =>
      before + (promptProvider(s) === 'opencode' ? name + ' skill' : skillInvocation(s)),
  );
  return promptProvider(s) === 'opencode' && prompt.startsWith(name + ' skill')
    ? 'Use the ' + prompt
    : prompt;
}
function overview() {
  return `<div class="page"><h1>Your global skills</h1><p class="lead">Browse installed skills and copy an example prompt for your task.</p><p>This view reads registered project libraries and personal Codex, Claude Code, OpenCode, and Cursor skill directories. Your selected CLI writes reference guidance when a skill is added or its documentation changes. Use $skill-name in Codex, /skill-name in Claude Code or Cursor, and ask OpenCode to use the named skill. Installed invocation policies determine how each skill starts.</p><p>Descriptions are generated guidance. Open the installed instructions for the source.</p></div>`;
}
function reference() {
  return `<div class="page"><span class="eyebrow">Keep this beside your task</span><div class="reference-heading"><h1>Quick reference</h1><button class="button" id="print-cheatsheet" ${filtered().length ? '' : 'disabled'}>Print Cheatsheet</button></div><p class="lead">Choose by the job in front of you. Open an entry for a ready-to-copy example.</p><table class="reference"><thead><tr><th>Invoke</th><th>Use it to</th><th>Starts</th></tr></thead><tbody>${filtered()
    .map(
      (s) =>
        `<tr><td><button class="text-link" data-skill="${esc(s.id)}"><code>${esc(skillInvocation(s))}</code></button></td><td>${esc(s.summary)}</td><td>${esc(s.invocationLabel)}</td></tr>`,
    )
    .join(
      '',
    )}</tbody></table>${filtered().length ? '' : '<p>No matching skills. Try a shorter search.</p>'}<p class="check">Print the skills shown here, using the current search and provider filters.</p></div>`;
}
function render() {
  document
    .querySelectorAll('[data-view]')
    .forEach((b) => b.classList.toggle('active', b.dataset.view === view && !category));
  document
    .querySelectorAll('[data-category]')
    .forEach((b) => b.classList.toggle('active', b.dataset.category === category));
  if (view === 'overview') {
    $('#content').innerHTML = overview();
    return;
  }
  if (view === 'reference') {
    $('#content').innerHTML = reference();
    return;
  }
  let matches = filtered();
  if (!matches.some((s) => s.id === selected) && matches.length) selected = matches[0].id;
  let s = matches.find((s) => s.id === selected);
  $('#content').innerHTML =
    `<div class="workspace"><section class="skill-list" aria-label="Skills"><div class="list-head"><strong>${esc(category || (view === 'saved' ? 'Saved skills' : 'All skills'))}</strong><span>${matches.length} skills</span></div>${matches.map((x) => `<button class="skill-row ${x.id === selected ? 'active' : ''}" data-skill="${esc(x.id)}" aria-pressed="${x.id === selected}"><span class="row-name">${esc(x.id)}</span><span class="row-summary">${esc(x.summary)}</span><span class="row-meta">${esc(x.source)} · ${esc(x.category)}</span></button>`).join('') || '<p class="empty">No skills here yet. Try another search or save a skill from the full list.</p>'}</section>${s ? detail(s) : '<div class="detail"><h1>No matches</h1><p class="lead">Clear your search or choose All skills.</p><button class="button" id="reset">Show all skills</button></div>'}</div>`;
}
async function copy(id) {
  let text = skillPrompt(skills.find((s) => s.id === id));
  try {
    if (!navigator.clipboard) throw Error();
    await navigator.clipboard.writeText(text);
    toast('Prompt copied');
  } catch {
    let el = document.createElement('textarea');
    el.value = text;
    el.setAttribute('aria-label', 'Prompt to copy');
    el.style.cssText = 'position:fixed;left:0;top:0;width:1px;height:1px';
    document.body.append(el);
    el.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {}
    el.remove();
    if (ok) toast('Prompt copied');
    else {
      toast('Copy unavailable. Select the prompt text and copy it.');
      let p = document.querySelector('pre');
      if (p) {
        let r = document.createRange();
        r.selectNodeContents(p);
        let sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(r);
      }
    }
  }
}
document.addEventListener('click', async (e) => {
  let b = e.target.closest('button');
  if (!b) return;
  if (b.dataset.view) {
    view = b.dataset.view;
    category = '';
    query = '';
    $('#search').value = '';
    render();
  } else if (b.dataset.category) {
    category = b.dataset.category;
    view = 'all';
    render();
  } else if (b.dataset.skill) {
    let fromLink = !b.classList.contains('skill-row');
    if (fromLink) {
      view = 'all';
      category = '';
      query = '';
      $('#search').value = '';
    }
    select(b.dataset.skill);
    if (fromLink) {
      let h = $('.detail h1');
      if (h) {
        h.tabIndex = -1;
        h.focus({ preventScroll: true });
        h.scrollIntoView({ block: 'nearest' });
      }
    }
  } else if (b.dataset.copy) copy(b.dataset.copy);
  else if (b.id === 'save') {
    saved = saved.includes(selected) ? saved.filter((x) => x !== selected) : [...saved, selected];
    let persisted = true;
    try {
      const response = await fetch('/api/preferences', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Skill-Desk-Token': window.skillDeskToken,
        },
        body: JSON.stringify({ saved }),
      });
      if (!response.ok) throw Error('Could not save preferences');
    } catch {
      persisted = false;
    }
    render();
    $('#save')?.focus();
    toast(persisted ? 'Saved list updated' : 'Could not save favorites. Please retry.');
  } else if (b.id === 'reset') {
    view = 'all';
    category = '';
    query = '';
    $('#search').value = '';
    render();
  } else if (b.id === 'print-cheatsheet') printCheatsheet();
});
$('#search').addEventListener('input', (e) => {
  query = e.target.value;
  if (view === 'overview') view = 'all';
  render();
});
document.addEventListener('keydown', (e) => {
  if (
    e.key === '/' &&
    !e.ctrlKey &&
    !e.metaKey &&
    !e.altKey &&
    !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) &&
    !document.activeElement.isContentEditable
  ) {
    e.preventDefault();
    $('#search').focus();
  }
  if (e.key === 'Escape' && document.activeElement === $('#search')) {
    $('#search').value = '';
    query = '';
    render();
  }
});
function printCheatsheet() {
  const rows = filtered();
  if (!rows.length) return;
  $('#printguide').innerHTML =
    '<h1>Skill-Desk cheatsheet</h1><p>' +
    rows.length +
    ' ' +
    (rows.length === 1 ? 'skill' : 'skills') +
    ' · Current Quick Reference filters</p><table class="reference"><thead><tr><th>Invoke</th><th>Use it to</th><th>Starts</th></tr></thead><tbody>' +
    rows
      .map(
        (s) =>
          `<tr><td><code>${esc(skillInvocation(s))}</code></td><td>${esc(s.summary)}</td><td>${esc(s.invocationLabel)}</td></tr>`,
      )
      .join('') +
    '</tbody></table>';
  window.print();
}
render();
