"""Shared pytest fixtures for Nexigon integration tests."""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from pathlib import Path

import pytest

from nexigon_hub_sdk import Client
from nexigon_hub_sdk.api_types import devices, projects
from rugix_testkit import Drive, Pflash, VMConfig, VMHandle

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEPLOY_SUBDIR = "tmp/deploy/images/qemux86-64"
IMAGE_NAME = "core-image-minimal-qemux86-64.rootfs.wic"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--test-outputs-dir",
        default="test-outputs",
        help="Directory for test artifacts (default: test-outputs/)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    build = Path(os.environ.get("KAS_BUILD_DIR", str(PROJECT_ROOT / "build")))
    image = build / DEPLOY_SUBDIR / IMAGE_NAME
    if not image.exists():
        skip = pytest.mark.skip(reason=f"QEMU image not built: {image}")
        for item in items:
            if "vm" in item.fixturenames or "device_id" in item.fixturenames:
                item.add_marker(skip)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    if report.when == "call":
        _dump_test_artifacts(item)
    return report


@pytest.fixture(scope="session")
def hub_url() -> str:
    url = os.environ.get("NEXIGON_HUB_URL")
    if not url:
        pytest.skip("NEXIGON_HUB_URL not set")
    return url


@pytest.fixture(scope="session")
def api_token() -> str:
    token = os.environ.get("NEXIGON_API_TOKEN")
    if not token:
        pytest.skip("NEXIGON_API_TOKEN not set")
    return token


@pytest.fixture(scope="session")
def project_id() -> projects.ProjectId:
    pid = os.environ.get("NEXIGON_PROJECT_ID")
    if not pid:
        pytest.skip("NEXIGON_PROJECT_ID not set")
    return projects.ProjectId(pid)


@pytest.fixture(scope="session")
def hub(hub_url: str, api_token: str) -> Generator[Client]:
    with Client(hub_url, token=api_token) as client:
        yield client


@pytest.fixture(scope="session")
def build_dir() -> Path:
    path = Path(os.environ.get("KAS_BUILD_DIR", str(PROJECT_ROOT / "build")))
    assert path.is_dir(), f"Build directory not found: {path}"
    return path


@pytest.fixture
def vm(build_dir: Path, request: pytest.FixtureRequest) -> Generator[VMHandle]:
    deploy = build_dir / DEPLOY_SUBDIR
    config = VMConfig(
        arch="x86_64",
        drives=[
            Drive(
                file=deploy / IMAGE_NAME,
                overlay=True,
                size="16G",
            ),
        ],
        pflash=[
            Pflash(file=deploy / "ovmf.code.qcow2", format="qcow2", readonly=True),
            Pflash(file=deploy / "ovmf.vars.qcow2", format="qcow2"),
        ],
    )
    with VMHandle.start(config) as handle:
        request.node._vm_handle = handle  # type: ignore[attr-defined]
        yield handle


@pytest.fixture
def device_id(vm: VMHandle) -> devices.DeviceId:
    """Ask the agent running on the VM for its device ID."""
    result = vm.run(["nexigon-agent", "device", "id"], hide=True)
    device_id = devices.DeviceId(result.stdout.strip())
    logger.info("VM device ID: %s", device_id)
    return device_id


def _dump_test_artifacts(item: pytest.Item) -> None:
    vm_handle: VMHandle | None = getattr(item, "_vm_handle", None)
    if vm_handle is None:
        return

    outputs_dir = Path(item.config.getoption("--test-outputs-dir"))
    safe_name = item.nodeid.replace("::", "--").replace("/", "--")
    artifact_dir = outputs_dir / safe_name
    artifact_dir.mkdir(parents=True, exist_ok=True)

    serial = vm_handle.serial_output
    if serial:
        (artifact_dir / "serial.log").write_text(serial)

    history = vm_handle.command_history
    if history:
        (artifact_dir / "commands.log").write_text(
            "\n\n".join(str(cmd) for cmd in history) + "\n"
        )
