"""Tests for device registration with Nexigon Hub."""

from nexigon_hub_sdk import Client
from nexigon_hub_sdk.api_types import devices, projects


def test_device_registers(device_id: devices.DeviceId) -> None:
    """Verify that the device registers with the Hub after boot."""
    assert device_id, "Expected a device ID"


def test_device_is_connected(
    hub: Client,
    project_id: projects.ProjectId,
    device_id: devices.DeviceId,
) -> None:
    """Verify that the registered device has an active connection."""
    result = hub.execute(projects.QueryProjectDevicesAction(project_id=project_id))
    device = next(d for d in result.devices if d.device_id == device_id)
    assert device.is_connected
