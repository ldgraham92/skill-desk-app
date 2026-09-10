/* Run in the head, before paint. No remote assets or background polling. */
(()=>{
 const key='skill-desk-theme',root=document.documentElement;
 let theme='dark';try{theme=localStorage.getItem(key)==='light'?'light':'dark';}catch{}
 if(['dark','light'].includes(window.skillDeskTheme))theme=window.skillDeskTheme;
 function apply(value){theme=value;root.dataset.theme=theme;document.querySelector('meta[name="color-scheme"]')?.setAttribute('content',theme);document.querySelectorAll('[data-theme-toggle]').forEach(button=>{button.setAttribute('aria-label','Switch to '+(theme==='dark'?'light':'dark')+' mode');button.title=button.getAttribute('aria-label');button.setAttribute('aria-pressed',String(theme==='dark'));button.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true">'+(theme==='dark'?'<path d="M20 14a8 8 0 0 1-10-10 8 8 0 1 0 10 10Z"/>':'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>')+'</svg><span>'+ (theme==='dark'?'Dark':'Light')+'</span>';});}
 apply(theme);
 document.addEventListener('DOMContentLoaded',()=>apply(theme));
 document.addEventListener('click',event=>{if(!event.target.closest('[data-theme-toggle]'))return;apply(theme==='dark'?'light':'dark');try{localStorage.setItem(key,theme);}catch{}window.skillDeskSaveTheme?.(theme);});
 window.addEventListener('storage',event=>{if(event.key===key)apply(event.newValue==='light'?'light':'dark');});
})();
