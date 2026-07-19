"""Tests for the root sidecar entry point."""

import sys
from collections.abc import Callable
from types import ModuleType

import main as root_entry_point
import pytest


# Test double
class SidecarEntryPointModule(ModuleType):
    """Represent the lazily imported sidecar entry-point module."""

    def __init__(self, start: Callable[[], None]) -> None:
        super().__init__("control.sidecar.main")
        self.main = start


# Entry-point behavior
def test_root_entry_point_starts_sidecar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = False

    def record_start() -> None:
        nonlocal started
        started = True

    sidecar_entry_point = SidecarEntryPointModule(record_start)
    monkeypatch.setitem(sys.modules, "control.sidecar.main", sidecar_entry_point)

    root_entry_point.main()

    assert started is True
