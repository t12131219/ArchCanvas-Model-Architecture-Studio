#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::Write;
use std::process::{Command, Stdio};

use serde_json::{json, Value};

const MAX_REQUEST_BYTES: usize = 1_000_000;

fn request_id(request: &Value) -> Value {
    request
        .get("request_id")
        .filter(|value| {
            value
                .as_str()
                .is_some_and(|id| id.starts_with("engine-request:"))
        })
        .cloned()
        .unwrap_or_else(|| Value::String("engine-request:desktop-invalid".into()))
}

fn rejected(request: &Value, code: &str, message: &str) -> Value {
    json!({
        "schema_version": "1.0",
        "request_id": request_id(request),
        "status": "rejected",
        "error": { "code": code, "message": message }
    })
}

fn sidecar_configuration(request: &Value) -> Result<(String, String), Value> {
    let python = std::env::var("ARCHCANVAS_ENGINE_PYTHON").map_err(|_| {
        rejected(
            request,
            "ENGINE_SIDECAR_NOT_CONFIGURED",
            "Set ARCHCANVAS_ENGINE_PYTHON to the approved Engine interpreter.",
        )
    })?;
    let cache_root = std::env::var("ARCHCANVAS_ENGINE_CACHE_ROOT").map_err(|_| {
        rejected(
            request,
            "ENGINE_SIDECAR_NOT_CONFIGURED",
            "Set ARCHCANVAS_ENGINE_CACHE_ROOT to an Engine-owned cache directory.",
        )
    })?;
    Ok((python, cache_root))
}

/// Forward one typed RPC envelope to the Engine sidecar. This bridge does not inspect project
/// paths, read source, or implement any project mutation.
#[tauri::command]
fn engine_rpc(request: Value) -> Value {
    let request_bytes = match serde_json::to_vec(&request) {
        Ok(bytes) if bytes.len() <= MAX_REQUEST_BYTES => bytes,
        Ok(_) => return rejected(&request, "REQUEST_TOO_LARGE", "request exceeds byte limit"),
        Err(_) => {
            return rejected(
                &request,
                "INVALID_ENGINE_REQUEST",
                "request is not serializable",
            )
        }
    };
    let (python, cache_root) = match sidecar_configuration(&request) {
        Ok(configuration) => configuration,
        Err(response) => return response,
    };
    let mut child = match Command::new(python)
        .args(["-m", "archcanvas_engine.stdio", "--cache-root"])
        .arg(cache_root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(child) => child,
        Err(_) => {
            return rejected(
                &request,
                "ENGINE_SIDECAR_START_FAILED",
                "could not start Engine sidecar",
            )
        }
    };
    if let Some(stdin) = child.stdin.as_mut() {
        if stdin.write_all(&request_bytes).is_err() || stdin.write_all(b"\n").is_err() {
            return rejected(
                &request,
                "ENGINE_SIDECAR_IO_FAILED",
                "could not write Engine request",
            );
        }
    } else {
        return rejected(
            &request,
            "ENGINE_SIDECAR_IO_FAILED",
            "Engine sidecar has no standard input",
        );
    }
    let output = match child.wait_with_output() {
        Ok(output) if output.status.success() => output,
        _ => {
            return rejected(
                &request,
                "ENGINE_SIDECAR_FAILED",
                "Engine sidecar exited without a response",
            )
        }
    };
    match serde_json::from_slice::<Value>(&output.stdout) {
        Ok(response) => response,
        Err(_) => rejected(
            &request,
            "ENGINE_SIDECAR_INVALID_RESPONSE",
            "Engine sidecar returned invalid JSON",
        ),
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![engine_rpc])
        .run(tauri::generate_context!())
        .expect("error while running ArchCanvas desktop");
}
