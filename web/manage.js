'use strict';
let providerData=null, packageInstalling=false;
let manageData={installed:[],archived:[]}, activeDraft=null, activeJob=null, manageFilter='All', lastManage='';
const manageNav=document.createElement('button');manageNav.dataset.view='manage';manageNav.innerHTML='<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 7h16M7 4v6M4 17h16M16 14v6"/></svg>Manage skills';$('#mainnav').append(manageNav);
const originalRender=render;
render=function(){if(view==='manage'){renderManage();renderProviderControls();}else originalRender();};
function renderManage(){
 document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
 document.querySelectorAll('[data-category]').forEach(b=>b.classList.remove('active'));
 const rows=manageData.installed.filter(s=>matchesHarness(s)&&(manageFilter==='All'||s.kind===manageFilter)&&query.toLowerCase().trim().split(/\s+/).every(t=>[s.name,s.description,s.kind,s.source].join(' ').toLowerCase().includes(t)));
 $('#content').innerHTML=`<div class="page manage-page"><div class="manage-heading"><div><span class="eyebrow">YOUR SKILL LIBRARY</span><h1>Manage skills</h1><p class="lead">Create a skill or bring one in. Available across projects in your selected local library.</p></div><div class="manage-actions"><button class="button" id="nearby-receive">Receive from device</button><button class="button" id="export-package">Export package</button><button class="button" id="import-package">Import package</button><button class="button" id="import-skill">Import skill</button><button class="button primary" id="create-skill">Create skill</button></div></div><div id="provider-controls"></div><div class="manage-filters">${['All','User Created','Repo Installed','Markdown Imported','Harness Copy','Package Imported','Existing'].map(k=>`<button class="button ${manageFilter===k?'primary':''}" data-origin="${k}">${k}</button>`).join('')}</div><p class="manage-note">${manageData.installed.length} installed · Removal archives the skill, so you can restore it later.</p><div class="manage-list">${rows.map(s=>`<article class="manage-row"><div><h2>${esc(s.name)}</h2><span class="tag">${esc(s.kind)}</span>${harnessBadges(s)}${s.linked?'<span class="tag">Linked folder</span>':''}<p>${esc(s.description)}</p><details><summary>Source</summary><p class="source-path">${esc(s.source)}</p></details>${s.error?`<p class="form-error">${esc(s.error)}</p>`:''}</div>${s.readOnly?'<span class="manage-note">Managed by its source CLI</span>':`<button class="button remove-button" data-remove="${esc(s.id)}">Remove</button>`}</article>`).join('')||'<p class="empty">No skills in this section yet.</p>'}</div><details class="archive-list"><summary>Removed skills (${manageData.archived.length})</summary>${manageData.archived.map(s=>`<div class="archive-row"><span>${esc(s.id)}<small>${esc(new Date(s.archived_at).toLocaleDateString())}</small></span><button class="button" data-restore="${esc(s.token)}">Restore</button></div>`).join('')}</details><p class="manage-note">Existing means installed outside Skill-Desk. New imports and creations have their source recorded automatically.</p></div>`;
}
const modal=document.createElement('dialog');modal.className='skill-dialog';modal.innerHTML='<div id="dialog-body"></div>';document.body.append(modal);
function showDialog(body){$('#dialog-body').innerHTML=body;if(!modal.open)modal.showModal();}
function errorMessage(message){const el=$('#form-message');if(el){el.textContent=message;el.className='form-error';}else toast(message);}
function dialogHeader(title){return `<div class="dialog-heading"><h2>${title}</h2><button class="button" type="button" id="close-dialog" aria-label="Close dialog">Close</button></div>`;}
async function api(path,body){const options=body===undefined?{signal:AbortSignal.timeout(15000)}:{method:'POST',headers:{'Content-Type':'application/json','X-Skill-Desk-Token':window.skillDeskToken},body:JSON.stringify(body)};const response=await fetch(path,options);const data=await response.json().catch(()=>({error:'Request failed'}));if(!response.ok){const error=Error(data.error||'Request failed');error.status=response.status;throw error;}return data;}
async function loadManage(){try{const next=await api('/api/manage');const signature=JSON.stringify(next);manageData=next;if(view==='manage'&&!modal.open&&signature!==lastManage)renderManage();lastManage=signature;renderProviderControls();}catch(e){if(view==='manage')toast(e.message);}}
function createForm(){showDialog(dialogHeader('Create a skill')+`<form id="create-form"><label for="skill-brief">What should this skill help you do?</label><textarea id="skill-brief" required maxlength="30000" rows="9" placeholder="Describe the purpose, when to use it, the steps or rules that matter, and the result you want. Include an example request if useful."></textarea><label class="checkbox-label"><input type="checkbox" id="explicit-skill"> Only use when I explicitly request it</label><p class="manage-note">Uses your selected authoring CLI with the installed skill-authoring guidance. You can review the generated instructions before installing.</p><p id="form-message" role="status"></p><button class="button primary" type="submit">Generate preview</button></form>`);}
function importForm(){showDialog(dialogHeader('Import a skill')+`<form id="import-form"><label for="import-mode">Import from</label><select id="import-mode"><option value="markdown">Markdown text or file</option><option value="github">GitHub repository</option></select><div id="markdown-fields"><label for="md-file">Markdown file</label><input type="file" id="md-file" accept=".md,.markdown,text/markdown,text/plain"><label for="md-content">Or paste Markdown</label><textarea id="md-content" rows="7" maxlength="200000" placeholder="Paste SKILL.md, including its YAML name and description."></textarea><details><summary>Ordinary Markdown without skill metadata?</summary><label for="md-name">Skill name</label><input id="md-name" placeholder="my-skill" maxlength="63"><label for="md-description">When should the agent use this skill?</label><input id="md-description" maxlength="1024"></details></div><div id="github-fields" hidden><label for="repo-url">GitHub URL</label><input type="url" id="repo-url" placeholder="https://github.com/owner/repository"><label for="repo-ref">Branch or tag <small>optional</small></label><input id="repo-ref" placeholder="Repository default"><label for="repo-path">Skill folder <small>optional</small></label><input id="repo-path" placeholder="skills/my-skill"><p class="manage-note">Repository imports preserve the complete skill folder, including references, scripts, licenses, and invocation settings. For branch names containing slashes, use the repository URL and enter the full branch here.</p></div><p id="form-message" role="status"></p><button class="button primary" type="submit">Preview import</button></form>`);}
function previewDraft(result){if(result.package){previewPackage(result);return;}activeDraft=result;showDialog(dialogHeader('Review skill')+(result.targetHarness?`<p>Install a separate copy in ${harnessLabel(result.targetHarness)}. All included files are preserved. Review any harness-specific tools or instructions before using the copy.</p>`:'')+`<p><span class="tag">${esc(result.kind)}</span></p>${result.candidates.length>1?`<label for="candidate">Choose a skill to install</label><select id="candidate">${result.candidates.map(s=>`<option value="${esc(s.candidate)}">${esc(s.name)}</option>`).join('')}</select>`:''}<div id="candidate-preview"></div><p id="form-message" role="status"></p><div class="manage-actions"><button class="button" id="discard-draft">Discard preview</button><button class="button primary" id="install-draft">${result.targetHarness?'Install in '+harnessLabel(result.targetHarness):'Install globally'}</button></div>`);renderCandidate();}
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
modal.addEventListener('submit',async e=>{if(!['create-form','import-form'].includes(e.target.id))return;e.preventDefault();const button=e.target.querySelector('button[type="submit"]');button.disabled=true;
 try{if(e.target.id==='create-form')await startJob('create',{brief:$('#skill-brief').value,explicit:$('#explicit-skill').checked});
 else await startJob('import',{mode:$('#import-mode').value,content:$('#md-content').value,name:$('#md-name').value,description:$('#md-description').value,filename:$('#md-file').files[0]?.name,url:$('#repo-url').value,ref:$('#repo-ref').value,path:$('#repo-path').value});}
 finally{button.disabled=false;}});
modal.addEventListener('change',async e=>{if(e.target.id==='import-mode'){const github=e.target.value==='github';$('#markdown-fields').hidden=github;$('#github-fields').hidden=!github;}if(e.target.id==='candidate')renderCandidate();if(e.target.id==='md-file'){const file=e.target.files[0];if(file){if(file.size>200000){errorMessage('Choose a Markdown file of up to 200 KB.');e.target.value='';return;}$('#md-content').value=await file.text();}}});
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;
 try{
 if(b.id==='create-skill'||b.id==='import-skill'){if(packageInstalling){toast('Wait for the package installation to finish.');return;}if(activeJob){showJobProgress();return;}if(activeDraft){previewDraft(activeDraft);return;}b.id==='create-skill'?createForm():importForm();}
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
harnessSelect.id='skill-harness';harnessSelect.setAttribute('aria-label','Skill provider');
harnessSelect.innerHTML='<option value="all">All providers</option><option value="codex">Codex</option><option value="claude">Claude</option>';
harnessSelect.value=harnessFilter;$('#print').before(harnessSelect);
const matchesHarness=s=>harnessFilter==='all'||(s.harnesses||[]).includes(harnessFilter);
const originalFiltered=filtered;
filtered=function(){return originalFiltered().filter(matchesHarness);};
const originalDetail=detail;
function harnessBadges(s){return (s.harnesses||[]).map(h=>`<span class="tag" data-harness="${h}">${harnessLabel(h)}</span>`).join('');}
function harnessActions(s){
 const missing=['codex','claude'].filter(h=>!(s.installedHarnesses||s.harnesses||[]).includes(h));
 return `<div class="harness-actions">${harnessBadges(s)}${missing.map(h=>`<button class="button" data-copy-harness="${h}" data-copy-skill="${esc(s.id)}">Install in ${harnessLabel(h)}</button>`).join('')}</div>`;
}
detail=function(s){const display={...s,invocationText:(s.invocationText||'').replaceAll('$'+skillName(s),skillInvocation(s)).replaceAll('/'+skillName(s),skillInvocation(s)).replaceAll(promptProvider(s)==='claude'?'Codex':'Claude',harnessLabel(promptProvider(s)))};return originalDetail(display).replace(`<h1>${esc(s.id)}</h1>`,`<h1>${esc(s.name||s.title)}</h1>`).replace('<div class="columns">',harnessActions(s)+'<div class="columns">').replace('Try this in Codex','Try this in '+harnessLabel(promptProvider(s)));};
const renderWithManagement=render;
render=function(){
 renderWithManagement();
 $('#printguide').innerHTML='<h1>Skills · '+(harnessFilter==='all'?'All':harnessLabel(harnessFilter))+'</h1>'+skills.filter(matchesHarness).map(s=>`<article><h2>${esc(s.name||s.title)}</h2><p>${esc(s.summary)}</p><pre>${esc(skillPrompt(s))}</pre></article>`).join('');
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

// The desktop service uses a new port after restarting; save appearance with the library.
let themeSave=Promise.resolve();
window.skillDeskSaveTheme=value=>{themeSave=themeSave.then(()=>api('/api/preferences',{theme:value})).catch(()=>toast('Could not save the theme. Please retry.'));};


// Portable packages contain only explicitly selected skill folders.
function exportPackageForm(){
 const rows=skills.filter(matchesHarness);
 showDialog(dialogHeader('Export skills package')+`<p>Select skills to move to another device. Full folders are included. Review private text and supporting files before sharing; credentials and app state are not part of the package metadata.</p><div class="manage-actions"><button class="button" id="package-select-all">Select all shown</button><button class="button" id="package-select-none">Clear selection</button></div><div class="package-list">${rows.map(s=>`<label class="checkbox-label"><input type="checkbox" name="package-skill" value="${esc(s.id)}"> ${esc(s.name||s.id)} ${harnessBadges(s)}</label>`).join('')||'<p>No skills for this provider.</p>'}</div><p id="form-message" role="status"></p><button class="button primary" id="prepare-export">Review package</button>`);
}
function importPackageForm(){
 showDialog(dialogHeader('Import skills package')+`<p>Choose a package exported by Skill-Desk. Review the instructions before installing. Existing skills are never overwritten.</p><label for="package-file">Package file · up to 100 MB</label><input id="package-file" type="file" accept=".zip,application/zip"><label for="package-target">Install into</label><select id="package-target"><option value="shared">Default skill library</option><option value="codex">Codex</option><option value="claude">Claude</option></select><p id="form-message" role="status"></p><button class="button primary" id="prepare-package">Preview package</button>`);
}
function isPackageDuplicate(skill){return /already exists|already installed|Installed from this package/.test(skill.conflict||'');}
function previewPackage(result){
 activeDraft=result;
 showDialog(dialogHeader('Review package')+`<p>Destination: ${esc(result.destination||'Default library')}</p><p>Select the skills to install. Skills with a conflict cannot be selected. Each blocked skill shows the reason below. Included scripts are copied, never executed by the import.</p>${result.candidates.some(isPackageDuplicate)?`<div class="package-conflicts"><label class="checkbox-label"><input type="checkbox" id="hide-package-duplicates"> Hide duplicates (${result.candidates.filter(isPackageDuplicate).length})</label><p id="package-conflict-summary" role="status"></p><p>Skill-Desk keeps the existing copy and does not overwrite it. To replace it, discard this preview, remove the existing skill in Manage (it is archived), then import the package again. For a separately managed skill, remove it through its source CLI first.</p></div>`:''}<div class="package-list" id="package-candidates">${result.candidates.map(s=>`<article class="manage-row" data-conflict="${isPackageDuplicate(s)}"><div><label class="checkbox-label"><input type="checkbox" name="package-candidate" value="${esc(s.candidate)}" ${s.conflict?'disabled':'checked'}> ${esc(s.name)}</label><p>${esc(s.description)}</p>${harnessBadges(s)}${s.conflict?`<p class="form-error">${esc(s.conflict)}</p>`:''}<details><summary>Review instructions and ${s.files.length} files</summary><ul>${s.files.map(f=>`<li>${esc(f)}</li>`).join('')}</ul><pre class="skill-preview">${esc(s.content)}</pre></details></div></article>`).join('')}</div><p id="form-message" role="status"></p><div class="manage-actions"><button class="button" id="discard-draft">Discard preview</button><button class="button primary" id="install-package">Install selected skills (0)</button></div>`);
 updatePackageSelection();
}
function updatePackageSelection(){
 const button=$('#install-package');if(!button)return;
 const count=document.querySelectorAll('[name=package-candidate]:checked:not(:disabled)').length;
 button.textContent=`Install selected skills (${count})`;button.disabled=packageInstalling||count===0;
 const hidden=$('#hide-package-duplicates')?.checked||false;
 const duplicates=document.querySelectorAll('#package-candidates [data-conflict="true"]');
 duplicates.forEach(row=>row.hidden=hidden);
 if($('#package-conflict-summary'))$('#package-conflict-summary').textContent=`${duplicates.length} duplicate skill${duplicates.length===1?"":"s"} ${hidden?"hidden":"shown"} and excluded from installation because a skill with that name is already installed. ${hidden?"Uncheck Hide duplicates to inspect each conflict.":"Each duplicate below shows where the conflict was found."}`;
}
modal.addEventListener('change',e=>{if(e.target.name==='package-candidate'||e.target.id==='hide-package-duplicates')updatePackageSelection();});
document.addEventListener('click',async e=>{
 const b=e.target.closest('button');if(!b||!['export-package','import-package','package-select-all','package-select-none','prepare-export','prepare-package','install-package'].includes(b.id))return;
 try{
  if(b.id==='export-package'){if(packageInstalling){toast('Wait for the package installation to finish.');return;}exportPackageForm();return;}
  if(b.id==='import-package'){if(packageInstalling){toast('Wait for the package installation to finish.');return;}if(activeJob){showJobProgress();return;}if(activeDraft){previewDraft(activeDraft);return;}importPackageForm();return;}
  if(b.id==='package-select-all'||b.id==='package-select-none')document.querySelectorAll('[name=package-skill]').forEach(x=>x.checked=b.id==='package-select-all');
  if(b.id==='prepare-export'){
   const ids=Array.from(document.querySelectorAll('[name=package-skill]:checked'),x=>x.value);
   if(!ids.length)throw Error('Select at least one skill.');
   b.disabled=true;$('#form-message').textContent='Preparing package…';
   const result=await api('/api/package-export',{ids});
   showDialog(dialogHeader('Review export')+`<p>${result.manifest.skills.length} skills · ${(result.bytes/1000000).toFixed(2)} MB. The download contains the actual files listed below. Check them for private information before sharing.</p><div class="package-list">${result.manifest.skills.map(s=>`<details><summary>${esc(s.name)} · ${Object.keys(s.files).length} files</summary><ul>${Object.keys(s.files).map(f=>`<li>${esc(f)}</li>`).join('')}</ul></details>`).join('')}</div><p id="form-message" role="status"></p><div class="manage-actions"><button class="button" id="download-package">Download package</button><button class="button primary" id="nearby-send-export">Send to device</button></div>`);
   $('#nearby-send-export').onclick=()=>openNearby('send',result.export);
   $('#download-package').textContent='Save package to Downloads';
   $('#download-package').onclick=async()=>{const button=$('#download-package');button.disabled=true;try{const saved=await api('/api/package-save',{export:result.export});$('#form-message').textContent='Saved to '+saved.path+'. Transfer this file to your other device and choose Import package.';}catch(err){errorMessage(err.message);button.disabled=false;}};
  }
  if(b.id==='prepare-package'){
   const file=$('#package-file').files[0];if(!file||file.size>100000000)throw Error('Choose a package of up to 100 MB.');
   const target=$('#package-target').value;b.disabled=true;$('#form-message').textContent='Reading and validating package…';
   const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('Could not read package.'));reader.readAsDataURL(file);});
   previewPackage(await api('/api/package-preview',{data,target}));
  }
  if(b.id==='install-package'){
   const selected=Array.from(document.querySelectorAll('[name=package-candidate]:checked'),x=>x.value);
   if(!selected.length)throw Error('Select at least one skill without a conflict.');
   b.disabled=true;packageInstalling=true;const result=activeDraft;let installed=0;const failures=[];
   for(const candidate of selected){$('#form-message').textContent=`Installing ${installed+failures.length+1} of ${selected.length}…`;try{await api('/api/install',{draft:result.draft,candidate});installed++;const s=result.candidates.find(x=>x.candidate===candidate);s.conflict='Installed from this package.';}catch(err){failures.push(err.message);}}
   await loadManage();await syncCatalog();
   if(failures.length){previewPackage(result);$('#form-message').textContent=`Installed ${installed}. ${failures.join(' ')}`;}
   else{await api('/api/discard',{draft:result.draft});activeDraft=null;modal.close();render();toast(`Installed ${installed} skills from package`);}
  }
 }catch(err){errorMessage(err.message);}finally{if(b.id==='install-package'){packageInstalling=false;updatePackageSelection();}else if(b.isConnected)b.disabled=false;}
});


let nearbyView=null, nearbyTimer=null, nearbyStop=Promise.resolve();
async function openNearby(mode,exportId=null){
 if(activeDraft||activeJob||packageInstalling){toast('Finish the current skill job or preview first.');return;}
 if(nearbyView)return;
 const viewState={mode,exportId};nearbyView=viewState;
 try{
  await nearbyStop;
  const state=await api('/api/nearby-start',{mode});
  if(nearbyView!==viewState){await api('/api/nearby-stop',{});return;}
  showDialog(dialogHeader(mode==='receive'?'Receive from another device':'Send to another device')+`<p>Keep Skill-Desk open on both devices on the same local network. Closing this window stops sharing.</p><div id="nearby-identity"></div><p class="manage-note" id="nearby-warning"></p>${mode==='send'?`<label for="nearby-peer">Receiving device</label><select id="nearby-peer"><option value="">Looking for devices…</option></select><p class="manage-note">Open Receive on the other device. If it does not appear, use its displayed address.</p><details><summary>Connect using an address</summary><label for="nearby-address">Receiver address and port</label><input id="nearby-address" placeholder="192.168.1.20:53317"><button class="button" id="nearby-probe">Find device</button></details><p>Receiver security code: <code id="nearby-peer-code">Choose a device</code></p><label class="checkbox-label"><input type="checkbox" id="nearby-confirm"> I checked that this code matches the receiving device.</label><label for="nearby-pin">Six-digit PIN shown on the receiver</label><input id="nearby-pin" inputmode="numeric" autocomplete="off" maxlength="6" placeholder="000000"><button class="button primary" id="nearby-send">Request transfer</button>`:''}<div id="nearby-offer"></div><div id="nearby-progress"><progress max="100" value="0" aria-label="Transfer progress"></progress><span></span></div><p id="nearby-message" role="status"></p><div id="nearby-review" hidden><label for="nearby-target">Install into</label><select id="nearby-target"><option value="shared">Default skill library</option><option value="codex">Codex</option><option value="claude">Claude</option></select><button class="button primary" id="nearby-preview">Review received package</button></div><p id="form-message" role="alert"></p><p class="manage-note">Sharing stops after 10 minutes, or after 60 seconds without this window checking in. Only selected packages are shared; your installed library stays private.</p><button class="button" id="nearby-stop">Stop sharing</button>`);
  paintNearby(state);
  async function poll(){
   if(nearbyView!==viewState)return;
   try{const next=await api('/api/nearby-status',{});if(nearbyView!==viewState)return;paintNearby(next);if(!next.active)return;}
   catch(error){if(nearbyView!==viewState)return;errorMessage('Connection lost. Sharing will expire automatically. '+error.message);}
   if(nearbyView===viewState)nearbyTimer=setTimeout(poll,1000);
  }
  nearbyTimer=setTimeout(poll,1000);
 }catch(error){nearbyView=null;errorMessage(error.message);}
}
function paintNearby(state){
 if(!nearbyView)return;
 if(['sent','received'].includes(state.phase)&&state.active){
  nearbyView.state=state;
  if(!nearbyView.completed){nearbyView.completed=true;showDialog(dialogHeader('Transfer successful')+`<div class="nearby-success"><h3>${state.phase==='sent'?'Package sent successfully':'Package received successfully'}</h3><p>${state.phase==='sent'?'The receiving device can now review and install the skills.':'Your package is ready. Review and select the skills before installing them.'}</p></div>${state.phase==='received'?`<label for="nearby-target">Install into</label><select id="nearby-target"><option value="shared">Default skill library</option><option value="codex">Codex</option><option value="claude">Claude</option></select><button class="button primary" id="nearby-preview">Review received package</button><p class="manage-note">Closing without reviewing discards the received package.</p>`:''}<p id="form-message" role="alert"></p><button class="button" id="nearby-stop">Close and stop sharing</button>`);}
  return;
 }
 if(!$('#nearby-message')){if(!state.active&&$('#nearby-preview')){$('#nearby-preview').disabled=true;errorMessage('Sharing expired. Receive the package again to review it.');}return;}
 nearbyView.state=state;
 if(!state.active){$('#nearby-message').textContent='Sharing has stopped. Close this window and reopen Send or Receive to try again.';document.querySelectorAll('#nearby-send,#nearby-probe,#nearby-preview,#nearby-accept,#nearby-reject').forEach(b=>b.disabled=true);return;}
 $('#nearby-identity').innerHTML=`<p>Your device: <strong>${esc(state.alias)}</strong></p>${state.mode==='receive'?`<div class="nearby-codes"><div><small>Receiver PIN</small><strong>${esc(state.pin)}</strong></div><div><small>Security code · compare on sender</small><code>${esc(state.code)}</code></div></div><p class="manage-note">Address: ${state.addresses.map(esc).join(' or ')||'No local IPv4 address found. Connect to your local network.'}</p>`:''}`;
 $('#nearby-warning').textContent=state.warning||'';
 $('#nearby-message').textContent=state.message||'Ready. Waiting for another device.';
 const progressing=['sending','transferring','receiving','waiting'].includes(state.phase);
 $('#nearby-progress').hidden=!progressing;
 $('#nearby-progress progress').value=state.progress;
 $('#nearby-progress span').textContent=state.phase==='waiting'?'Waiting for acceptance…':state.progress+'%';
 $('#nearby-review').hidden=state.phase!=='received';
 const offer=state.phase==='offered'?state.incoming:null;
 const offerKey=offer?.id||'';
 if($('#nearby-offer').dataset.offer!==offerKey){$('#nearby-offer').dataset.offer=offerKey;$('#nearby-offer').innerHTML=offer?`<div class="nearby-offer"><h3>Incoming skill package</h3><p>${esc(offer.alias)} · ${esc(offer.ip)} · ${(offer.size/1000000).toFixed(2)} MB</p><p>Accept only the transfer you requested. Acceptance receives a package; it does not install skills.</p><div class="manage-actions"><button class="button" id="nearby-reject">Reject</button><button class="button primary" id="nearby-accept">Accept package</button></div></div>`:'';}
 if(state.mode==='send'){
  const select=$('#nearby-peer'), previous=select.value;
  const options='<option value="">Choose a receiving device</option>'+state.peers.map(p=>`<option value="${esc(p.id)}">${esc(p.alias)} · ${esc(p.ip)}</option>`).join('');
  if(select.innerHTML!==options){select.innerHTML=options;select.value=previous;if(select.value!==previous){$('#nearby-confirm').checked=false;$('#nearby-pin').value='';}}
  const peer=state.peers.find(p=>p.id===select.value);$('#nearby-peer-code').textContent=peer?.code||'Choose a device';
  const busy=['waiting','sending'].includes(state.phase);
  $('#nearby-send').disabled=busy||state.phase==='sent';select.disabled=busy;$('#nearby-probe').disabled=busy;
 }
}
modal.addEventListener('close',()=>{
 if(!nearbyView)return;
 nearbyView=null;clearTimeout(nearbyTimer);
 nearbyStop=api('/api/nearby-stop',{}).catch(()=>toast('Sharing connection lost; the session will expire automatically.'));
});
modal.addEventListener('change',e=>{if(e.target.id==='nearby-peer'){$('#nearby-confirm').checked=false;$('#nearby-pin').value='';const peer=nearbyView?.state?.peers.find(p=>p.id===e.target.value);$('#nearby-peer-code').textContent=peer?.code||'Choose a device';}});
document.addEventListener('click',async e=>{
 const b=e.target.closest('button');if(!b||!['nearby-receive','nearby-stop','nearby-probe','nearby-send','nearby-accept','nearby-reject','nearby-preview'].includes(b.id))return;
 b.disabled=true;
 try{
  if(b.id==='nearby-receive'){await openNearby('receive');return;}
  if(b.id==='nearby-stop'){modal.close();return;}
  if(!nearbyView)return;
  const current=nearbyView;let state;
  if(b.id==='nearby-probe'){
   b.textContent='Finding device…';
   state=await api('/api/nearby-probe',{address:$('#nearby-address').value});
   if(nearbyView!==current)return;
   paintNearby(state);
   if(state.selectedPeer){$('#nearby-peer').value=state.selectedPeer;$('#nearby-peer').dispatchEvent(new Event('change',{bubbles:true}));$('#nearby-address').closest('details').open=false;$('#nearby-confirm').focus();}
  }
  if(b.id==='nearby-send')state=await api('/api/nearby-send',{export:current.exportId,peer:$('#nearby-peer').value,pin:$('#nearby-pin').value,confirmed:$('#nearby-confirm').checked});
  if(b.id==='nearby-accept'||b.id==='nearby-reject')state=await api('/api/nearby-decide',{id:current.state?.incoming?.id,accept:b.id==='nearby-accept'});
  if(b.id==='nearby-preview'){
   const result=await api('/api/nearby-preview',{target:$('#nearby-target').value});
   if(nearbyView!==current)return;
   nearbyView=null;clearTimeout(nearbyTimer);previewPackage(result);return;
  }
  if(nearbyView===current&&state)paintNearby(state);
 }catch(error){errorMessage(error.message);}finally{if(b.id==='nearby-probe'&&b.isConnected)b.textContent='Find device';if(b.isConnected&&!['nearby-send','nearby-preview'].includes(b.id))b.disabled=false;else if(b.isConnected&&b.id==='nearby-preview')b.disabled=false;}
});
