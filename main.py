"""Process entry point for the headless agent loop sidecar."""

import sys
from pathlib import Path

# Source bootstrap
SOURCE_ROOT = Path(__file__).resolve().parent / "src"


def main() -> None:
    """Start the JSON-RPC sidecar."""
    source_root = str(SOURCE_ROOT)
    if source_root not in sys.path:
        sys.path.insert(0, source_root)

    from control.sidecar.main import main as run_sidecar

    run_sidecar()


if __name__ == "__main__":
    main()
