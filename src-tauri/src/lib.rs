use std::sync::atomic::{AtomicU16, Ordering};
use std::sync::Arc;
use tauri::{AppHandle, Manager, State, WebviewWindowBuilder, WebviewUrl};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandEvent;

pub struct BackendState {
    pub port: Arc<AtomicU16>,
}

#[tauri::command]
fn get_system_status() -> String {
    "KUANTRA_CORE_ONLINE".into()
}

#[tauri::command]
fn get_backend_port(state: State<'_, BackendState>) -> u16 {
    state.port.load(Ordering::SeqCst)
}

#[tauri::command]
fn get_backend_url(state: State<'_, BackendState>) -> String {
    let port = state.port.load(Ordering::SeqCst);
    if port == 0 {
        "http://127.0.0.1:8000".into()
    } else {
        format!("http://127.0.0.1:{}", port)
    }
}

#[tauri::command]
async fn create_popout_window(
    app: AppHandle,
    label: String,
    title: String,
    url: String,
    width: f64,
    height: f64,
) -> Result<String, String> {
    if let Some(existing) = app.get_webview_window(&label) {
        let _ = existing.set_focus();
        return Ok(format!("Focused existing window: {}", label));
    }

    let webview_url = if url.starts_with("http") {
        WebviewUrl::External(url.parse().map_err(|e| format!("Invalid URL: {}", e))?)
    } else {
        WebviewUrl::App(url.into())
    };

    WebviewWindowBuilder::new(&app, &label, webview_url)
        .title(&title)
        .inner_size(width, height)
        .min_inner_size(600.0, 400.0)
        .resizable(true)
        .decorations(true)
        .build()
        .map_err(|e| format!("Failed to create pop-out window: {}", e))?;

    println!("[+] Pop-out window created: {} ('{}')", label, title);
    Ok(format!("Created window {}", label))
}

pub fn spawn_sidecar(app: &AppHandle, port_state: Arc<AtomicU16>) {
    let parent_pid = std::process::id();
    let shell = app.shell();

    let sidecar_cmd = shell.sidecar("kuantra-backend");
    
    match sidecar_cmd {
        Ok(cmd) => {
            let cmd_with_args = cmd.args([
                "--port", "0",
                "--parent-pid", &parent_pid.to_string(),
            ]);

            let (mut rx, _child) = cmd_with_args
                .spawn()
                .expect("Failed to spawn Kuantra Terminal backend sidecar");

            println!("[+] Spawning Kuantra Backend sidecar with Parent PID: {}", parent_pid);

            let port_holder = port_state.clone();
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            let text = String::from_utf8_lossy(&line);
                            print!("{}", text);
                            
                            if let Some(pos) = text.find("KUANTRA_BACKEND_PORT:") {
                                let remainder = &text[pos + "KUANTRA_BACKEND_PORT:".len()..];
                                if let Some(first_line) = remainder.lines().next() {
                                    if let Ok(parsed_port) = first_line.trim().parse::<u16>() {
                                        port_holder.store(parsed_port, Ordering::SeqCst);
                                        println!("[+] Intercepted dynamic backend port: {}", parsed_port);
                                    }
                                }
                            }
                        }
                        CommandEvent::Stderr(line) => {
                            eprint!("{}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Terminated(payload) => {
                            println!("[-] Backend sidecar terminated with code: {:?}", payload.code);
                            break;
                        }
                        _ => {}
                    }
                }
            });
        }
        Err(e) => {
            eprintln!("[!] Note: Sidecar binary not found in dev mode (fallback to Python): {}", e);
            port_state.store(8000, Ordering::SeqCst);
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let port_state = Arc::new(AtomicU16::new(8000));
    let managed_state = BackendState {
        port: port_state.clone(),
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .manage(managed_state)
        .invoke_handler(tauri::generate_handler![
            get_system_status,
            get_backend_port,
            get_backend_url,
            create_popout_window
        ])
        .setup(move |app| {
            spawn_sidecar(app.handle(), port_state);
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Kuantra Terminal application");
}