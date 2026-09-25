const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const [url,fixture,out]=process.argv.slice(2);
(async()=>{
 const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 const checks=[];
 async function checked(name,fn){await fn();checks.push({name,status:'pass'});}
 async function contrast(){const ratios=await page.locator('.history-coverage p,.usage-explanation,.manage-note').evaluateAll(nodes=>nodes.filter(e=>e.getClientRects().length).map(e=>{const rgb=color=>color.match(/[\d.]+/g).slice(0,3).map(Number);const lum=color=>rgb(color).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);let background=e;while(background.parentElement&&getComputedStyle(background).backgroundColor==='rgba(0, 0, 0, 0)')background=background.parentElement;const a=lum(getComputedStyle(e).color),b=lum(getComputedStyle(background).backgroundColor);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);}));assert.ok(ratios.length>0);assert.ok(ratios.every(r=>r>=4.5),'Body text contrast must reach 4.5:1: '+ratios);}
 async function close(){if(await page.locator('dialog.skill-dialog').isVisible())await page.locator('#close-dialog').click();}
 async function addMenu(id){await page.locator('#add-skills-menu summary').click();await page.locator(id).click();}
 async function api(path,body){return page.evaluate(async({path,body})=>{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Skill-Desk-Token':window.skillDeskToken},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(data.error);return data;},{path,body});}
 try{
 await page.goto(url);await page.locator('[data-view="manage"]').click();
 await checked('Page identity, meaningful content and test banner',async()=>{assert.match(await page.title(),/Skill/);assert.equal(new URL(page.url()).origin,url);await page.locator('.library-heading').waitFor();assert.match(await page.locator('.instance-banner').innerText(),/TEST INSTANCE/);assert.equal(await page.locator('nextjs-portal,vite-error-overlay').count(),0);});
 await checked('Saved job outcomes display without missing-result errors or automatic replay',async()=>{
  const requests=[];const collect=request=>requests.push({url:request.url(),method:request.method()});page.on('request',collect);
  for(const [name,status,message] of [['complete','complete','result is no longer available'],['failed','failed','cause is unknown'],['cancelled','cancelled','was cancelled'],['running','failed','interrupted'],['validation','failed','outside the reviewed sample']]){
   await page.evaluate(id=>sessionStorage.setItem('skill-desk-job',id),'fixture-'+name);await page.reload();
   await page.locator('#dialog-title').filter({hasText:name==='complete'?'Job completed':name==='cancelled'?'Job cancelled':'Could not review usage'}).waitFor();
   assert.ok((await page.locator('#dialog-body').innerText()).includes(message));
   const record=await (await page.request.get(url+'/api/jobs/fixture-'+name)).json();assert.equal(record.status,status);assert.equal(record.resultAvailable,false);
   await close();await page.locator('#view-skill-job').click();assert.ok((await page.locator('#dialog-body').innerText()).includes(message));
   if(name==='complete'){
    assert.equal(await page.locator('#view-skill-job').innerText(),'View status');await page.screenshot({path:out+'/saved-completed-job.png'});
    await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await page.screenshot({path:out+'/saved-completed-job-mobile.png'});await page.setViewportSize({width:1440,height:1000});
   }
   await close();await page.locator('#dismiss-skill-job').click();assert.equal(await page.locator('#skill-job-banner').isVisible(),false);
  }
  page.off('request',collect);
  assert.equal(requests.filter(r=>r.method==='POST'&&/\/api\/(recommend|create|import)$/.test(r.url)).length,0);
  for(const name of ['complete','failed','cancelled','running','validation'])assert.equal(requests.filter(r=>r.url.endsWith('/api/jobs/fixture-'+name)).length,1,'A saved terminal status must stop polling');
  await page.locator('[data-view="manage"]').click();
 });
 await checked('History coverage and reviewed evidence',async()=>{
  await page.locator('[data-manage-tab="for-you"]').first().click();await page.locator('#preview-usage').click();await page.locator('.history-coverage').waitFor();
  assert.equal(await page.locator('[data-usage-text]').count(),2);assert.match(await page.locator('.history-coverage').innerText(),/2 session files found/);
  await page.locator('[data-usage-text]').first().fill('Edited browser debugging request');
  await page.locator('#run-recommendations').click();await page.locator('.recommendation-row').waitFor();
  await page.locator('.recommendation-evidence summary').click();assert.match(await page.locator('.recommendation-row blockquote').innerText(),/Edited browser debugging request/);
  await page.screenshot({animations:'disabled',path:out+'/recommendations-dark.png'});
 });
 await checked('Recommendation review, saving and installation have distinct outcomes',async()=>{
  const installed=fixture+'/.codex/skills/diagnosing-bugs/SKILL.md';
  await page.locator('.recommendation-evidence summary').click();
  const review=page.getByRole('button',{name:'Review & install Diagnosing bugs',exact:true});
  assert.equal(await review.count(),1);assert.equal(await page.locator('[data-save-recommendation]').isVisible(),false);
  await page.screenshot({path:out+'/recommendations-simplified.png'});
  await page.setViewportSize({width:390,height:844});await page.locator('.recommendation-options summary').click();
  assert.match(await page.locator('.recommendation-options').innerText(),/without installing/);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  await page.screenshot({path:out+'/recommendations-options-mobile.png'});await page.locator('.recommendation-options summary').click();
  await review.click();await page.locator('#install-package').waitFor();
  assert.equal(await page.locator('#preview-recommended-skill').count(),0);
  assert.equal(await page.locator('#install-package').innerText(),'Install for Codex');
  assert.equal(await page.locator('[name=package-candidate]:visible').count(),0);
  assert.match(await page.locator('.recommendation-instructions').innerText(),/name: diagnosing-bugs/);
  assert.equal(fs.existsSync(installed),false,'Review must not install');
  await page.screenshot({path:out+'/recommendation-review-mobile.png'});
  await close();await review.click();await page.locator('#install-package').waitFor();
  assert.equal(fs.existsSync(installed),false,'Closing and reopening a review must not install');
  await page.locator('#discard-draft').click();assert.equal(fs.existsSync(installed),false);
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('.recommendation-options summary').click();await page.locator('[data-save-recommendation]').click();
  await page.waitForFunction(()=>document.querySelectorAll('.recommendation-row').length===0);
  assert.equal(fs.existsSync(installed),false,'Saving must not install');
  await page.locator('#saved-recommendations').click();await page.locator('[data-review-saved]').click();await page.locator('#install-package').waitFor();
  assert.equal(await page.locator('#install-package').innerText(),'Install for Codex');await page.locator('#discard-draft').click();
  await page.locator('#saved-recommendations').click();await page.locator('[data-reset-choice]').click();await page.waitForFunction(()=>document.querySelectorAll('[data-reset-choice]').length===0);await close();
  await page.locator('#new-recommendations').click();await page.locator('#preview-usage').click();await page.locator('#run-recommendations').click();await review.waitFor();
  await page.locator('[data-theme-toggle]').click();await page.screenshot({path:out+'/recommendations-simplified-light.png'});await page.locator('[data-theme-toggle]').click();
  await review.click();await page.locator('#install-package').waitFor();await page.locator('.recommendation-destination summary').click();
  assert.ok((await page.locator('.recommendation-destination').innerText()).includes('/.codex/skills'));
  await page.screenshot({path:out+'/recommendation-review.png'});await page.locator('#install-package').click();
  await page.locator('[data-first-step]').waitFor();assert.equal(await page.locator('#dialog-title').innerText(),'Skill installed');
  assert.match(fs.readFileSync(installed,'utf8'),/name: diagnosing-bugs/);assert.deepEqual(fs.readdirSync(fixture+'/.codex/skills'),['diagnosing-bugs']);
  await close();await page.locator('.recommendation-installed').waitFor();assert.equal(await review.count(),0);
  await page.screenshot({path:out+'/recommendation-installed-status.png'});
 });
 await checked('Capability matrix and private diagnostic report',async()=>{
  await page.locator('#library-settings').click();await page.locator('.agent-capabilities summary').click();assert.equal(await page.locator('.agent-capabilities tbody tr').count(),4);
  await page.screenshot({animations:'disabled',path:out+'/capabilities-dark.png'});
  await page.locator('#local-diagnostics').click();const text=await page.locator('.skill-preview').innerText();assert.equal(text.includes(fixture),false);assert.equal(text.includes('Edited browser'),false);assert.equal(text.includes('browser-example'),false);await close();
 });
 await checked('Create draft survives dialog close and cancellation',async()=>{
  await addMenu('#create-skill');await page.locator('#skill-brief').fill('FIXTURE_SLOW Verify cancellation');await page.locator('#close-dialog').click();
  await addMenu('#create-skill');assert.equal(await page.locator('#skill-brief').inputValue(),'FIXTURE_SLOW Verify cancellation');
  await page.locator('#create-form button[type=submit]').click();await page.locator('#cancel-job').waitFor();await page.locator('#close-dialog').click();await page.locator('#view-skill-job').click();await page.locator('#cancel-job').click();
  await page.locator('#edit-job-input').waitFor();assert.match(await page.locator('#dialog-title').innerText(),/cancelled/);
  await page.locator('#edit-job-input').click();assert.equal(await page.locator('#skill-brief').inputValue(),'FIXTURE_SLOW Verify cancellation');
  await page.locator('#skill-brief').fill('FIXTURE_FAIL Verify error handling');await page.locator('#create-form button[type=submit]').click();await page.locator('#edit-job-input').waitFor();assert.match(await page.locator('#form-message').innerText(),/model is unavailable/);await page.locator('#retry-job').click();await page.locator('#edit-job-input').waitFor();assert.match(await page.locator('#form-message').innerText(),/model is unavailable/);
  await page.locator('#edit-job-input').click();await page.locator('#skill-brief').fill('Verify browser workflow');await page.locator('#create-form button[type=submit]').click();
  await page.locator('#install-draft').waitFor();assert.match(await page.locator('#dialog-body').innerText(),/Destination:/);await page.locator('#install-draft').click();await page.locator('[data-first-step]').waitFor();await close();
 });
 await checked('Replacement comparison archives previous content',async()=>{
  await addMenu('#import-skill');await page.locator('#md-content').fill('---\nname: browser-example\ndescription: Verify the new version.\n---\nUpdated browser instructions.');
  await page.locator('#import-form button[type=submit]').click();await page.locator('#compare-replacement').click();
  assert.match(await page.locator('.skill-preview').innerText(),/Updated browser instructions/);assert.equal(await page.locator('#replace-skill').isDisabled(),true);
  await page.screenshot({animations:'disabled',path:out+'/replacement-review.png'});
  await page.locator('#confirm-replacement').check();await page.locator('#replace-skill').click();await page.locator('dialog.skill-dialog').waitFor({state:'hidden'});
  assert.match(fs.readFileSync(fixture+'/skills/browser-example/SKILL.md','utf8'),/Updated browser instructions/);
 });
 await checked('Project history scope, refresh and unsupported agent',async()=>{
  await page.locator('#onboard-project').click();await page.locator('#project-path').fill(fixture+'/repo');await page.locator('#project-name').fill('QA project');await page.locator('#project-form button').click();await page.locator('dialog.skill-dialog').waitFor({state:'hidden'});
  await page.locator('[data-manage-tab="for-you"]').first().click();await page.locator('#preview-usage').click();await page.locator('.history-coverage').waitFor();assert.equal(await page.locator('[data-usage-text]').count(),1);
  await page.locator('#usage-scope').selectOption('all');assert.equal(await page.locator('[data-usage-text]').count(),0);await page.locator('#preview-usage').click();await page.locator('.history-coverage').waitFor();assert.equal(await page.locator('[data-usage-text]').count(),2);
  await contrast();await page.screenshot({animations:'disabled',path:out+'/history-dark.png'});
  await page.locator('#project-agent').selectOption('cursor');assert.match(await page.locator('.library-body').innerText(),/currently support Codex and Claude/);
 });
 await checked('Keyboard focus and draft input labels',async()=>{
  await page.locator('#library-settings').click();assert.equal(await page.locator('#dialog-title').evaluate(e=>document.activeElement===e),true);
  await page.keyboard.press('Tab');assert.equal(await page.locator('#close-dialog').evaluate(e=>document.activeElement===e),true);
  // The close event restores focus after Escape's default action. Wait for that
  // event rather than racing it with a synchronous activeElement assertion.
  await page.evaluate(()=>{window.dialogClosed=new Promise(resolve=>document.querySelector('dialog.skill-dialog').addEventListener('close',()=>resolve(),{once:true}));});
  await page.keyboard.press('Escape');await page.evaluate(()=>window.dialogClosed);assert.equal(await page.locator('#library-settings').evaluate(e=>document.activeElement===e),true);
  await addMenu('#create-skill');assert.equal(await page.getByLabel('What should this skill help you do?').count(),1);await close();
 });
 await checked('Light theme and narrow layout',async()=>{
  await page.locator('#project-agent').selectOption('codex');await page.locator('#preview-usage').click();await page.locator('.history-coverage').waitFor();
  await page.locator('[data-theme-toggle]').click();assert.equal(await page.locator('html').getAttribute('data-theme'),'light');await contrast();await page.screenshot({animations:'disabled',path:out+'/history-light.png'});
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await page.screenshot({animations:'disabled',path:out+'/history-mobile.png',fullPage:true});
  await page.locator('#library-settings').click();await page.locator('.agent-capabilities summary').click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await page.screenshot({animations:'disabled',path:out+'/capabilities-mobile.png'});await close();
 });
 await checked('Large library, long names, duplicates and filtering',async()=>{
  await page.setViewportSize({width:1440,height:1000});await page.locator('#project-scope').selectOption('');await page.locator('[data-manage-tab="installed"]').first().click();
  for(let i=0;i<180;i++){const name='large-library-example-'+String(i).padStart(3,'0')+'-with-a-long-descriptive-name';const folder=fixture+'/skills/'+name;fs.mkdirSync(folder);fs.writeFileSync(folder+'/SKILL.md',`---\nname: ${name}\ndescription: A long synthetic description for checking library filtering and layout.\n---\nVerify the result.`);}
  const duplicate=fixture+'/.codex/skills/browser-example';fs.mkdirSync(duplicate,{recursive:true});fs.writeFileSync(duplicate+'/SKILL.md','---\nname: browser-example\ndescription: Another copy in a compatible library.\n---\nVerify the duplicate warning.');
  await page.waitForFunction(()=>document.querySelectorAll('.library-row').length>=182,{},{timeout:15000});
  await page.locator('#search').fill('browser-example');await page.waitForFunction(()=>document.querySelectorAll('.library-row').length===2);assert.match(await page.locator('.library-row').first().innerText(),/Multiple copies/);
  await page.locator('.library-name').first().click();assert.match(await page.locator('#dialog-body').innerText(),/Other copies/);await close();
  await page.locator('#search').fill('large-library-example-179');await page.waitForFunction(()=>document.querySelectorAll('.library-row').length===1);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await page.screenshot({animations:'disabled',path:out+'/long-name-mobile.png',fullPage:true});
  await page.locator('#search').fill('no matching fixture');assert.match(await page.locator('.library-empty').innerText(),/No matching skills/);await page.locator('#search').fill('');
 });
 await checked('Editable drafts, validation, file previews, revision and saved recovery',async()=>{
  await page.setViewportSize({width:1440,height:1000});
  await addMenu('#import-skill');await page.locator('#md-content').fill('---\nname: editable-preview\ndescription: Test editable drafts.\n---\nReview these synthetic instructions.');await page.locator('#import-form button[type=submit]').click();await page.locator('#edit-draft').waitFor();
  await page.locator('#candidate-preview summary').first().click();await page.locator('[data-draft-file="SKILL.md"]').click();assert.match(await page.locator('.skill-preview').innerText(),/editable-preview/);await page.locator('#draft-back').click();
  await page.locator('#edit-draft').click();const original=await page.locator('#draft-content').inputValue();await page.locator('#draft-content').fill(original.replace('editable-preview','INVALID NAME'));await page.locator('#validate-draft').click();await page.waitForFunction(()=>document.querySelector('#form-message').textContent.includes('Name must'));assert.equal(await page.locator('#apply-draft').isDisabled(),true);
  await page.locator('#draft-content').fill(original+'\nAn edited step.');await page.locator('#validate-draft').click();await page.waitForFunction(()=>!document.querySelector('#apply-draft').disabled);await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await page.screenshot({path:out+'/draft-editor-mobile.png'});await page.locator('#apply-draft').scrollIntoViewIfNeeded();await page.screenshot({path:out+'/draft-editor-mobile-actions.png'});await page.locator('#apply-draft').click();await page.setViewportSize({width:1440,height:1000});await page.locator('#draft-revisions').click();assert.match(await page.locator('.skill-preview').innerText(),/edited step/);await page.locator('#draft-back').click();
  await page.locator('#save-draft').click();await page.waitForFunction(()=>document.querySelector('#save-draft').textContent==='Saved locally');await page.locator('#revise-draft').click();await page.locator('#revision-request').fill('FIXTURE_FAIL preserve this revision request');await page.locator('#run-revision').click();await page.locator('#edit-job-input').waitFor();await page.locator('#edit-job-input').click();assert.equal(await page.locator('#revision-request').inputValue(),'FIXTURE_FAIL preserve this revision request');await page.locator('#revision-request').fill('Add a final check.');await page.locator('#run-revision').click();await page.locator('#edit-draft').waitFor();assert.match(await page.locator('#candidate-preview .skill-preview').innerText(),/Revised fixture instruction/);
  await page.locator('#draft-revisions').click();assert.match(await page.locator('.skill-preview').innerText(),/Revised fixture instruction/);await page.screenshot({path:out+'/draft-revision.png'});await page.locator('#draft-back').click();await page.locator('#discard-draft').click();
  await addMenu('#saved-drafts');await page.locator('[data-open-draft]').waitFor();assert.equal(await page.locator('[data-open-draft]').count(),1);assert.ok(await page.locator('[data-resume-draft]').count()>0);await page.locator('[data-open-draft]').click();assert.match(await page.locator('#candidate-preview .skill-preview').innerText(),/An edited step/);assert.doesNotMatch(await page.locator('#candidate-preview .skill-preview').innerText(),/Revised fixture instruction/);await page.locator('#discard-draft').click();
  await addMenu('#saved-drafts');await page.locator('[data-delete-draft]').click();await page.locator('#confirm-delete-draft').click();await page.waitForFunction(()=>document.querySelectorAll('[data-delete-draft]').length===0);const previews=(await api('/api/saved-drafts',{})).previews;for(const p of previews)await api('/api/discard',{draft:p.draft});await close();
 });
 await checked('Duplicate and multiple-agent copies with comparison and conflicts',async()=>{
  await page.locator('#search').fill('browser-example');await page.locator('.library-name').first().click();await page.locator('[data-duplicate-skill]').click();await page.locator('#duplicate-name').fill('night-copy');await page.locator('#prepare-duplicate').click();await page.locator('#install-draft').click();await page.locator('[data-first-step]').waitFor();await close();
  await page.locator('#search').fill('night-copy');await page.waitForFunction(()=>document.querySelectorAll('.library-row').length===1);await page.locator('.library-name').click();await page.locator('[data-multi-copy]').click();await page.locator('[data-copy-agent="claude"]').check();await page.locator('[data-copy-agent="opencode"]').check();await page.locator('#prepare-multi-copy').click();await page.locator('#install-multi-copy').click();await page.waitForFunction(()=>document.querySelectorAll('[data-copy-selection]').length===0);await page.screenshot({path:out+'/multi-copy.png'});await page.locator('#discard-multi-copy').click();
  await page.waitForFunction(()=>document.querySelectorAll('.library-row').length===3);await page.locator('.library-name').first().click();await page.locator('[data-compare-copies]').click();await page.locator('#run-copy-comparison').click();await page.waitForFunction(()=>document.querySelector('#copy-comparison-result').textContent.includes('identical'));await close();
  const changed=fixture+'/.claude/skills/night-copy/SKILL.md';fs.appendFileSync(changed,'\nChanged copy.');await page.locator('.library-name').first().click();await page.locator('[data-compare-copies]').click();await page.locator('#compare-copy').selectOption(await page.locator('#compare-copy option').evaluateAll(options=>options.find(o=>o.textContent.endsWith('/.claude/skills/night-copy')).value));await page.locator('#run-copy-comparison').click();await page.waitForFunction(()=>document.querySelector('#copy-comparison-result').textContent.includes('diverged'));await close();
  await page.locator('.library-name').first().click();await page.locator('[data-multi-copy]').click();await page.locator('[data-copy-agent="claude"]').check();await page.locator('#prepare-multi-copy').click();await page.locator('#discard-multi-copy').waitFor();assert.match(await page.locator('#dialog-body').innerText(),/already exists/);assert.equal(await page.locator('[data-copy-selection]').count(),0);await page.locator('#discard-multi-copy').click();assert.match(fs.readFileSync(changed,'utf8'),/Changed copy/);await page.locator('#search').fill('');
 });
 await checked('Deeper history scan, coverage table and excerpt filters',async()=>{
  await page.locator('[data-manage-tab="for-you"]').first().click();await page.locator('#preview-usage').click();await page.locator('#preview-deeper').click();await page.waitForFunction(()=>document.querySelector('.history-coverage')?.textContent.includes('128 MB read'));assert.match(await page.locator('.history-coverage').innerText(),/128/);
  await page.locator('#usage-filter-text').fill('other');assert.equal(await page.locator('.usage-excerpts article:visible').count(),1);assert.match(await page.locator('#usage-selected-count').innerText(),/2 selected/);await page.locator('#usage-filter-text').fill('');
  await page.locator('#usage-filter-project').selectOption({label:'QA project'});assert.equal(await page.locator('.usage-excerpts article:visible').count(),1);await page.locator('#usage-filter-project').selectOption('');await page.getByText('Prompts found by date and project',{exact:true}).click();assert.ok(await page.locator('.history-coverage tbody tr').count()>0);await page.screenshot({path:out+'/history-breakdown.png'});
 });
 await checked('Model discovery, explicit connection test and readiness states',async()=>{
  await page.locator('#library-settings').click();await page.locator('#author-provider').selectOption('opencode');await page.locator('#list-opencode-models').click();await page.locator('#model-search').waitFor();await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await page.screenshot({path:out+'/model-picker-mobile.png'});await page.setViewportSize({width:1440,height:1000});await page.locator('#model-search').fill('other');assert.equal(await page.locator('[data-model-id]').count(),1);await page.locator('[data-model-id]').click();
  await page.locator('#library-settings').click();assert.equal(await page.locator('#author-model').inputValue(),'opencode/test-other');await page.locator('#test-provider').click();assert.match(await page.locator('#dialog-body').innerText(),/synthetic prompt/);await page.locator('#confirm-provider-test').click();await page.waitForFunction(()=>document.querySelector('#dialog-title')?.textContent==='Connection test passed');await close();
  await page.locator('#library-settings').click();assert.match(await page.locator('#provider-controls').innerText(),/Connection tested this session/);fs.writeFileSync(fixture+'/fail-connection','test');await page.locator('#test-provider').click();await page.locator('#confirm-provider-test').click();await page.locator('#edit-job-input').waitFor();await page.locator('#edit-job-input').click();await page.locator('#provider-controls').waitFor();assert.doesNotMatch(await page.locator('#provider-controls').innerText(),/Connection tested this session/);fs.unlinkSync(fixture+'/fail-connection');await close();
 });
 await checked('Health report includes skills excluded from catalog',async()=>{
  const folder=fixture+'/skills/malformed-fixture';fs.mkdirSync(folder);fs.writeFileSync(folder+'/SKILL.md','No metadata');await page.locator('#library-settings').click();await page.locator('#library-health').click();await page.waitForFunction(()=>document.querySelector('#dialog-title')?.textContent==='Library health');assert.match(await page.locator('#dialog-body').innerText(),/malformed-fixture/);assert.match(await page.locator('#dialog-body').innerText(),/frontmatter/);await close();
 });

 await checked('Maintenance search, annotations, collections and quality',async()=>{
  await addMenu('#maintenance');await page.locator('[data-maint-page="search"]').click();await page.locator('#maint-query').fill('night-copy');await page.locator('#maint-search').click();await page.waitForFunction(()=>document.querySelectorAll('[data-maint-notes]').length===3);await page.locator('[data-maint-notes]').first().click();await page.locator('#maint-notes').fill('A private local maintenance note.');await page.locator('#maint-tags').fill('overnight, review');await page.locator('#maint-collections').fill('Travel');await page.locator('#maint-save-notes').click();await page.locator('[data-maint-page="search"]').click();await page.locator('#maint-query').fill('private local maintenance');await page.locator('#maint-search').click();await page.waitForFunction(()=>document.querySelectorAll('[data-maint-notes]').length===1);await page.screenshot({path:out+'/maintenance-search.png'});
  await page.locator('[data-maint-quality]').click();await page.locator('#maint-export-quality').waitFor();assert.match(await page.locator('#dialog-body').innerText(),/Installation checks passed/);await close();await addMenu('#maintenance');await page.locator('[data-maint-page="collections"]').click();await page.waitForFunction(()=>document.querySelector('#dialog-title')?.textContent==='Local collections');assert.match(await page.locator('#dialog-body').innerText(),/Travel/);await close();
 });
 await checked('Upstream update review preserves local supporting edits',async()=>{
  await addMenu('#import-skill');await page.locator('#import-mode').selectOption('github');await page.locator('#repo-url').fill('https://github.com/fixture/skills');await page.locator('#skill-target').selectOption('shared');await page.locator('#import-form button[type=submit]').click();await page.locator('#install-draft').click();await page.locator('[data-first-step]').waitFor();await close();fs.writeFileSync(fixture+'/skills/review-example/notes.txt','Local supporting edit.');fs.writeFileSync(fixture+'/upstream-version','two');
  await addMenu('#maintenance');await page.locator('[data-maint-page="search"]').click();await page.locator('#maint-query').fill('review-example');await page.locator('#maint-search').click();await page.waitForFunction(()=>document.querySelectorAll('[data-maint-provenance]').length===1);await page.locator('[data-maint-provenance]').click();await page.locator('#maint-upstream-ref').waitFor();assert.match(await page.locator('#dialog-body').innerText(),/Local files differ/);await page.locator('[data-upstream-check]').click();await page.locator('#maint-prepare-update').waitFor();await page.screenshot({path:out+'/upstream-review.png'});await page.locator('#maint-prepare-update').click();await page.locator('#compare-replacement').click();await page.locator('#confirm-replacement').check();await page.locator('#replace-skill').click();await page.locator('dialog.skill-dialog').waitFor({state:'hidden'});assert.match(fs.readFileSync(fixture+'/skills/review-example/SKILL.md','utf8'),/version two/);assert.equal(fs.readFileSync(fixture+'/skills/review-example/notes.txt','utf8'),'Local supporting edit.');
 });
 await checked('Supporting file editor, export and persistent revisions',async()=>{
  await addMenu('#import-skill');await page.locator('#import-mode').selectOption('markdown');await page.locator('#md-content').fill('---\nname: draft-files-example\ndescription: Verify complete supporting file changes locally.\n---\n# Example\nKeep the original instruction.');await page.locator('#import-form button[type=submit]').click();await page.locator('#maint-draft-tools').click();await page.locator('#maint-add-file').click();await page.locator('#maint-file-path').fill('references/notes.md');await page.locator('#maint-file-content').fill('# Notes\nOriginal supporting text.');await page.locator('#maint-file-save').click();await page.locator('#install-draft').waitFor();await page.locator('#maint-draft-tools').click();await page.locator('[data-maint-file="references/notes.md"]').click();await page.locator('#maint-file-content').fill('# Notes\nEdited supporting text.');await page.locator('#maint-file-save').click();await page.locator('#install-draft').waitFor();await page.locator('#maint-draft-tools').click();await page.locator('#maint-tree-revisions').click();await page.locator('[data-tree-revision]').first().waitFor();assert.equal(await page.locator('[data-tree-revision]').count(),2);await page.locator('[data-tree-revision]').last().click();await page.locator('#install-draft').waitFor();await page.locator('#maint-draft-tools').click();await page.locator('[data-maint-file="references/notes.md"]').click();assert.match(await page.locator('#maint-file-content').inputValue(),/Original supporting/);await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await page.screenshot({path:out+'/supporting-editor-mobile.png'});await page.setViewportSize({width:1440,height:1000});await page.locator('#maint-draft-tools').click();await page.locator('#maint-markdown').click();assert.equal(await page.locator('.maint-markdown h1').innerText(),'Example');await page.locator('#maint-draft-tools').click();const downloadPromise=page.waitForEvent('download');await page.locator('#maint-export-draft').click();const download=await downloadPromise;await download.saveAs(out+'/draft-export.zip');await close();
  const previews=await api('/api/saved-drafts',{});for(const draft of previews.previews)await api('/api/discard',{draft:draft.draft});await page.evaluate(()=>{activeDraft=null;clearJobStatus();});
 });
 await checked('Reviewed workspace backup and selected restoration',async()=>{
  await addMenu('#maintenance');await page.locator('[data-maint-page="backup"]').click();await page.locator('[data-maint-select="review-example"]').check();const pending=page.waitForEvent('download');await page.locator('#maint-backup-export').click();const download=await pending;await download.saveAs(out+'/workspace-backup.zip');fs.writeFileSync(fixture+'/skills/review-example/notes.txt','Changed after backup.');await page.locator('#maint-backup-file').setInputFiles(out+'/workspace-backup.zip');await page.locator('#maint-backup-preview').click();await page.locator('[data-restore-select="0"]').check();await page.locator('[data-restore-replace="0"]').check();await page.screenshot({path:out+'/restore-review.png'});await page.locator('#maint-restore').click();await page.waitForFunction(()=>document.querySelector('#dialog-title')?.textContent==='Restore results');assert.match(await page.locator('#dialog-body').innerText(),/restored/);assert.equal(fs.readFileSync(fixture+'/skills/review-example/notes.txt','utf8'),'Local supporting edit.');await close();
 });
 await checked('History exclusions and explicitly saved sample',async()=>{
  await page.locator('[data-manage-tab="for-you"]').first().click();await page.locator('#usage-provider').selectOption('codex');await page.locator('#preview-usage').click();await page.locator('#maint-save-sample').click();await addMenu('#maintenance');await page.locator('[data-maint-page="history"]').click();await page.locator('#maint-save-exclusions').waitFor();assert.equal(await page.locator('[data-sample-open]').count(),1);await page.locator('#maint-exclude-projects').fill(fixture+'/other');await page.locator('#maint-save-exclusions').click();await page.locator('[data-maint-page="history"]').waitFor();await close();await page.locator('#preview-usage').click();await page.waitForFunction(()=>document.querySelectorAll('[data-usage-text]').length===1);assert.match(await page.locator('.history-coverage').innerText(),/excluded by your settings/);await addMenu('#maintenance');await page.locator('[data-maint-page="history"]').click();await page.locator('[data-sample-open]').click();await page.locator('dialog.skill-dialog').waitFor({state:'hidden'});await page.waitForFunction(()=>document.querySelectorAll('[data-usage-text]').length===2);assert.equal(await page.locator('[data-usage-text]').count(),2);
 });
 await checked('Maintenance keyboard return focus',async()=>{await addMenu('#maintenance');await page.waitForFunction(()=>document.querySelector('dialog.skill-dialog')?.open&&document.querySelector('#dialog-title')?.textContent==='Maintain library');assert.equal(await page.locator('#dialog-title').evaluate(e=>document.activeElement===e),true);await page.keyboard.press('Escape');await page.locator('dialog.skill-dialog').waitFor({state:'hidden'});await page.waitForFunction(()=>document.activeElement===document.querySelector('#add-skills-menu summary'));assert.equal(await page.locator('#add-skills-menu summary').evaluate(e=>document.activeElement===e),true);});
 await checked('No runtime or console errors',async()=>assert.deepEqual(errors,[]));
 }catch(error){fs.writeFileSync(out+'/failure.txt',await page.locator('body').innerText());await page.screenshot({animations:'disabled',path:out+'/failure.png'});throw error;}finally{fs.writeFileSync(out+'/checks.json',JSON.stringify({url,checks,errors},null,2));await browser.close();}
 console.log(JSON.stringify(checks));
})().catch(e=>{console.error(e);process.exitCode=1;});
