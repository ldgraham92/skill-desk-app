#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::sync::Mutex;
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder, menu::{Menu, MenuItem}, tray::TrayIconBuilder};
use tauri_plugin_shell::{ShellExt, process::{CommandChild, CommandEvent}};

mod updates;
struct Service(Mutex<Option<CommandChild>>);
fn stop(app: &tauri::AppHandle) {
    if let Some(mut child) = app.state::<Service>().0.lock().unwrap().take() {
        let _ = child.write(b"q");
    }
}
fn show(app: &tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("main") { let _ = w.show(); let _ = w.unminimize(); let _ = w.set_focus(); }
}
fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| show(app)))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(updates::Updates::default())
        .invoke_handler(tauri::generate_handler![updates::update_status,updates::update_check,updates::update_install])
        .on_page_load(|window, _| { if window.label()=="main" { updates::sync_button(window.app_handle()); } })
        .manage(Service(Mutex::new(None)))
        .setup(|app| {
            let navigation_app=app.handle().clone();
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("Skill-Desk").inner_size(1180.0, 800.0).min_inner_size(760.0, 560.0)
                .icon(app.default_window_icon().unwrap().clone())?
                .on_navigation(move |url| { if url.scheme()=="skilldesk" && url.host_str()==Some("updates") {updates::open(&navigation_app);false} else {true} }).build()?;
            let open = MenuItem::with_id(app, "open", "Open Skill-Desk", true, None::<&str>)?;
            let hide = MenuItem::with_id(app, "hide", "Hide to tray", true, None::<&str>)?;
            let update_menu = MenuItem::with_id(app, "updates", "Check for updates", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit Skill-Desk", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &hide, &update_menu, &quit])?;
            TrayIconBuilder::new().icon(app.default_window_icon().unwrap().clone())
                .tooltip("Skill-Desk").menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() { "open" => show(app), "updates" => updates::open(app), "hide" => { if let Some(w) = app.get_webview_window("main") { let _ = w.hide(); } }, "quit" => { stop(app); app.exit(0); }, _ => {} })
                .build(app)?;
            // The loopback page receives no Tauri IPC capabilities. Only Rust can
            // start the bundled service or perform native desktop operations.
            let (mut rx, child) = app.shell().sidecar("skilldesk-service")?
                .args(["--desktop", "--port", "0", "--parent-pid", &std::process::id().to_string()]).spawn()?;
            *app.state::<Service>().0.lock().unwrap() = Some(child);
            updates::automatic(app.handle().clone());
            let window_events = window.clone();
            tauri::async_runtime::spawn(async move {
                let mut diagnostics = String::new();
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            let line = String::from_utf8_lossy(&bytes);
                            if let Some(token)=line.trim().strip_prefix("Skill-Desk control: ") { window_events.app_handle().state::<updates::Updates>().connection.lock().unwrap().1=token.to_string(); }
                            if let Some(url) = line.trim().strip_prefix("Skill-Desk: ") {
                                window_events.app_handle().state::<updates::Updates>().connection.lock().unwrap().0=url.to_string();
                                if url.starts_with("http://127.0.0.1:") {
                                    if let Ok(url) = url.parse() {
                                        let _ = window_events.navigate(url);
                                    }
                                }
                            }
                        }
                        CommandEvent::Stderr(bytes) => { diagnostics.push_str(&String::from_utf8_lossy(&bytes)); }
                        CommandEvent::Terminated(_) => {
                            let message = format!("The local service stopped. Quit and reopen Skill-Desk. {}", diagnostics.chars().take(2000).collect::<String>());
                            let js = format!("document.body.innerHTML='';const h=document.createElement('h1');h.textContent='Skill-Desk could not start';document.body.append(h);const p=document.createElement('p');p.textContent={};document.body.append(p)", serde_json::to_string(&message).unwrap());
                            let _ = window_events.eval(&js);
                            break;
                        }
                        _ => {}
                    }
                }
            });
            // Closing the last window quits; background residency is not forced.
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event { if window.label()!="main" {return;} stop(window.app_handle()); window.app_handle().exit(0); }
        })
        .build(tauri::generate_context!()).expect("Could not start Skill-Desk");
    app.run(|app, event| {
        if matches!(event, tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit) {
            stop(app);
        }
    });
}
