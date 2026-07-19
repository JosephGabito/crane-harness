"""Build the Python sidecar runtime bundled as a Tauri resource."""

import shutil
import subprocess
import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_ROOT = PROJECT_ROOT / "build" / "pyinstaller"
TAURI_RUNTIME = (
    PROJECT_ROOT
    / "src"
    / "control"
    / "tauri-react"
    / "src-tauri"
    / "resources"
    / "agent-loop-sidecar"
)


# Runtime staging
def stage_runtime(
    source: Path,
    destination: Path,
    executable_name: str,
) -> None:
    """Replace the staged runtime with one complete PyInstaller directory."""
    executable = source / executable_name
    if not executable.is_file():
        raise FileNotFoundError(
            f"PyInstaller did not create the sidecar executable: {executable}"
        )

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    (destination / executable_name).chmod(0o755)
    (destination / ".gitkeep").touch()


# Sidecar build
def main() -> None:
    """Build and stage the complete sidecar runtime directory."""
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    executable_name = (
        "agent-loop-sidecar.exe" if sys.platform == "win32" else "agent-loop-sidecar"
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--onedir",
            "--paths",
            str(PROJECT_ROOT / "src"),
            "--name",
            "agent-loop-sidecar",
            "--specpath",
            str(BUILD_ROOT),
            "--workpath",
            str(BUILD_ROOT / "work"),
            "--distpath",
            str(BUILD_ROOT / "dist"),
            str(PROJECT_ROOT / "main.py"),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )

    source = BUILD_ROOT / "dist" / "agent-loop-sidecar"
    stage_runtime(source, TAURI_RUNTIME, executable_name)
    print(TAURI_RUNTIME)


if __name__ == "__main__":
    main()
