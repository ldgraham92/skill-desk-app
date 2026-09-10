'use strict';
let providerData=null;
let manageData={installed:[],archived:[]}, activeDraft=null, activeJob=null, manageFilter='All', lastManage='';
const manageNav=document.createElement('button');manageNav.dataset.view='manage';manageNav.textContent='Manage';$('#mainnav').append(manageNav);
const originalRender=render;
render=function(){if(view==='manage'){renderManage();renderProviderControls();}else originalRender();};
function renderManage(){
 document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
 document.querySelectorAll('[data-category]').forEach(b=>b.classList.remove('active'));
 const rows=manageData.installed.filter(s=>matchesHarness(s)&&(manageFilter==='All'||s.kind===manageFilter)&&query.toLowerCase().trim().split(/\s+/).every(t=>[s.name,s.description,s.kind,s.source].join(' ').toLowerCase().includes(t)));
 $('#content').innerHTML=`<div class="page manage-page"><div class="manage-heading"><div><span class="eyebrow">YOUR SKILL LIBRARY</span><h1>Manage skills</h1><p class="lead">Create a skill or bring one in. Available across projects in your selected local library.</p></div><div class="manage-actions"><button class="button" id="import-skill">Import skill</button><button class="button primary" id="create-skill">Create skill</button></div></div><div id="provider-controls"></div><div class="manage-filters">${['All','User Created','Repo Installed','Markdown Imported','Harness Copy','Existing'].map(k=>`<button class="button ${manageFilter===k?'primary':''}" data-origin="${k}">${k}</button>`).join('')}</div><p class="manage-note">${manageData.installed.length} installed · Removal archives the skill, so you can restore it later.</p><div class="manage-list">${rows.map(s=>`<article class="manage-row"><div><h2>${esc(s.name)}</h2><span class="tag">${esc(s.kind)}</span>${harnessBadges(s)}${s.linked?'<span class="tag">Linked folder</span>':''}<p>${esc(s.description)}</p><details><summary>Source</summary><p class="source-path">${esc(s.source)}</p></details>${s.error?`<p class="form-error">${esc(s.error)}</p>`:''}</div>${s.readOnly?'<span class="manage-note">Managed by its source CLI</span>':`<button class="button remove-button" data-remove="${esc(s.id)}">Remove</button>`}</article>`).join('')||'<p class="empty">No skills in this section yet.</p>'}</div><details class="archive-list"><summary>Removed skills (${manageData.archived.length})</summary>${manageData.archived.map(s=>`<div class="archive-row"><span>${esc(s.id)}<small>${esc(new Date(s.archived_at).toLocaleDateString())}</small></span><button class="button" data-restore="${esc(s.token)}">Restore</button></div>`).join('')}</details><p class="manage-note">Existing means installed outside Skill-Desk. New imports and creations have their source recorded automatically.</p></div>`;
}
const modal=document.createElement('dialog');modal.className='skill-dialog';modal.innerHTML='<div id="dialog-body"></div>';document.body.append(modal);
function showDialog(body){$('#dialog-body').innerHTML=body;if(!modal.open)modal.showModal();}
function errorMessage(message){const el=$('#form-message');if(el){el.textContent=message;el.className='form-error';}else toast(message);}
function dialogHeader(title){return `<div class="dialog-heading"><h2>${title}</h2><button class="button" type="button" id="close-dialog" aria-label="Close dialog">Close</button></div>`;}
async function api(path,body){const options=body===undefined?{signal:AbortSignal.timeout(15000)}:{method:'POST',headers:{'Content-Type':'application/json','X-Skill-Desk-Token':window.skillDeskToken},body:JSON.stringify(body)};const response=await fetch(path,options);const data=await response.json().catch(()=>({error:'Request failed'}));if(!response.ok){const error=Error(data.error||'Request failed');error.status=response.status;throw error;}return data;}
async function loadManage(){try{const next=await api('/api/manage');const signature=JSON.stringify(next);manageData=next;if(view==='manage'&&!modal.open&&signature!==lastManage)renderManage();lastManage=signature;renderProviderControls();}catch(e){if(view==='manage')toast(e.message);}}
function createForm(){showDialog(dialogHeader('Create a skill')+`<form id="create-form"><label for="skill-brief">What should this skill help you do?</label><textarea id="skill-brief" required maxlength="30000" rows="9" placeholder="Describe the purpose, when to use it, the steps or rules that matter, and the result you want. Include an example request if useful."></textarea><label class="checkbox-label"><input type="checkbox" id="explicit-skill"> Only use when I explicitly request it</label><p class="manage-note">Uses your selected authoring CLI with the installed skill-authoring guidance. You can review the generated instructions before installing.</p><p id="form-message" role="status"></p><button class="button primary" type="submit">Generate preview</button></form>`);}
function importForm(){showDialog(dialogHeader('Import a skill')+`<form id="import-form"><label for="import-mode">Import from</label><select id="import-mode"><option value="markdown">Markdown text or file</option><option value="github">GitHub repository</option></select><div id="markdown-fields"><label for="md-file">Markdown file</label><input type="file" id="md-file" accept=".md,.markdown,text/markdown,text/plain"><label for="md-content">Or paste Markdown</label><textarea id="md-content" rows="7" maxlength="200000" placeholder="Paste SKILL.md, including its YAML name and description."></textarea><details><summary>Ordinary Markdown without skill metadata?</summary><label for="md-name">Skill name</label><input id="md-name" placeholder="my-skill" maxlength="63"><label for="md-description">When should Codex use this skill?</label><input id="md-description" maxlength="1024"></details></div><div id="github-fields" hidden><label for="repo-url">GitHub URL</label><input type="url" id="repo-url" placeholder="https://github.com/owner/repository"><label for="repo-ref">Branch or tag <small>optional</small></label><input id="repo-ref" placeholder="Repository default"><label for="repo-path">Skill folder <small>optional</small></label><input id="repo-path" placeholder="skills/my-skill"><p class="manage-note">Repository imports preserve the complete skill folder, including references, scripts, licenses, and invocation settings. For branch names containing slashes, use the repository URL and enter the full branch here.</p></div><p id="form-message" role="status"></p><button class="button primary" type="submit">Preview import</button></form>`);}
function previewDraft(result){activeDraft=result;showDialog(dialogHeader('Review skill')+(result.targetHarness?`<p>Install a separate copy in ${harnessLabel(result.targetHarness)}. All included files are preserved. Review any harness-specific tools or instructions before using the copy.</p>`:'')+`<p><span class="tag">${esc(result.kind)}</span></p>${result.candidates.length>1?`<label for="candidate">Choose a skill to install</label><select id="candidate">${result.candidates.map(s=>`<option value="${esc(s.candidate)}">${esc(s.name)}</option>`).join('')}</select>`:''}<div id="candidate-preview"></div><p id="form-message" role="status"></p><div class="manage-actions"><button class="button" id="discard-draft">Discard preview</button><button class="button primary" id="install-draft">${result.targetHarness?'Install in '+harnessLabel(result.targetHarness):'Install globally'}</button></div>`);renderCandidate();}
function selectedCandidate(){return activeDraft.candidates.find(x=>x.candidate===($('#candidate')?.value||activeDraft.candidates[0].candidate));}
function renderCandidate(){const s=selectedCandidate();$('#candidate-preview').innerHTML=`<h3>${esc(s.name)}</h3><p>${esc(s.description)}</p><p class="manage-note">${esc(s.invocation)} · ${s.files.length} files</p><details><summary>Included files</summary><ul>${s.files.map(f=>`<li>${esc(f)}</li>`).join('')}</ul></details><pre class="skill-preview">${esc(s.content)}</pre>${s.conflict?`<p class="form-error">${esc(s.conflict)}</p>`:''}`;$('#install-draft').disabled=!!s.conflict;}
let jobState=null, jobConnectionLost=false;
const jobBanner=document.createElement('section');jobBanner.id='skill-job-banner';jobBanner.hidden=true;
jobBanner.setAttribute('aria-label','Skill preparation status');$('.topbar').after(jobBanner);
function elapsedJob(){
 if(!jobState?.started_at)return 'Starting…';
 const seconds=Math.max(0,Math.floor((jobState.finished_at||Date.now()/1000)-jobState.started_at));
 return seconds<60?`${seconds}s elapsed`:`${Math.floor(seconds/60)}m ${String(seconds%60).padStart(2,'0')}s elapsed`;
}
function jobTitle(){return jobConnectionLost?'Connection interrupted':jobState?.message||'Preparing your skill';}
function jobHint(){
 if(jobConnectionLost)return 'Retrying the status connection. The server may still be working.';
 if(jobState?.status==='complete')return 'Your preview is ready. Review it before installing globally.';
 if(jobState?.status==='failed')return 'No skill was installed by this job. Dismiss this status to try again.';
 if(jobState?.phase==='generating')return 'Waiting for the authoring CLI to return the draft. This can take a few minutes.';
 return 'You can continue browsing. This job will keep running.';
}
function paintJob(){
 if(!jobState){jobBanner.hidden=true;return;}
 const running=jobState.status==='running';jobBanner.hidden=false;
 const label=jobState.status==='complete'?'Review skill':running?'View progress':'View error';
 const markup=`<div class="job-status-main"><span class="job-indicator ${running?'is-running':''}" aria-hidden="true">${running?'':jobState.status==='complete'?'✓':'!'}</span><div><strong class="job-title" role="status">${esc(jobTitle())}</strong><p>${esc(jobHint())}</p></div></div><span class="job-elapsed">${elapsedJob()}</span><button class="button" id="view-skill-job">${label}</button>${jobState.status==='failed'?'<button class="button" id="dismiss-skill-job">Dismiss</button>':''}`;
 // Keep the controls in place so the timer does not disrupt focus or clicks.
 const signature=JSON.stringify([jobState.status,jobState.phase,jobState.message,jobConnectionLost]);
 if(jobBanner.dataset.signature!==signature){jobBanner.innerHTML=markup;jobBanner.dataset.signature=signature;}
 else jobBanner.querySelector('.job-elapsed').textContent=elapsedJob();
 const progress=$('#job-progress');
 if(progress){
  progress.querySelector('.job-title').textContent=jobTitle();
  progress.querySelector('.job-hint').textContent=jobHint();
  progress.querySelector('.job-elapsed').textContent=elapsedJob();
  progress.querySelectorAll('[data-stage]').forEach(el=>{
   const steps=['preparing',jobState.action==='import'?'downloading':'generating','validating'];
   const index=steps.indexOf(jobState.phase),current=steps.indexOf(el.dataset.stage);
   el.classList.toggle('current',current===index);el.classList.toggle('done',current<index);
  });
 }
}
function showJobProgress(){
 if(jobState?.status==='complete'&&activeDraft){previewDraft(activeDraft);return;}
 if(jobState?.status==='failed'){showDialog(dialogHeader('Could not prepare skill')+'<p id="form-message" role="alert"></p>');errorMessage(jobState.message);return;}
 const steps=jobState?.action==='import'?[['preparing','Read import'],['downloading','Fetch files'],['validating','Validate']]:[['preparing','Prepare'],['generating','Write with AI'],['validating','Validate']];
 showDialog(dialogHeader('Preparing your skill')+`<div id="job-progress"><div class="job-status-main"><span class="job-indicator is-running" aria-hidden="true"></span><h3 class="job-title" role="status"></h3></div><p class="job-hint"></p><p class="job-elapsed" aria-live="off"></p><ol class="job-stages">${steps.map(([id,label])=>`<li data-stage="${id}">${label}</li>`).join('')}</ol><p class="manage-note">Closing this dialog does not cancel the job. Its status stays above the page.</p></div>`);
 $('#close-dialog').textContent='Continue browsing';paintJob();
}
function clearJobStatus(){jobState=null;activeJob=null;jobConnectionLost=false;try{sessionStorage.removeItem('skill-desk-job');}catch{}paintJob();}
async function waitForJob(id){
 activeJob=id;try{sessionStorage.setItem('skill-desk-job',id);}catch{}
 jobState={status:'running',phase:'preparing',started_at:Date.now()/1000,message:'Connecting to job status'};
 showJobProgress();paintJob();
 while(activeJob===id){
  try{
   const job=await api('/api/jobs/'+id);const actionChanged=jobState.action!==job.action;jobConnectionLost=false;jobState=job;
   if(actionChanged&&job.status==='running'&&modal.open&&$('#job-progress'))showJobProgress();
   if(job.status==='complete'){
    activeJob=null;activeDraft=job.result;const wasViewing=modal.open&&!!$('#job-progress');paintJob();
    if(wasViewing)previewDraft(job.result);else toast('Your skill is ready to review');return;
   }
   if(job.status==='failed'){activeJob=null;paintJob();if(modal.open&&$('#job-progress'))showJobProgress();return;}
   paintJob();
  }catch(e){
   if(e.status===404){activeJob=null;jobConnectionLost=false;jobState={...jobState,status:'failed',finished_at:Date.now()/1000,message:'This job is no longer available. The server may have restarted.'};paintJob();if(modal.open&&$('#job-progress'))showJobProgress();return;}
   jobConnectionLost=true;paintJob();
  }
  await new Promise(r=>setTimeout(r,1500));
 }
}
async function startJob(action,payload){try{const data=await api('/api/'+action,payload);await waitForJob(data.job);}catch(e){errorMessage(e.message);}}
modal.addEventListener('submit',async e=>{e.preventDefault();const button=e.target.querySelector('button[type="submit"]');button.disabled=true;
 try{if(e.target.id==='create-form')await startJob('create',{brief:$('#skill-brief').value,explicit:$('#explicit-skill').checked});
 else await startJob('import',{mode:$('#import-mode').value,content:$('#md-content').value,name:$('#md-name').value,description:$('#md-description').value,filename:$('#md-file').files[0]?.name,url:$('#repo-url').value,ref:$('#repo-ref').value,path:$('#repo-path').value});}
 finally{button.disabled=false;}});
modal.addEventListener('change',async e=>{if(e.target.id==='import-mode'){const github=e.target.value==='github';$('#markdown-fields').hidden=github;$('#github-fields').hidden=!github;}if(e.target.id==='candidate')renderCandidate();if(e.target.id==='md-file'){const file=e.target.files[0];if(file){if(file.size>200000){errorMessage('Choose a Markdown file of up to 200 KB.');e.target.value='';return;}$('#md-content').value=await file.text();}}});
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;
 try{
 if(b.id==='create-skill'||b.id==='import-skill'){if(activeJob){showJobProgress();return;}if(activeDraft){previewDraft(activeDraft);return;}b.id==='create-skill'?createForm():importForm();}
 if(b.id==='view-skill-job')showJobProgress();
 if(b.id==='dismiss-skill-job'){clearJobStatus();if(modal.open)modal.close();}
 if(b.id==='close-dialog')modal.close();
 if(b.dataset.origin){manageFilter=b.dataset.origin;renderManage();}
 if(b.dataset.view==='manage')await loadManage();
 if(b.id==='discard-draft'){await api('/api/discard',{draft:activeDraft.draft});activeDraft=null;clearJobStatus();modal.close();}
 if(b.id==='install-draft'){b.disabled=true;const s=selectedCandidate();await api('/api/install',{draft:activeDraft.draft,candidate:s.candidate});await api('/api/discard',{draft:activeDraft.draft});activeDraft=null;clearJobStatus();modal.close();await loadManage();await syncCatalog();toast('Skill installed globally');}
 if(b.dataset.remove){const s=manageData.installed.find(x=>x.id===b.dataset.remove);showDialog(dialogHeader('Remove '+esc(s.name)+'?')+`<p>This removes the skill from global discovery and keeps an archived copy for restoration.${s.linked?' Only the link is moved; its target folder is preserved.':''}</p><p id="form-message" role="status"></p><button class="button primary" id="confirm-remove">Remove and archive</button>`);$('#confirm-remove').onclick=async()=>{try{await api('/api/archive',{id:s.id,fingerprint:s.fingerprint});modal.close();await loadManage();await syncCatalog();toast('Skill removed and archived');}catch(e){errorMessage(e.message);}};}
 if(b.dataset.restore){b.disabled=true;await api('/api/restore',{token:b.dataset.restore});await loadManage();await syncCatalog();toast('Skill restored');}
 }catch(e){errorMessage(e.message);b.disabled=false;}
});
loadManage();

window.addEventListener('skilldesk-change',()=>{if(view==='manage')loadManage();});
try{const job=sessionStorage.getItem('skill-desk-job');if(job)waitForJob(job);}catch{}

function renderProviderControls(){
 const el=$('#provider-controls');if(!el||!providerData)return;
 el.innerHTML=`<label for="author-provider">Author with</label><select id="author-provider">${providerData.providers.map(p=>`<option value="${p.id}" ${p.id===providerData.selected?'selected':''} ${!p.installed?'disabled':''}>${p.label}${p.installed?'':' · CLI not installed'}</option>`).join('')}</select><p class="manage-note">Uses the selected CLI's existing login. Generation uses that provider account. Installed does not mean signed in.<br>New skills install to: <code>${esc(providerData.root)}</code><br>Scanned folders: ${(providerData.libraries||[providerData.root]).map(p=>`<code>${esc(p)}</code>`).join('<br>')}</p>`;
}
async function loadProviders(){try{providerData=await api('/api/providers');renderProviderControls();}catch(e){toast(e.message);}}
document.addEventListener('change',async e=>{if(e.target.id!=='author-provider')return;e.target.disabled=true;try{await api('/api/provider',{provider:e.target.value});await loadProviders();toast('Authoring provider updated');}catch(error){toast(error.message);renderProviderControls();}});
loadProviders();

let harnessFilter='all';
try{harnessFilter=localStorage.getItem('skill-desk-harness')||'all';}catch{}
if(!['all','codex','claude'].includes(harnessFilter))harnessFilter='all';
const harnessLabel=h=>h==='claude'?'Claude':'Codex';
const harnessSelect=document.createElement('select');
harnessSelect.id='skill-harness';harnessSelect.setAttribute('aria-label','Skill harness');
harnessSelect.innerHTML='<option value="all">All</option><option value="codex">Codex</option><option value="claude">Claude</option>';
harnessSelect.value=harnessFilter;$('#print').before(harnessSelect);
const matchesHarness=s=>harnessFilter==='all'||(s.harnesses||[]).includes(harnessFilter);
const originalFiltered=filtered;
filtered=function(){return originalFiltered().filter(matchesHarness);};
const originalDetail=detail;
function harnessBadges(s){return (s.harnesses||[]).map(h=>`<span class="tag">${harnessLabel(h)}</span>`).join('');}
function harnessActions(s){
 const missing=['codex','claude'].filter(h=>!(s.installedHarnesses||s.harnesses||[]).includes(h));
 return `<div class="harness-actions">${harnessBadges(s)}${missing.map(h=>`<button class="button" data-copy-harness="${h}" data-copy-skill="${esc(s.id)}">Install in ${harnessLabel(h)}</button>`).join('')}</div>`;
}
detail=function(s){return originalDetail(s).replace(`<h1>${esc(s.id)}</h1>`,`<h1>${esc(s.name||s.title)}</h1>`).replace('<div class="columns">',harnessActions(s)+'<div class="columns">').replace('Try this in Codex','Try this in '+harnessLabel((s.harnesses||['codex'])[0]));};
const renderWithManagement=render;
render=function(){
 renderWithManagement();
 $('#printguide').innerHTML='<h1>Skills · '+(harnessFilter==='all'?'All':harnessLabel(harnessFilter))+'</h1>'+skills.filter(matchesHarness).map(s=>`<article><h2>${esc(s.name||s.title)}</h2><p>${esc(s.summary)}</p><pre>${esc(s.prompt)}</pre></article>`).join('');
 document.querySelectorAll('.skill-row').forEach(el=>{
  const s=skills.find(x=>x.id===el.dataset.skill);if(!s)return;
  el.querySelector('.row-name').textContent=s.name||s.title;
  if(harnessFilter==='all')el.querySelector('.row-meta').insertAdjacentHTML('beforeend','<br>'+harnessBadges(s));
 });
};
harnessSelect.addEventListener('change',()=>{
 harnessFilter=harnessSelect.value;
 try{localStorage.setItem('skill-desk-harness',harnessFilter);}catch{}
 if(view==='overview')view='all';
 render();
});
document.addEventListener('click',async e=>{
 const b=e.target.closest('[data-copy-harness]');if(!b)return;
 if(activeDraft||activeJob){toast('Finish or discard the current preview first.');return;}
 b.disabled=true;
 try{
  const result=await api('/api/copy-preview',{id:b.dataset.copySkill,target:b.dataset.copyHarness});
  previewDraft(result);
 }catch(error){toast(error.message);}finally{b.disabled=false;}
});
render();
