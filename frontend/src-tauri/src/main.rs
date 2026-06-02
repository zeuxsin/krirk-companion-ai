// Prevents additional console window on Windows in release — NÃO REMOVER
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    krirk_lib::run()
}
