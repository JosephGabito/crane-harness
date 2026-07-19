# Crane Harness desktop

This folder contains the desktop control surface for Crane Harness.

The interface shows one complete runtime snapshot:

- messages waiting in the Inbox;
- messages saved in the Thread;
- whether the loop is idle or running; and
- the current epoch and revision.

See the [project README](../../../README.md) for the product idea, full setup,
and architecture.

## Parts

```text
React
  renders state and sends commands
    |
    v
Tauri and Rust
  own the desktop window and Python process
    |
    v
Python sidecar
  runs Crane application use cases
```

React never starts a model or writes the journal directly.

## Install

Install the Python environment from the repository root first:

```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.dev.txt
```

Then install the desktop dependencies:

```sh
cd src/control/tauri-react
npm install
```

Install the stable Rust toolchain before running Tauri.

## Run the complete desktop application

From the repository root:

```sh
./bin/start.sh
```

This mode uses:

- the React interface;
- the Tauri desktop window;
- the Rust sidecar lifecycle; and
- the real Python runtime with filesystem persistence.

Use this mode to test the complete application.

## Run only React

```sh
npm run dev
```

This mode runs in a normal browser. It uses an in-memory development loop and
a fake reply. It does not start Tauri, Rust, or Python.

Use this mode for quick visual changes.

## Useful commands

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the React development server. |
| `npm test` | Run the React tests once. |
| `npm run build` | Type-check and build the React application. |
| `npm run sidecar:build` | Package Python for the desktop application. |
| `npm run tauri dev` | Start the complete desktop application. |
| `npm run tauri build` | Build a platform-native desktop package. |

## Development behavior

The fake model waits five seconds before replying. While it waits, send more
messages to test the Inbox.

Enter `/clear` in the composer to clear the Inbox and Thread.

React files reload in the development window. Tauri watches the Python source
folders and the root `main.py` entry point.

## Security boundary

The webview has no shell permission.

Rust owns the Python process and checks it with `runtime.ping`. Rust matches
each JSON-RPC response to its request. If the sidecar stops, times out, or
returns invalid data, Rust fails pending requests and starts a new process on
the next command.

Release builds package Python as a PyInstaller directory. The runtime is built
once and bundled with the desktop application.
