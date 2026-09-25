// Runs only when a debug app is explicitly launched with a synthetic test script.
(async()=>{
 if(window.__skillDeskNativeTest)return;window.__skillDeskNativeTest=true;
 const checks=[],errors=[];window.addEventListener('error',e=>errors.push(e.message));
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 async function wait(fn,label){const end=Date.now()+15000;while(Date.now()<end){if(fn())return;await sleep(50);}throw Error('Timed out: '+label);}
 const q=s=>document.querySelector(s);
 async function click(selector){await wait(()=>q(selector)&&!q(selector).disabled,selector);q(selector).click();await sleep(80);}
 function fill(selector,value){q(selector).value=value;q(selector).dispatchEvent(new Event('input',{bubbles:true}));}
 function assert(value,message){if(!value)throw Error(message);checks.push(message);}
 try{
  await wait(()=>window.skillDeskToken&&q('[data-view="manage"]'),'app scripts');
  assert(window.skillDeskMode==='test','Synthetic test instance');
  assert(navigator.userAgent.includes('AppleWebKit'),'Native WebKit renderer');
  await click('[data-view="manage"]');await click('#add-skills-menu summary');await click('#import-skill');
  fill('#md-content','---\nname: native-review\ndescription: Verify native WebKit maintenance interactions locally.\n---\n# Native example\nKeep this instruction.');
  await click('#import-form button[type="submit"]');await wait(()=>q('#install-draft'),'import preview');
  assert(q('#dialog-body').textContent.includes('native-review'),'Native import preview');
  await click('#maint-draft-tools');await click('#maint-add-file');fill('#maint-file-path','notes.md');fill('#maint-file-content','# Notes\nNative supporting file.');await click('#maint-file-save');await wait(()=>q('#install-draft'),'supporting file preview');
  assert(q('#dialog-body').textContent.includes('notes.md'),'Native supporting file edit');
  await click('#install-draft');await wait(()=>q('[data-first-step]'),'installed');await click('#close-dialog');
  await click('#add-skills-menu summary');await click('#maintenance');await click('[data-maint-page="search"]');await wait(()=>q('#maint-query'),'search form');fill('#maint-query','native-review');await click('#maint-search');await wait(()=>q('[data-maint-notes]'),'search result');
  assert(q('#maint-results').textContent.includes('native-review'),'Native full instruction search');
  await click('[data-maint-notes]');fill('#maint-notes','Synthetic native notes');fill('#maint-tags','native');await click('#maint-save-notes');await wait(()=>q('[data-maint-page="search"]'),'saved notes');
  assert(document.documentElement.scrollWidth<=innerWidth+1,'No horizontal overflow');
  assert(errors.length===0,'No native JavaScript errors');
 }catch(error){errors.push(String(error));}
 await wait(()=>window.skillDeskToken,'report token');
 await fetch('/api/native-test-report',{method:'POST',headers:{'Content-Type':'application/json','X-Skill-Desk-Token':window.skillDeskToken},body:JSON.stringify({checks,errors,passed:errors.length===0,userAgent:navigator.userAgent,width:innerWidth,height:innerHeight})});
})();
