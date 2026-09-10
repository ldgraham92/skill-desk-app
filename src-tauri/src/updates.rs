use std::{sync::{Mutex, atomic::{AtomicBool, Ordering}}, time::{Duration, SystemTime, UNIX_EPOCH}};
use serde_json::{json, Value};
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_updater::{UpdaterExt, Update};

pub struct Updates {
    pub connection: Mutex<(String, String)>,
    status: Mutex<Value>,
    update: Mutex<Option<Update>>,
    working: AtomicBool,
    opening: AtomicBool,
}
impl Default for Updates {
    fn default() -> Self { Self { connection: Mutex::new((String::new(), String::new())), status: Mutex::new(json!({"phase":"idle"})), update: Mutex::new(None), working: AtomicBool::new(false), opening: AtomicBool::new(false) } }
}
fn guard(window: &tauri::WebviewWindow) -> Result<(), String> {
    let url=window.url().map_err(|e|e.to_string())?;
    if window.label()!="updater" || !(url.scheme()=="tauri" || url.host_str()==Some("tauri.localhost")) { return Err("Updates are available only in the native updater window.".into()); }
    Ok(())
}
pub fn sync_button(app: &tauri::AppHandle) {
    let state=app.state::<Updates>().status.lock().unwrap().clone();
    if let Some(w)=app.get_webview_window("main") {
        let label=if state["phase"]=="available" {"Update available"} else {"Updates"};
        let code=format!(r#"(()=>{{const bar=document.querySelector('.topbar');if(!bar)return;let b=document.getElementById('app-updates');if(!b){{b=document.createElement('button');b.id='app-updates';b.className='button';b.onclick=()=>{{location.href='skilldesk://updates'}};bar.append(b);}}b.textContent={};}})()"#,serde_json::to_string(label).unwrap());
        let _=w.eval(&code);
    }
}
fn status(app:&tauri::AppHandle,value:Value) {
    *app.state::<Updates>().status.lock().unwrap()=value;
    sync_button(app);
}
pub fn open(app:&tauri::AppHandle) {
    if app.state::<Updates>().opening.swap(true, Ordering::SeqCst) { return; }
    let app = app.clone();
    // WebView2 creation must not block a navigation or tray event callback.
    // run_on_main_thread would still run inside the event loop; use a worker.
    tauri::async_runtime::spawn_blocking(move || {
        let result = open_window(&app);
        app.state::<Updates>().opening.store(false, Ordering::SeqCst);
        if let Err(error) = result {
            status(&app, json!({"phase":"error","message":format!("Could not open the updater: {error}")}));
            if let Some(main) = app.get_webview_window("main") {
                let _ = main.eval("if(typeof toast==='function')toast('Could not open Updates. Please quit and reopen Skill-Desk, then retry.');");
            }
        }
    });
}
fn open_window(app:&tauri::AppHandle) -> tauri::Result<()> {
    if let Some(w)=app.get_webview_window("updater") { w.show()?;w.set_focus()?;return Ok(()); }
    WebviewWindowBuilder::new(app,"updater",WebviewUrl::App("updater.html".into()))
        .title("Skill-Desk updates").inner_size(540.0,510.0).resizable(false).build()?;
    Ok(())
}
#[tauri::command]
pub async fn update_status(window:tauri::WebviewWindow,app:tauri::AppHandle)->Result<Value,String> {
    guard(&window)?;
    let mut value=app.state::<Updates>().status.lock().unwrap().clone();
    value["currentVersion"]=json!(app.package_info().version.to_string());
    Ok(value)
}
async fn check(app:&tauri::AppHandle)->Result<(),String> {
    status(app,json!({"phase":"checking"}));
    #[cfg(target_os="linux")]
    if std::env::var_os("APPIMAGE").is_none() { return Err("Automatic Linux updates require the AppImage edition. Update Debian packages through your package manager.".into()); }
    let update=app.updater_builder().timeout(Duration::from_secs(120)).build().map_err(|e|e.to_string())?.check().await.map_err(|e|e.to_string())?;
    if let Some(ref u)=update { status(app,json!({"phase":"available","version":u.version,"notes":u.body})); }
    else {status(app,json!({"phase":"current"}));}
    *app.state::<Updates>().update.lock().unwrap()=update;
    Ok(())
}
#[tauri::command]
pub async fn update_check(window:tauri::WebviewWindow,app:tauri::AppHandle)->Result<(),String> {
    guard(&window)?;
    run_check(app).await;
    Ok(())
}
async fn run_check(app:tauri::AppHandle) {
    if app.state::<Updates>().working.swap(true,Ordering::SeqCst) {return;}
    if let Err(e)=check(&app).await {status(&app,json!({"phase":"error","message":e}));}
    app.state::<Updates>().working.store(false,Ordering::SeqCst);
}
async fn service(app:&tauri::AppHandle,action:&str)->Result<Value,String> {
    let (url,token)=app.state::<Updates>().connection.lock().unwrap().clone();
    if url.is_empty() || token.is_empty() {return Err("The skill service is not ready. Reopen Skill-Desk and retry.".into());}
    reqwest::Client::new().post(format!("{url}/api/{action}"))
        .timeout(Duration::from_secs(10)).header("Origin",&url).header("X-Skill-Desk-Token",token).json(&json!({}))
        .send().await.map_err(|e|e.to_string())?.error_for_status().map_err(|e|e.to_string())?.json().await.map_err(|e|e.to_string())
}
#[tauri::command]
pub async fn update_install(window:tauri::WebviewWindow,app:tauri::AppHandle)->Result<(),String> {
    guard(&window)?;
    if app.state::<Updates>().working.swap(true,Ordering::SeqCst) {return Err("An update operation is already running.".into());}
    let result=install(&app).await;
    if let Err(ref e)=result {
        let _=service(&app,"update-resume").await;
        status(&app,json!({"phase":"error","message":e}));
    }
    app.state::<Updates>().working.store(false,Ordering::SeqCst);
    result
}
async fn install(app:&tauri::AppHandle)->Result<(),String> {
    if app.state::<Updates>().update.lock().unwrap().is_none() {check(app).await?;}
    let update=app.state::<Updates>().update.lock().unwrap().clone().ok_or("No update is available.")?;
    status(app,json!({"phase":"downloading","version":update.version,"downloaded":0}));
    let mut received=0u64;
    let mut last=std::time::Instant::now();
    let bytes=update.download(|n,total| {received+=n as u64;if last.elapsed()>Duration::from_millis(150) {status(app,json!({"phase":"downloading","downloaded":received,"total":total}));last=std::time::Instant::now();}},||{}).await.map_err(|e|e.to_string())?;
    // The plugin verifies the signature before returning download bytes.
    loop {
        let response=service(app,"update-prepare").await?;
        if response["ready"]==true {break;}
        status(app,json!({"phase":"waiting","message":response["reason"]}));
        tokio::time::sleep(Duration::from_secs(2)).await;
    }
    status(app,json!({"phase":"installing"}));
    crate::stop(app);
    // Let the helper finish shutting down before Windows replaces its executable.
    tokio::time::sleep(Duration::from_secs(2)).await;
    if let Err(e)=update.install(bytes) {
        status(app,json!({"phase":"error","message":format!("Installation failed: {e}. Quit and reopen Skill-Desk before retrying.")}));
        return Err(e.to_string());
    }
    app.restart();
}
pub fn automatic(app:tauri::AppHandle) {
    tauri::async_runtime::spawn(async move {
        loop {
            let path=app.path().app_data_dir().ok().map(|p|p.join("update-check.json"));
            let now=SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
            let cached=path.as_ref().and_then(|p|std::fs::read_to_string(p).ok()).and_then(|s|serde_json::from_str::<Value>(&s).ok()).unwrap_or(json!({}));
            let previous=cached["checked"].as_u64().unwrap_or(0);
            if app.state::<Updates>().status.lock().unwrap()["phase"]=="idle" && cached["status"]["phase"]=="available" && cached["status"]["version"]!=app.package_info().version.to_string() {status(&app,cached["status"].clone());}
            if now.saturating_sub(previous)>=86400 {
                run_check(app.clone()).await;
                if let Some(p)=&path { if let Some(parent)=p.parent(){let _=std::fs::create_dir_all(parent);}let _=std::fs::write(p,json!({"checked":now,"status":app.state::<Updates>().status.lock().unwrap().clone()}).to_string()); }
            }
            tokio::time::sleep(Duration::from_secs(86400)).await;
        }
    });
}
