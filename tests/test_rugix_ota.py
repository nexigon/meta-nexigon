"""Tests for the Rugix OTA update via nexigon-rugix-ota."""

from __future__ import annotations

import json
import shlex
from typing import Any

from nexigon_hub_sdk import Client
from nexigon_hub_sdk.api_types import devices
from rugix_testkit import RugixCtrl, VMHandle

import pytest

from conftest import OtaTestEnv

pytestmark = pytest.mark.rugix


def _disable_ota_timer(vm: VMHandle) -> None:
    vm.run(
        ["systemctl", "disable", "--now", "nexigon-rugix-ota.timer"],
        check=False,
        hide=True,
    )


def _get_ota_status(hub: Client, device_id: devices.DeviceId) -> dict[str, Any]:
    prop = hub.execute(
        devices.GetDevicePropertyAction(
            device_id=device_id,
            name="dev.nexigon.ota.status",
        )
    )
    assert prop.result == "Found"
    assert isinstance(prop.value, dict)
    return prop.value


def test_ota_no_update_available(
    hub: Client,
    vm: VMHandle,
    device_id: devices.DeviceId,
    ota_test_env: OtaTestEnv,
) -> None:
    """OTA script reports 'completed' when the device already runs the latest version."""
    _disable_ota_timer(vm)

    result = vm.run(["/usr/bin/nexigon-rugix-ota"], hide=True)
    assert "no updates available" in result.stderr

    status = _get_ota_status(hub, device_id)
    assert status["state"] == "completed"
    assert status["currentVersion"] == ota_test_env.v1


def test_ota_update_install(
    hub: Client,
    vm: VMHandle,
    device_id: devices.DeviceId,
    ota_test_env: OtaTestEnv,
) -> None:
    """OTA script installs an update when a new version is available."""
    _disable_ota_timer(vm)

    v2 = ota_test_env.publish_v2()

    vm.run(
        [
            "systemd-run",
            "--no-block",
            "--unit=ota-test-run",
            "/usr/bin/nexigon-rugix-ota",
        ],
        hide=True,
    )
    vm.wait_for_reboot(timeout=600)

    _disable_ota_timer(vm)
    ota_test_env.configure_vm(vm, v2)

    # Wait for the agent to reconnect after reboot.
    vm.run(["nexigon-agent", "device", "id"], hide=True)

    vm.run(["/usr/bin/nexigon-rugix-ota"], hide=True)

    status = _get_ota_status(hub, device_id)
    assert status["state"] == "completed"
    assert status["currentVersion"] == v2


def test_ota_unresolvable_path(
    hub: Client,
    vm: VMHandle,
    device_id: devices.DeviceId,
    ota_test_env: OtaTestEnv,
) -> None:
    """OTA script reports failure when the configured version path cannot be resolved."""
    _disable_ota_timer(vm)

    bogus_config = json.dumps({"path": "nonexistent/repo/tag"})
    vm.run(
        ["sh", "-c", f"echo {shlex.quote(bogus_config)} > /etc/nexigon-rugix-ota.json"],
        hide=True,
    )

    result = vm.run(["/usr/bin/nexigon-rugix-ota"], check=False, hide=True)
    assert result.return_code != 0

    status = _get_ota_status(hub, device_id)
    assert status["state"] == "failed"
    assert "unable to resolve" in status["lastError"]


def test_ota_broken_bundle(
    hub: Client,
    vm: VMHandle,
    device_id: devices.DeviceId,
    ota_test_env: OtaTestEnv,
) -> None:
    """OTA script reports failure when the bundle is corrupt."""
    _disable_ota_timer(vm)

    ota_test_env.publish_v2(bundle_content=b"broken")

    result = vm.run(["/usr/bin/nexigon-rugix-ota"], check=False, hide=True)
    assert result.return_code != 0

    status = _get_ota_status(hub, device_id)
    assert status["state"] == "failed"
    assert "rugix-ctrl update install failed" in status["lastError"]


def test_ota_commit_hook_failure(
    hub: Client,
    vm: VMHandle,
    device_id: devices.DeviceId,
    ota_test_env: OtaTestEnv,
) -> None:
    """A failed pre-commit hook leaves state as 'committing'; rollback marks it failed."""
    _disable_ota_timer(vm)

    ota_test_env.publish_v2()

    # Install and reboot into slot B.
    vm.run(
        [
            "systemd-run",
            "--no-block",
            "--unit=ota-test-run",
            "/usr/bin/nexigon-rugix-ota",
        ],
        hide=True,
    )
    vm.wait_for_reboot(timeout=600)

    _disable_ota_timer(vm)
    ota_test_env.configure_vm(vm, ota_test_env.v1)

    # Install a pre-commit hook that always fails.
    vm.run(
        ["mkdir", "-p", "/etc/rugix/hooks/system-commit/pre-commit"],
        hide=True,
    )
    vm.run(
        [
            "sh",
            "-c",
            'echo "#!/bin/sh\nexit 1" > /etc/rugix/hooks/system-commit/pre-commit/10-reject '
            "&& chmod +x /etc/rugix/hooks/system-commit/pre-commit/10-reject",
        ],
        hide=True,
    )

    # Commit fails — state should stay at "committing", not "completed".
    vm.run(["/usr/bin/nexigon-rugix-ota"], check=False, hide=True)

    status = _get_ota_status(hub, device_id)
    assert status["state"] == "committing"

    # Reboot without commit → rolls back to slot A.
    vm.reboot()

    _disable_ota_timer(vm)
    ota_test_env.configure_vm(vm, ota_test_env.v1)

    # OTA script sees state "committing" with a version mismatch → rollback failure.
    vm.run(["/usr/bin/nexigon-rugix-ota"], check=False, hide=True)

    status = _get_ota_status(hub, device_id)
    assert status["state"] == "failed"
    assert "rolled back" in status["lastError"]


def test_watchdog_noop_when_committed(vm: VMHandle) -> None:
    """Watchdog exits cleanly when the system is already committed."""
    result = vm.run(["/usr/libexec/nexigon/nexigon-rugix-watchdog"], hide=True)
    assert result.ok
    assert "nothing to do" in result.stderr


def test_watchdog_triggers_rollback(vm: VMHandle, ota_test_env: OtaTestEnv) -> None:
    """Watchdog reboots an uncommitted system back to the default slot."""
    _disable_ota_timer(vm)

    ota_test_env.publish_v2()

    vm.run(
        [
            "systemd-run",
            "--no-block",
            "--unit=ota-test-run",
            "/usr/bin/nexigon-rugix-ota",
        ],
        hide=True,
    )
    vm.wait_for_reboot(timeout=600)

    _disable_ota_timer(vm)
    vm.run(
        ["systemctl", "disable", "--now", "nexigon-rugix-watchdog.timer"],
        check=False,
        hide=True,
    )

    rugix = RugixCtrl(vm)
    info = rugix.system_info()
    assert info.active_group != info.default_group

    vm.run(
        [
            "systemd-run",
            "--no-block",
            "--unit=watchdog-test",
            "/usr/libexec/nexigon/nexigon-rugix-watchdog",
        ],
        hide=True,
    )
    vm.wait_for_reboot(timeout=300)

    rugix = RugixCtrl(vm)
    info = rugix.system_info()
    assert info.active_group == info.default_group
