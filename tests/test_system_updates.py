"""Tests for the system update integration of the agent.

The tests run against both Rugix and RAUC images. The ``ota_test_env`` fixture
detects the enabled integration from the agent configuration.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any

from nexigon_hub_sdk import Client
from nexigon_hub_sdk.api_types import devices
from rugix_testkit import VMHandle

import pytest

from conftest import OtaTestEnv

CAPABILITIES = {"window", "retry", "checkpoints", "spread", "hold"}


def test_no_update_available(
    hub: Client, vm: VMHandle, device_id: devices.DeviceId, ota_test_env: OtaTestEnv
) -> None:
    """The agent reports 'completed' when the device already runs the target."""
    ota_test_env.check(vm)
    status = ota_test_env.wait_for_status(
        lambda s: (
            s.get("state") == "completed" and s.get("currentVersion") == ota_test_env.v1
        )
    )
    assert status["currentVersionId"] == ota_test_env.v1_version_id
    assert set(status["capabilities"]) == CAPABILITIES
    updater = status["updater"]
    assert updater["name"] == ota_test_env.engine
    assert updater["version"]
    assert updater["primarySlot"] == updater["bootedSlot"]
    slots = {slot["name"]: slot for slot in updater["slots"]}
    assert len(slots) == 2
    assert slots[updater["bootedSlot"]]["state"] == "booted"

    manifest = hub.execute(
        devices.GetDevicePropertyAction(
            device_id=device_id, name="dev.nexigon.commands"
        )
    )
    assert manifest.result == "Found"
    assert "nexigon.ota.check" in str(manifest.value)


# Installing and rebooting into a bundle can take several minutes.
@pytest.mark.timeout(1500)
def test_update_install(vm: VMHandle, ota_test_env: OtaTestEnv) -> None:
    """The agent installs a new version, reboots, and reports completion."""
    booted = ota_test_env.wait_for_status(
        lambda s: bool(s.get("updater", {}).get("bootedSlot"))
    )["updater"]["bootedSlot"]
    v2 = ota_test_env.publish_v2()
    ota_test_env.check(vm)
    vm.wait_for_reboot(timeout=900)

    status = ota_test_env.wait_for_status(
        lambda s: s.get("state") == "completed" and s.get("currentVersionId") == v2
    )
    assert status["currentVersion"] == ota_test_env.built_version
    assert status["failureCount"] == 0
    # The device runs the other slot and boots it again after the commit.
    updater = status["updater"]
    assert updater["bootedSlot"] != booted
    assert updater["primarySlot"] == updater["bootedSlot"]
    assert not updater.get("awaitingCommit")


def test_unresolvable_path(vm: VMHandle, ota_test_env: OtaTestEnv) -> None:
    """A path to a missing version yields 'failed' with an explanation."""
    ota_test_env.set_config(path=ota_test_env.path("nonexistent"))
    ota_test_env.check(vm)
    status = ota_test_env.wait_for_status(lambda s: s.get("state") == "failed")
    assert "does not exist" in status["lastError"]


@pytest.mark.allow_agent_warnings
def test_broken_bundle_retry_limit(vm: VMHandle, ota_test_env: OtaTestEnv) -> None:
    """A failed installation counts as an attempt and stops at the retry limit."""
    v2 = ota_test_env.publish_v2(bundle_content=b"not a bundle")
    ota_test_env.set_config(retry={"maxAttempts": 1})
    ota_test_env.check(vm)
    status = ota_test_env.wait_for_status(
        lambda s: s.get("state") == "failed" and s.get("failureCount") == 1
    )
    assert status["nextVersionId"] == v2
    assert status["currentVersion"] == ota_test_env.v1
    assert "nextAttemptAt" not in status
    assert status["lastError"]


def _window_elsewhere() -> dict[str, Any]:
    """Maintenance window that is closed for the next six hours."""
    now = datetime.datetime.now(datetime.UTC)
    start = (now + datetime.timedelta(hours=6)).strftime("%H:%M")
    end = (now + datetime.timedelta(hours=7)).strftime("%H:%M")
    return {"ranges": [{"start": start, "end": end}]}


@pytest.mark.parametrize(
    ("code", "config"),
    [
        ("hold", lambda: {"hold": True}),
        ("window", lambda: {"window": _window_elsewhere()}),
        ("spread", lambda: {"spread": {"percentage": 0}}),
    ],
)
def test_blocked(
    vm: VMHandle,
    ota_test_env: OtaTestEnv,
    code: str,
    config: Callable[[], dict[str, Any]],
) -> None:
    """Holds, closed windows, and spreads keep the device on its version."""
    v2 = ota_test_env.publish_v2()
    ota_test_env.set_config(**config())
    ota_test_env.check(vm)
    status = ota_test_env.wait_for_status(lambda s: s.get("state") == "blocked")
    assert status["blocked"]["code"] == code
    assert status["currentVersion"] == ota_test_env.v1
    assert status["nextVersionId"] == v2


@pytest.mark.timeout(1500)
@pytest.mark.allow_agent_warnings
def test_checkpoint_path(vm: VMHandle, ota_test_env: OtaTestEnv) -> None:
    """The device installs the base of the target before the target itself."""
    checkpoint = ota_test_env.publish(tags=[ota_test_env.built_version])
    target = ota_test_env.publish(
        tags=[ota_test_env.test_id],
        bundle_content=b"not a bundle",
        image_version=f"{ota_test_env.test_id}-v3",
        base=checkpoint,
    )
    ota_test_env.set_config(retry={"maxAttempts": 1})
    ota_test_env.check(vm)
    vm.wait_for_reboot(timeout=900)

    # The broken target fails after the device has reached the checkpoint.
    status = ota_test_env.wait_for_status(
        lambda s: s.get("state") == "failed" and s.get("currentVersionId") == checkpoint
    )
    assert status["nextVersionId"] == target
    assert status["targetVersionId"] == target
    assert status["failureCount"] == 1


@pytest.mark.allow_agent_warnings
def test_rollback_detection(
    hub: Client, vm: VMHandle, device_id: devices.DeviceId, ota_test_env: OtaTestEnv
) -> None:
    """A device that boots its old version after an installation reports a rollback.

    The test simulates the rollback with the status the agent reports before
    rebooting into an installed version.
    """
    v2 = ota_test_env.publish_v2()
    vm.run(["systemctl", "stop", "nexigon-agent"], hide=True)
    config = hub.execute(
        devices.GetDevicePropertyAction(
            device_id=device_id, name="dev.nexigon.ota.config"
        )
    )
    assert config.result == "Found"
    hub.execute(
        devices.SetDevicePropertyAction(
            device_id=device_id,
            name="dev.nexigon.ota.status",
            value={
                "state": "rebooting",
                "configVersion": config.version,
                "currentVersion": ota_test_env.v1,
                "targetVersionId": v2,
                "nextVersionId": v2,
                "failureCount": 0,
            },
        )
    )
    vm.run(["systemctl", "start", "nexigon-agent"], hide=True)

    # The first retry waits for the initial delay.
    status = ota_test_env.wait_for_status(
        lambda s: s.get("state") == "failed" and s.get("failureCount") == 1
    )
    assert "rolled back" in status["lastError"]
    assert "nextAttemptAt" in status
    assert status["currentVersion"] == ota_test_env.v1

    # Checks while waiting for the retry keep reporting the error.
    version = _status_version(hub, device_id)
    ota_test_env.check(vm)
    ota_test_env.wait_for_status(lambda _: _status_version(hub, device_id) > version)
    status = ota_test_env.status()
    assert status["state"] == "failed"
    assert "rolled back" in status["lastError"]
    assert status["failureCount"] == 1


def _status_version(hub: Client, device_id: devices.DeviceId) -> int:
    prop = hub.execute(
        devices.GetDevicePropertyAction(
            device_id=device_id, name="dev.nexigon.ota.status"
        )
    )
    assert prop.result == "Found"
    return prop.version
