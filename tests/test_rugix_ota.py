"""Tests specific to Rugix images."""

from __future__ import annotations

from rugix_testkit import VMHandle

import pytest

pytestmark = pytest.mark.rugix


def test_watchdog_noop_when_committed(vm: VMHandle) -> None:
    """Watchdog exits cleanly when the system is already committed."""
    result = vm.run(["/usr/libexec/nexigon/nexigon-rugix-watchdog"], hide=True)
    assert result.ok
    assert "nothing to do" in result.stderr
