#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{BufRead, BufReader, Read, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;

use serde_json::{json, Value};
use tauri::Manager;

const MAX_REQUEST_BYTES: usize = 1_000_000;
const MAX_RESPONSE_BYTES: u64 = 32_000_000;

struct Sidecar {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
    configuration: (String, String),
}

impl Sidecar {
    fn start(configuration: (String, String)) -> std::io::Result<Self> {
        let mut command = Command::new(&configuration.0);
        command.args([
            "-m",
            "archcanvas_engine.stdio",
            "--cache-root",
            &configuration.1,
        ]);
        Self::spawn(&mut command, configuration)
    }

    fn spawn(command: &mut Command, configuration: (String, String)) -> std::io::Result<Self> {
        let mut child = command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()?;
        let stdin = child.stdin.take().expect("piped child stdin");
        let stdout = BufReader::new(child.stdout.take().expect("piped child stdout"));
        Ok(Self {
            child,
            stdin,
            stdout,
            configuration,
        })
    }

    fn exchange(&mut self, request: &Value, request_bytes: &[u8]) -> Result<Value, &'static str> {
        self.stdin
            .write_all(request_bytes)
            .map_err(|_| "ENGINE_SIDECAR_IO_FAILED")?;
        self.stdin
            .write_all(b"\n")
            .map_err(|_| "ENGINE_SIDECAR_IO_FAILED")?;
        self.stdin.flush().map_err(|_| "ENGINE_SIDECAR_IO_FAILED")?;
        let mut response_bytes = Vec::new();
        self.stdout
            .by_ref()
            .take(MAX_RESPONSE_BYTES + 1)
            .read_until(b'\n', &mut response_bytes)
            .map_err(|_| "ENGINE_SIDECAR_IO_FAILED")?;
        if response_bytes.is_empty() {
            return Err("ENGINE_SIDECAR_FAILED");
        }
        if response_bytes.len() as u64 > MAX_RESPONSE_BYTES || response_bytes.last() != Some(&b'\n')
        {
            return Err("ENGINE_SIDECAR_INVALID_RESPONSE");
        }
        let response: Value = serde_json::from_slice(&response_bytes)
            .map_err(|_| "ENGINE_SIDECAR_INVALID_RESPONSE")?;
        if response.get("request_id") != request.get("request_id") {
            return Err("ENGINE_SIDECAR_INVALID_RESPONSE");
        }
        Ok(response)
    }
}

impl Drop for Sidecar {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn snake_case(key: &str) -> String {
    let mut result = String::with_capacity(key.len());
    for character in key.chars() {
        if character.is_ascii_uppercase() {
            result.push('_');
            result.push(character.to_ascii_lowercase());
        } else {
            result.push(character);
        }
    }
    result
}

// Tauri's IPC serializers may camel-case nested JavaScript object keys. The Engine protocol is
// deliberately snake_case, so normalize the transport representation before strict validation.
fn normalize_request(value: Value) -> Value {
    match value {
        Value::Array(items) => Value::Array(items.into_iter().map(normalize_request).collect()),
        Value::Object(items) => {
            let mut normalized: serde_json::Map<String, Value> = items
                .into_iter()
                .map(|(key, value)| (snake_case(&key), normalize_request(value)))
                .collect();
            if let Some(request) = normalized.remove("request") {
                if let Value::Object(envelope) = request {
                    if envelope.contains_key("schema_version")
                        && envelope.contains_key("request_id")
                        && envelope.contains_key("command")
                    {
                        Value::Object(envelope)
                    } else {
                        normalized.insert("request".into(), Value::Object(envelope));
                        Value::Object(normalized)
                    }
                } else {
                    normalized.insert("request".into(), request);
                    Value::Object(normalized)
                }
            } else {
                Value::Object(normalized)
            }
        }
        value => value,
    }
}

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
fn engine_rpc(request: Value, sidecar: tauri::State<'_, Mutex<Option<Sidecar>>>) -> Value {
    let request = normalize_request(request);
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
    let mut session = match sidecar.lock() {
        Ok(session) => session,
        Err(_) => {
            return rejected(
                &request,
                "ENGINE_SIDECAR_FAILED",
                "Engine session lock failed",
            )
        }
    };
    let configuration = (python, cache_root);
    if session
        .as_ref()
        .is_some_and(|active| active.configuration != configuration)
    {
        return rejected(
            &request,
            "ENGINE_SIDECAR_CONFIGURATION_CHANGED",
            "Engine configuration changed; restart the desktop application",
        );
    }
    if session.is_none() {
        *session = match Sidecar::start(configuration) {
            Ok(active) => Some(active),
            Err(_) => {
                return rejected(
                    &request,
                    "ENGINE_SIDECAR_START_FAILED",
                    "could not start Engine sidecar",
                )
            }
        };
    }
    match session
        .as_mut()
        .expect("session started")
        .exchange(&request, &request_bytes)
    {
        Ok(response) => response,
        Err(code) => {
            *session = None;
            rejected(
                &request,
                code,
                "Engine session ended; request was not replayed",
            )
        }
    }
}

fn main() {
    tauri::Builder::default()
        .manage(Mutex::<Option<Sidecar>>::new(None))
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::Destroyed) {
                let session = window.state::<Mutex<Option<Sidecar>>>();
                if let Ok(mut active) = session.lock() {
                    *active = None;
                };
            }
        })
        .invoke_handler(tauri::generate_handler![engine_rpc])
        .run(tauri::generate_context!())
        .expect("error while running ArchCanvas desktop");
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;

    #[test]
    fn repeated_requests_share_a_process_and_disconnected_requests_are_not_replayed() {
        let mut command = Command::new("sh");
        command.arg("-c").arg(
            "count=0; while IFS= read -r line; do count=$((count+1)); printf '{\"request_id\":\"engine-request:test\",\"count\":%s}\\n' \"$count\"; done",
        );
        let mut sidecar = Sidecar::spawn(&mut command, ("test".into(), "test".into())).unwrap();
        let request = json!({ "request_id": "engine-request:test" });
        let bytes = serde_json::to_vec(&request).unwrap();
        assert_eq!(sidecar.exchange(&request, &bytes).unwrap()["count"], 1);
        assert_eq!(sidecar.exchange(&request, &bytes).unwrap()["count"], 2);

        sidecar.child.kill().unwrap();
        sidecar.child.wait().unwrap();
        assert!(sidecar.exchange(&request, &bytes).is_err());
    }

    #[test]
    fn mismatched_response_id_is_rejected() {
        let mut command = Command::new("sh");
        command
            .arg("-c")
            .arg("IFS= read -r line; printf '{\"request_id\":\"engine-request:other\"}\\n'");
        let mut sidecar = Sidecar::spawn(&mut command, ("test".into(), "test".into())).unwrap();
        let request = json!({ "request_id": "engine-request:test" });
        assert_eq!(
            sidecar.exchange(&request, &serde_json::to_vec(&request).unwrap()),
            Err("ENGINE_SIDECAR_INVALID_RESPONSE"),
        );
    }
}
