use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
    Manager, WindowEvent,
};

#[tauri::command]
fn set_always_on_top(window: tauri::WebviewWindow, value: bool) {
    let _ = window.set_always_on_top(value);
}

#[tauri::command]
fn open_settings(app: tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("settings") {
        let _ = w.show();
        let _ = w.set_focus();
    }
}

#[tauri::command]
fn close_settings(app: tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("settings") {
        let _ = w.hide();
    }
}

#[tauri::command]
fn set_compact_mode(window: tauri::WebviewWindow, compact: bool) -> Result<(), String> {
    use tauri::{LogicalSize, LogicalPosition};

    if compact {
        let monitor = window.current_monitor()
            .map_err(|e| e.to_string())?
            .ok_or_else(|| "Monitor não encontrado".to_string())?;

        let scale = monitor.scale_factor();
        let phys  = monitor.size();
        let sw = phys.width  as f64 / scale;
        let sh = phys.height as f64 / scale;

        let (w, h, taskbar) = (230.0_f64, 400.0_f64, 48.0_f64);

        window.set_size(LogicalSize::new(w, h))
            .map_err(|e| e.to_string())?;
        window.set_position(LogicalPosition::new(sw - w - 16.0, sh - h - taskbar))
            .map_err(|e| e.to_string())?;
        window.set_always_on_top(true)
            .map_err(|e| e.to_string())?;
    } else {
        window.set_size(LogicalSize::new(560.0_f64, 420.0_f64))
            .map_err(|e| e.to_string())?;
        window.center()
            .map_err(|e| e.to_string())?;
        window.set_always_on_top(false)
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Retorna se a janela principal está visível.
/// Usado pelo frontend para decidir se deve enviar notificação nativa.
#[tauri::command]
fn is_window_visible(app: tauri::AppHandle) -> bool {
    app.get_webview_window("main")
        .and_then(|w| w.is_visible().ok())
        .unwrap_or(false)
}

/// Oculta a janela principal para a bandeja (remove da taskbar).
#[tauri::command]
fn hide_to_tray(app: tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.hide();
        let _ = w.set_skip_taskbar(true);
    }
}

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.set_skip_taskbar(false);
        let _ = w.set_focus();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![
            set_always_on_top,
            open_settings,
            close_settings,
            set_compact_mode,
            is_window_visible,
            hide_to_tray,
        ])
        .setup(|app| {
            // ── System Tray ───────────────────────────────────────────────────
            let show  = MenuItem::with_id(app, "show",  "Mostrar KRIRK",         true, None::<&str>)?;
            let hide  = MenuItem::with_id(app, "hide",  "Ocultar para bandeja",   true, None::<&str>)?;
            let config= MenuItem::with_id(app, "config","Configurações",           true, None::<&str>)?;
            let sep   = PredefinedMenuItem::separator(app)?;
            let quit  = MenuItem::with_id(app, "quit",  "Sair",                   true, None::<&str>)?;

            let menu = Menu::with_items(app, &[&show, &hide, &config, &sep, &quit])?;

            TrayIconBuilder::new()
                .tooltip("KRIRK — Companion AI")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "quit"   => app.exit(0),
                    "show"   => show_main_window(app),
                    "hide"   => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.hide();
                            let _ = w.set_skip_taskbar(true);
                        }
                    }
                    "config" => {
                        if let Some(w) = app.get_webview_window("settings") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let tauri::tray::TrayIconEvent::Click {
                        button: tauri::tray::MouseButton::Left,
                        button_state: tauri::tray::MouseButtonState::Up, ..
                    } = event {
                        show_main_window(tray.app_handle());
                    }
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let label = window.label();
                if label == "main" {
                    // Janela principal → esconde para a bandeja (some da taskbar)
                    let _ = window.hide();
                    let _ = window.set_skip_taskbar(true);
                    api.prevent_close();
                }
                if label == "settings" {
                    let _ = window.hide();
                    api.prevent_close();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("Erro ao iniciar o KRIRK");
}
