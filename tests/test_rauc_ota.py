"""Tests for the RAUC OTA update via nexigon-rauc-ota."""

from __future__ import annotations

import json
import logging
import shlex
from typing import Any

import pytest

from nexigon_hub_sdk import Client
from nexigon_hub_sdk.api_types import devices
from rugix_testkit import VMHandle

from conftest import OtaTestEnv

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.rauc


def _disable_ota_timer(vm: VMHandle) -> None:
    vm.run(
        ["systemctl", "disable", "--now", "nexigon-rauc-ota.timer"],
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


def test_rauc_ota_no_update_available(
    hub: Client,
    vm: VMHandle,
    device_id: devices.DeviceId,
    ota_test_env: OtaTestEnv,
) -> None:
    """OTA script reports 'completed' when the device already runs the latest version."""
    _disable_ota_timer(vm)

    result = vm.run(["/usr/bin/nexigon-rauc-ota"], hide=True)
    assert "no updates available" in result.stderr

    status = _get_ota_status(hub, device_id)
    assert status["state"] == "completed"
    assert status["currentVersion"] == ota_test_env.v1


def test_rauc_ota_update_install(
    hub: Client,
    vm: VMHandle,
    device_id: devices.DeviceId,
    ota_test_env: OtaTestEnv,
) -> None:
    """OTA script installs an update and after reboot detects completion."""
    _disable_ota_timer(vm)

    v2 = ota_test_env.publish_v2()

    vm.run(
        [
            "systemd-run",
            "--no-block",
            "--unit=ota-test-run",
            "/usr/bin/nexigon-rauc-ota",
        ],
        hide=True,
    )
    vm.wait_for_reboot(timeout=600)

    _disable_ota_timer(vm)
    ota_test_env.configure_vm(vm, v2)

    # Wait for the agent to reconnect after reboot.
    vm.run(["nexigon-agent", "device", "id"], hide=True)

    result = vm.run(["/usr/bin/nexigon-rauc-ota"], hide=True)
    logger.info("OTA commit run stderr:\n%s", result.stderr)

    status = _get_ota_status(hub, device_id)
    assert status["state"] == "completed", f"OTA status: {status}"
    assert status["currentVersion"] == v2


def test_rauc_ota_unresolvable_path(
    hub: Client,
    vm: VMHandle,
    device_id: devices.DeviceId,
    ota_test_env: OtaTestEnv,
) -> None:
    """OTA script reports failure when the configured version path cannot be resolved."""
    _disable_ota_timer(vm)

    bogus_config = json.dumps({"path": "nonexistent/repo/tag"})
    vm.run(
        ["sh", "-c", f"echo {shlex.quote(bogus_config)} > /etc/nexigon-rauc-ota.json"],
        hide=True,
    )

    result = vm.run(["/usr/bin/nexigon-rauc-ota"], check=False, hide=True)
    assert result.return_code != 0

    status = _get_ota_status(hub, device_id)
    assert status["state"] == "failed"
    assert "unable to resolve" in status["lastError"]
