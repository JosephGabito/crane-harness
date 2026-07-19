"""Tests for staging the distributable Python runtime."""

from pathlib import Path

import pytest
from scripts.build_sidecar import stage_runtime


# Runtime staging
def test_stage_runtime_replaces_stale_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    executable = source / "agent-loop-sidecar"
    executable.write_text("runtime")
    (source / "_internal").mkdir()
    (source / "_internal" / "library").write_text("dependency")

    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "stale").write_text("old")

    stage_runtime(source, destination, executable.name)

    assert not (destination / "stale").exists()
    assert (destination / executable.name).read_text() == "runtime"
    assert (destination / "_internal" / "library").read_text() == "dependency"


def test_stage_runtime_requires_the_executable(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(FileNotFoundError):
        stage_runtime(
            source,
            tmp_path / "destination",
            "agent-loop-sidecar",
        )
