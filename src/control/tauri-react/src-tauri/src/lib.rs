use std::collections::HashMap;
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Duration;

use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use serde_json::Value;
#[cfg(not(debug_assertions))]
use tauri::path::BaseDirectory;
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_shell::process::{Command, CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tokio::sync::{oneshot, Mutex};
use tokio::time::timeout;

// Sidecar protocol
#[cfg(not(debug_assertions))]
const SIDECAR_RESOURCE_DIRECTORY: &str = "agent-loop-runtime";
const SIDECAR_TIMEOUT: Duration = Duration::from_secs(30);
const RUNTIME_SNAPSHOT_METHOD: &str = "runtime.snapshot";
const RUNTIME_SNAPSHOT_EVENT: &str = "runtime-snapshot";

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct Message {
    sender: String,
    message: String,
    attachments: Vec<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
struct Inbox {
    messages: Vec<Message>,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
struct Thread {
    messages: Vec<Message>,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
struct RuntimeSnapshot {
    epoch: u64,
    revision: u64,
    status: String,
    inbox: Inbox,
    thread: Thread,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct SendMessageResult {
    accepted: bool,
    snapshot: RuntimeSnapshot,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct ClearRuntimeResult {
    cleared: bool,
    snapshot: RuntimeSnapshot,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct GetRuntimeResult {
    snapshot: RuntimeSnapshot,
}

#[derive(Serialize)]
struct JsonRpcRequest<'a, Params: ?Sized> {
    jsonrpc: &'static str,
    id: u64,
    method: &'static str,
    params: &'a Params,
}

#[derive(Debug, Deserialize)]
struct JsonRpcIncoming {
    jsonrpc: String,
    id: Option<u64>,
    method: Option<String>,
    params: Option<Value>,
    result: Option<Value>,
    error: Option<JsonRpcError>,
}

#[derive(Debug, Deserialize)]
struct JsonRpcError {
    code: i64,
    message: String,
}

#[derive(Debug, Deserialize)]
struct RuntimePingResult {
    ready: bool,
}

#[derive(Serialize)]
struct EmptyParams {}

type PendingResult = Result<Value, String>;
type PendingSender = oneshot::Sender<PendingResult>;
type PendingRequests = Arc<Mutex<HashMap<u64, PendingSender>>>;

// Sidecar lifecycle
fn thread_path(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    app.path()
        .app_data_dir()
        .map(|directory| directory.join("thread.jsonl"))
        .map_err(|error| format!("Unable to resolve runtime storage: {error}"))
}

struct SidecarProcess {
    child: CommandChild,
    pending: PendingRequests,
}

impl SidecarProcess {
    fn spawn(app: &AppHandle) -> Result<Self, String> {
        let command = sidecar_command(app)?;
        let (events, child) = command
            .spawn()
            .map_err(|error| format!("Unable to start the agent runtime: {error}"))?;
        let pending = Arc::new(Mutex::new(HashMap::new()));

        spawn_event_dispatcher(app.clone(), events, Arc::clone(&pending));
        Ok(Self { child, pending })
    }

    async fn send_request<Params>(
        &mut self,
        request_id: u64,
        method: &'static str,
        params: &Params,
    ) -> Result<oneshot::Receiver<PendingResult>, String>
    where
        Params: Serialize + ?Sized,
    {
        let request = JsonRpcRequest {
            jsonrpc: "2.0",
            id: request_id,
            method,
            params,
        };
        let mut payload = serde_json::to_vec(&request)
            .map_err(|error| format!("Unable to encode the message: {error}"))?;
        payload.push(b'\n');

        let (sender, receiver) = oneshot::channel();
        self.pending.lock().await.insert(request_id, sender);
        if let Err(error) = self.child.write(&payload) {
            self.pending.lock().await.remove(&request_id);
            return Err(format!("Unable to contact the agent runtime: {error}"));
        }

        Ok(receiver)
    }

    fn stop(self) {
        if let Err(error) = self.child.kill() {
            eprintln!("Unable to stop agent-loop-sidecar: {error}");
        }
    }
}

fn spawn_event_dispatcher(
    app: AppHandle,
    mut events: tauri::async_runtime::Receiver<CommandEvent>,
    pending: PendingRequests,
) {
    tauri::async_runtime::spawn(async move {
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Stdout(payload) => {
                    if let Err(error) = dispatch_stdout(&app, &pending, &payload).await {
                        fail_pending(&pending, error).await;
                    }
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("agent-loop-sidecar: {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Error(error) => {
                    fail_pending(&pending, format!("The agent runtime failed: {error}")).await;
                }
                CommandEvent::Terminated(status) => {
                    fail_pending(
                        &pending,
                        format!(
                            "The agent runtime stopped unexpectedly (code: {:?}, signal: {:?}).",
                            status.code, status.signal
                        ),
                    )
                    .await;
                    break;
                }
                _ => {}
            }
        }

        fail_pending(
            &pending,
            "The agent runtime connection closed unexpectedly.".to_string(),
        )
        .await;
    });
}

async fn dispatch_stdout(
    app: &AppHandle,
    pending: &PendingRequests,
    payload: &[u8],
) -> Result<(), String> {
    let incoming: JsonRpcIncoming = serde_json::from_slice(payload)
        .map_err(|error| format!("The agent runtime returned invalid data: {error}"))?;

    if incoming.jsonrpc != "2.0" {
        return Err("The agent runtime returned an unexpected response.".to_string());
    }

    if incoming.method.as_deref() == Some(RUNTIME_SNAPSHOT_METHOD) {
        let snapshot: RuntimeSnapshot = serde_json::from_value(
            incoming
                .params
                .ok_or_else(|| "The runtime snapshot was empty.".to_string())?,
        )
        .map_err(|error| format!("The runtime snapshot was invalid: {error}"))?;
        app.emit(RUNTIME_SNAPSHOT_EVENT, snapshot)
            .map_err(|error| format!("Unable to publish the runtime snapshot: {error}"))?;
        return Ok(());
    }

    let request_id = incoming
        .id
        .ok_or_else(|| "The agent runtime returned an unrecognized notification.".to_string())?;
    let sender = pending
        .lock()
        .await
        .remove(&request_id)
        .ok_or_else(|| "The agent runtime returned an unexpected response.".to_string())?;

    let result = if let Some(error) = incoming.error {
        Err(format!(
            "The agent runtime rejected the message ({}): {}",
            error.code, error.message
        ))
    } else {
        incoming
            .result
            .ok_or_else(|| "The agent runtime returned an empty response.".to_string())
    };
    let _ = sender.send(result);
    Ok(())
}

async fn fail_pending(pending: &PendingRequests, error: String) {
    let requests = {
        let mut pending = pending.lock().await;
        pending
            .drain()
            .map(|(_, sender)| sender)
            .collect::<Vec<_>>()
    };

    for sender in requests {
        let _ = sender.send(Err(error.clone()));
    }
}

#[cfg(debug_assertions)]
fn sidecar_command(app: &AppHandle) -> Result<Command, String> {
    let project_root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../..")
        .canonicalize()
        .map_err(|error| format!("Unable to resolve the project root: {error}"))?;
    let python = if cfg!(target_os = "windows") {
        project_root.join("venv/Scripts/python.exe")
    } else {
        project_root.join("venv/bin/python")
    };
    let entry_point = project_root.join("main.py");

    if !python.is_file() {
        return Err(format!(
            "The development Python runtime does not exist: {}",
            python.display()
        ));
    }

    Ok(app
        .shell()
        .command(python)
        .arg(entry_point)
        .env("AGENT_LOOP_THREAD_PATH", thread_path(app)?))
}

#[cfg(not(debug_assertions))]
fn sidecar_command(app: &AppHandle) -> Result<Command, String> {
    let executable_name = if cfg!(target_os = "windows") {
        "agent-loop-sidecar.exe"
    } else {
        "agent-loop-sidecar"
    };
    let executable = app
        .path()
        .resolve(
            Path::new(SIDECAR_RESOURCE_DIRECTORY).join(executable_name),
            BaseDirectory::Resource,
        )
        .map_err(|error| format!("Unable to resolve the agent runtime: {error}"))?;

    if !executable.is_file() {
        return Err(format!(
            "The bundled agent runtime does not exist: {}",
            executable.display()
        ));
    }

    Ok(app
        .shell()
        .command(executable)
        .env("AGENT_LOOP_THREAD_PATH", thread_path(app)?))
}

struct SidecarState {
    process: Mutex<Option<SidecarProcess>>,
    next_request_id: AtomicU64,
}

impl Default for SidecarState {
    fn default() -> Self {
        Self {
            process: Mutex::new(None),
            next_request_id: AtomicU64::new(1),
        }
    }
}

fn next_request_id(state: &SidecarState) -> u64 {
    state.next_request_id.fetch_add(1, Ordering::Relaxed)
}

async fn await_response<ResultType>(
    receiver: oneshot::Receiver<PendingResult>,
) -> Result<ResultType, String>
where
    ResultType: DeserializeOwned,
{
    let value = timeout(SIDECAR_TIMEOUT, receiver)
        .await
        .map_err(|_| "The agent runtime did not respond in time.".to_string())?
        .map_err(|_| "The agent runtime response was dropped.".to_string())??;

    serde_json::from_value(value)
        .map_err(|error| format!("The agent runtime returned invalid data: {error}"))
}

async fn start_sidecar(app: &AppHandle, state: &SidecarState) -> Result<SidecarProcess, String> {
    let mut process = SidecarProcess::spawn(app)?;
    let request_id = next_request_id(state);
    let receiver = match process
        .send_request(request_id, "runtime.ping", &EmptyParams {})
        .await
    {
        Ok(receiver) => receiver,
        Err(error) => {
            process.stop();
            return Err(error);
        }
    };
    let result: RuntimePingResult = match await_response(receiver).await {
        Ok(result) => result,
        Err(error) => {
            process.stop();
            return Err(error);
        }
    };

    if result.ready {
        Ok(process)
    } else {
        process.stop();
        Err("The agent runtime started but did not become ready.".to_string())
    }
}

async fn send_request<Params, ResultType>(
    app: &AppHandle,
    state: &SidecarState,
    method: &'static str,
    params: &Params,
) -> Result<ResultType, String>
where
    Params: Serialize + ?Sized,
    ResultType: DeserializeOwned,
{
    let receiver_result = {
        let mut process = state.process.lock().await;
        if process.is_none() {
            *process = Some(start_sidecar(app, state).await?);
        }

        let request_id = next_request_id(state);
        process
            .as_mut()
            .expect("sidecar process must exist after successful startup")
            .send_request(request_id, method, params)
            .await
    };
    let receiver = match receiver_result {
        Ok(receiver) => receiver,
        Err(error) => {
            let mut process = state.process.lock().await;
            if let Some(unhealthy_process) = process.take() {
                unhealthy_process.stop();
            }
            return Err(error);
        }
    };

    let result = await_response(receiver).await;
    if result.is_err() {
        let mut process = state.process.lock().await;
        if let Some(unhealthy_process) = process.take() {
            unhealthy_process.stop();
        }
    }
    result
}

fn prewarm_sidecar(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        let state = app.state::<SidecarState>();
        let mut process = state.process.lock().await;
        if process.is_some() {
            return;
        }

        match start_sidecar(&app, &state).await {
            Ok(ready_process) => *process = Some(ready_process),
            Err(error) => eprintln!("Unable to prewarm agent-loop-sidecar: {error}"),
        }
    });
}

// Desktop commands
#[tauri::command]
async fn add_message(
    app: AppHandle,
    state: State<'_, SidecarState>,
    message: Message,
) -> Result<SendMessageResult, String> {
    send_request(&app, &state, "message.add", &message).await
}

#[tauri::command]
async fn get_runtime_snapshot(
    app: AppHandle,
    state: State<'_, SidecarState>,
) -> Result<GetRuntimeResult, String> {
    send_request(&app, &state, "runtime.get", &EmptyParams {}).await
}

#[tauri::command]
async fn clear_thread(
    app: AppHandle,
    state: State<'_, SidecarState>,
) -> Result<ClearRuntimeResult, String> {
    send_request(&app, &state, "thread.clear", &EmptyParams {}).await
}

// Application entry point
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState::default())
        .setup(|app| {
            prewarm_sidecar(app.handle().clone());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            add_message,
            get_runtime_snapshot,
            clear_thread
        ])
        .build(tauri::generate_context!())
        .expect("error while building the Tauri application");

    app.run(|app_handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            let state = app_handle.state::<SidecarState>();
            let process = {
                let mut process = state.process.blocking_lock();
                process.take()
            };
            if let Some(process) = process {
                process.stop();
            }
        }
    });
}

// Protocol tests
#[cfg(test)]
mod tests {
    use super::{
        ClearRuntimeResult, GetRuntimeResult, Inbox, Message, RuntimeSnapshot, SendMessageResult,
        Thread,
    };

    fn empty_snapshot() -> RuntimeSnapshot {
        RuntimeSnapshot {
            epoch: 0,
            revision: 0,
            status: "idle".to_string(),
            inbox: Inbox {
                messages: Vec::new(),
            },
            thread: Thread {
                messages: Vec::new(),
            },
        }
    }

    #[test]
    fn deserializes_an_accepted_message_response() {
        let result: SendMessageResult = serde_json::from_str(
            r#"{"accepted":true,"snapshot":{"epoch":0,"revision":1,"status":"idle","inbox":{"messages":[{"sender":"user","message":"Hello","attachments":[]}]},"thread":{"messages":[]}}}"#,
        )
        .expect("response should deserialize");

        assert!(result.accepted);
        assert_eq!(result.snapshot.inbox.messages[0].message, "Hello");
    }

    #[test]
    fn deserializes_a_runtime_snapshot_response() {
        let result: GetRuntimeResult = serde_json::from_str(
            r#"{"snapshot":{"epoch":0,"revision":0,"status":"idle","inbox":{"messages":[]},"thread":{"messages":[]}}}"#,
        )
        .expect("response should deserialize");

        assert_eq!(result.snapshot, empty_snapshot());
    }

    #[test]
    fn deserializes_a_cleared_runtime_response() {
        let result: ClearRuntimeResult = serde_json::from_str(
            r#"{"cleared":true,"snapshot":{"epoch":1,"revision":0,"status":"idle","inbox":{"messages":[]},"thread":{"messages":[]}}}"#,
        )
        .expect("response should deserialize");

        assert!(result.cleared);
        assert_eq!(result.snapshot.epoch, 1);
    }

    #[test]
    fn serializes_runtime_messages_with_the_expected_shape() {
        let message = Message {
            sender: "user".to_string(),
            message: "Hello".to_string(),
            attachments: Vec::new(),
        };

        assert_eq!(
            serde_json::to_value(message).expect("message should serialize"),
            serde_json::json!({
                "sender": "user",
                "message": "Hello",
                "attachments": [],
            })
        );
    }
}
