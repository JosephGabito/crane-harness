#!/usr/bin/env bash

set -euo pipefail


# Project paths
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP_ROOT="${PROJECT_ROOT}/src/control/tauri-react"


# Rust environment
if [[ -f "${HOME}/.cargo/env" ]]; then
    # rustup installs Cargo here, but editor terminals may not load it.
    source "${HOME}/.cargo/env"
fi

if ! command -v cargo >/dev/null 2>&1; then
    echo "Agent Loop requires the Rust toolchain." >&2
    echo "Install it from https://rustup.rs, restart your terminal, and try again." >&2
    exit 1
fi


# Desktop entry point
cd "${DESKTOP_ROOT}"
exec npm run tauri dev -- "$@"
