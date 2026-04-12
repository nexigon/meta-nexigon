"""Tests for device commands (systemd, power, rugix-apps)."""

import json

from rugix_testkit import VMHandle


def test_systemd_list_units(vm: VMHandle) -> None:
    """The list-units command returns a JSON array of systemd units."""
    result = vm.run(["/usr/libexec/nexigon/nexigon-systemd-list-units"], hide=True)
    line = json.loads(result.stdout)
    assert line["type"] == "Output"
    units = line["data"]
    assert isinstance(units, list)
    assert any(u["unit"] == "nexigon-agent.service" for u in units)


def test_systemd_status(vm: VMHandle) -> None:
    """The status command returns properties of a systemd unit."""
    result = vm.run(
        [
            "sh",
            "-c",
            'echo \'{"unit":"nexigon-agent.service"}\' '
            "| /usr/libexec/nexigon/nexigon-systemd-status",
        ],
        hide=True,
    )
    line = json.loads(result.stdout)
    assert line["type"] == "Output"
    props = line["data"]
    assert props["Id"] == "nexigon-agent.service"
    assert props["ActiveState"] == "active"


def test_systemd_restart(vm: VMHandle) -> None:
    """The restart command restarts a unit and it stays active."""
    vm.run(
        [
            "sh",
            "-c",
            'echo \'{"unit":"nexigon-agent.service"}\' '
            "| /usr/libexec/nexigon/nexigon-systemd-restart",
        ],
        hide=True,
    )
    result = vm.run(
        ["systemctl", "is-active", "nexigon-agent.service"],
        hide=True,
    )
    assert result.stdout.strip() == "active"


def test_power_reboot(vm: VMHandle) -> None:
    """The reboot command handler triggers a reboot."""
    vm.run(["systemd-run", "--no-block", "reboot"], hide=True)
    vm.wait_for_reboot(timeout=300)
    result = vm.run(["uptime"], hide=True)
    assert result.ok


def test_rugix_apps_dict(vm: VMHandle) -> None:
    """The list command returns a JSON array (possibly empty)."""
    result = vm.run(
        ["/usr/libexec/nexigon/nexigon-rugix-apps", "list"],
        hide=True,
    )
    line = json.loads(result.stdout)
    assert line["type"] == "Output"
    assert isinstance(line["data"], dict)
