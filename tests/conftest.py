"""Shared pytest fixtures for Nexigon integration tests."""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import os
import time
import tomllib
import urllib.parse
import uuid
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import httpx
import pytest

from nexigon_hub_sdk import Client
from nexigon_hub_sdk.api_types import (
    devices,
    digest,
    json as json_types,
    projects,
    repositories,
)
from rugix_testkit import Drive, Pflash, VMConfig, VMHandle
from rugix_testkit.qemu.config import find_free_port

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

IMAGE_NAME = "core-image-minimal-qemux86-64.rootfs.wic"
IMAGE_BASENAME = "core-image-minimal-qemux86-64.rootfs"

DEPLOY_SUBDIR = "tmp/deploy/images/qemux86-64"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--test-outputs-dir",
        default="test-outputs",
        help="Directory for test artifacts (default: test-outputs/)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "rugix: tests requiring a Rugix image")
    config.addinivalue_line("markers", "rauc: tests requiring a RAUC image")
    config.addinivalue_line(
        "markers", "allow_agent_warnings: tests expecting agent warnings"
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    build = Path(os.environ.get("KAS_BUILD_DIR", str(PROJECT_ROOT / "build")))
    deploy = build / DEPLOY_SUBDIR

    has_rugix = bool(list(deploy.glob("*.rugixb")))
    has_rauc = bool(list(deploy.glob("*.raucb")))
    has_image = (deploy / IMAGE_NAME).exists()

    for item in items:
        if not has_image and ("vm" in getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.skip(reason="QEMU image not built"))
        elif item.get_closest_marker("rugix") and not has_rugix:
            item.add_marker(pytest.mark.skip(reason="Rugix image not built"))
        elif item.get_closest_marker("rauc") and not has_rauc:
            item.add_marker(pytest.mark.skip(reason="RAUC image not built"))


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
    token = os.environ.get("TESTS_API_TOKEN")
    if not token:
        pytest.skip("TESTS_API_TOKEN not set")
    return token


@pytest.fixture(scope="session")
def project_id() -> projects.ProjectId:
    pid = os.environ.get("TESTS_PROJECT_ID")
    if not pid:
        pytest.skip("TESTS_PROJECT_ID not set")
    return projects.ProjectId(pid)


@pytest.fixture(scope="session")
def hub(hub_url: str, api_token: str) -> Generator[Client]:
    with Client(
        hub_url,
        token=api_token,
        dangerous_allow_plaintext=hub_url.startswith("http://"),
    ) as client:
        yield client


@pytest.fixture(scope="session")
def build_dir() -> Path:
    path = Path(os.environ.get("KAS_BUILD_DIR", str(PROJECT_ROOT / "build")))
    assert path.is_dir(), f"Build directory not found: {path}"
    return path


@pytest.fixture
def deploy_dir(build_dir: Path) -> Path:
    """Deploy directory for the QEMU image."""
    path = build_dir / DEPLOY_SUBDIR
    if not (path / IMAGE_NAME).exists():
        pytest.skip(f"QEMU image not built: {path / IMAGE_NAME}")
    return path


@pytest.fixture
def ports() -> tuple[int, int]:
    """Host ports forwarded to the SSH server and the provisioning endpoint."""
    ssh_port = find_free_port()
    while (pairing_port := find_free_port()) == ssh_port:
        pass
    return ssh_port, pairing_port


@pytest.fixture
def vm(
    deploy_dir: Path, ports: tuple[int, int], request: pytest.FixtureRequest
) -> Generator[VMHandle]:
    ovmf_dir = os.environ.get("OVMF_DIR")
    if not ovmf_dir:
        pytest.fail("OVMF_DIR is not set. Run tests with `mise run test`.")
    firmware_dir = Path(ovmf_dir) / "FV"
    ssh_port, pairing_port = ports
    config = VMConfig(
        arch="x86_64",
        ssh_port=ssh_port,
        net=(
            "user,model=virtio-net-pci"
            f",hostfwd=tcp::{ssh_port}-:22,hostfwd=tcp::{pairing_port}-:6947"
        ),
        drives=[
            Drive(
                file=deploy_dir / IMAGE_NAME,
                overlay=True,
                size="16G",
            ),
        ],
        pflash=[
            Pflash(file=firmware_dir / "OVMF_CODE.fd", format="raw", readonly=True),
            Pflash(file=firmware_dir / "OVMF_VARS.fd", format="raw"),
        ],
    )
    with VMHandle.start(config) as handle:
        request.node._vm_handle = handle
        yield handle
        if not request.node.get_closest_marker("allow_agent_warnings"):
            _assert_no_agent_warnings(handle)


def _assert_no_agent_warnings(vm: VMHandle) -> None:
    """Fail the test if the nexigon-agent journal contains warning-or-higher entries."""
    result = vm.run(
        ["journalctl", "-u", "nexigon-agent", "-p", "warning", "--no-pager", "-q"],
        check=False,
        hide=True,
    )
    # Local test Hubs without TLS make the agent warn about plaintext connections.
    output = "\n".join(
        line
        for line in result.stdout.strip().splitlines()
        if "explicitly allowed plaintext channel" not in line
    )
    if output:
        pytest.fail(
            "nexigon-agent emitted warning-or-higher journal entries:\n" + output
        )


@pytest.fixture
def device_id(
    vm: VMHandle,
    hub: Client,
    hub_url: str,
    project_id: projects.ProjectId,
    ports: tuple[int, int],
) -> devices.DeviceId:
    """Pair the agent running on the VM with the test project and return its ID.

    The images pair through provisioning, so the fixture redeems a pairing key
    through the provisioning endpoint of the agent. Then it asks the agent for
    its device ID. The command connects to Nexigon Hub like the agent service.
    On first boot, both would create the device identity concurrently, so the
    command waits until the service has connected.
    """
    _pair(hub, hub_url, project_id, ports[1])
    deadline = time.monotonic() + 180
    while not vm.run(
        ["sh", "-c", "journalctl -u nexigon-agent --no-pager | grep -q device_id="],
        check=False,
        hide=True,
    ).ok:
        if time.monotonic() > deadline:
            pytest.fail("the agent did not connect to Nexigon Hub")
        time.sleep(2)
    result = vm.run(["nexigon-agent", "device", "id"], hide=True)
    device_id = devices.DeviceId(result.stdout.strip())
    logger.info("VM device ID: %s", device_id)
    return device_id


def _pair(
    hub: Client, hub_url: str, project_id: projects.ProjectId, pairing_port: int
) -> None:
    """Redeem a new pairing key through the provisioning endpoint of the agent."""
    key = hub.execute(
        projects.CreateDevicePairingKeyAction(project_id=project_id)
    ).pairing_key
    # Without a domain, the agent redeems the key at the endpoints of its
    # configuration, which may point to a test Hub without TLS.
    url = urllib.parse.urlsplit(hub_url)
    pairing = f"{url.netloc},{key}" if url.scheme == "https" else key
    deadline = time.monotonic() + 180
    while True:
        try:
            response = httpx.post(
                f"http://127.0.0.1:{pairing_port}/pair", content=pairing, timeout=60
            )
            break
        except httpx.TransportError:
            # The endpoint is not listening yet.
            if time.monotonic() > deadline:
                pytest.fail("the provisioning endpoint of the agent did not respond")
            time.sleep(2)
    if response.is_error:
        pytest.fail(f"pairing the device failed: {response.text}")


@dataclasses.dataclass
class OtaTestEnv:
    """State created by the ``ota_test_env`` fixture.

    The device tracks the ``test-<id>`` channel tag of its package through the
    ``dev.nexigon.ota.config`` property and runs the fake version ``v1``. Bundles
    published by the test install the built image, whose version string is
    ``built_version``.
    """

    test_id: str
    repo_name: str
    package_name: str
    repository_id: repositories.RepositoryId
    package_id: repositories.PackageId
    device_id: devices.DeviceId
    image_id: str
    bundle_ext: str
    built_version: str
    v1_version_id: repositories.PackageVersionId
    _version_ids: list[repositories.PackageVersionId]
    _hub: Client
    _deploy_dir: Path

    @property
    def v1(self) -> str:
        return f"{self.test_id}-v1"

    @property
    def engine(self) -> str:
        """Name of the update engine as reported in the status."""
        return "rugix" if self.bundle_ext == "rugixb" else "rauc"

    def path(self, version: str | None = None) -> str:
        """Version path within the test package, defaulting to the channel tag."""
        return f"{self.repo_name}/{self.package_name}/{version or self.test_id}"

    def set_config(self, **config: json_types.JsonValue) -> None:
        """Set the desired state, tracking the channel tag unless a path is given."""
        self._hub.execute(
            devices.SetDevicePropertyAction(
                device_id=self.device_id,
                name="dev.nexigon.ota.config",
                value={"path": self.path(), **config},
                protected=True,
            )
        )

    def check(self, vm: VMHandle) -> None:
        """Run a check by restarting the agent, which checks right after it starts."""
        vm.run(["systemctl", "restart", "nexigon-agent"], hide=True)

    def status(self) -> dict[str, Any]:
        prop = self._hub.execute(
            devices.GetDevicePropertyAction(
                device_id=self.device_id, name="dev.nexigon.ota.status"
            )
        )
        if prop.result != "Found" or not isinstance(prop.value, dict):
            return {}
        return prop.value

    def wait_for_status(
        self, predicate: Callable[[dict[str, Any]], bool], timeout: float = 180
    ) -> dict[str, Any]:
        """Poll the reported status until it satisfies the predicate."""
        deadline = time.monotonic() + timeout
        status: dict[str, Any] = {}
        while time.monotonic() < deadline:
            try:
                status = self.status()
            except httpx.HTTPError:
                status = {}
            if predicate(status):
                return status
            time.sleep(2)
        raise AssertionError(f"status did not reach the expected state: {status}")

    def publish(
        self,
        *,
        tags: list[str],
        bundle_content: bytes | None = None,
        image_version: str | None = None,
        base: repositories.PackageVersionId | None = None,
    ) -> repositories.PackageVersionId:
        """Publish a version with a bundle, reassigning the given tags.

        Without explicit content, the bundle is the built image, whose version
        string is ``built_version``.
        """
        bundle_path = self._find_bundle()
        bundle_data = (
            bundle_content if bundle_content is not None else bundle_path.read_bytes()
        )
        file_digest = hashlib.sha256(bundle_data).hexdigest()
        asset_output = self._hub.execute(
            repositories.CreateAssetAction(
                repository_id=self.repository_id,
                size=len(bundle_data),
                digest=digest.Digest(f"sha256_{file_digest}"),
            )
        )
        upload_url = self._hub.execute(
            repositories.IssueAssetUploadUrlAction(asset_id=asset_output.asset_id)
        )
        httpx.put(
            upload_url.url, content=bundle_data, timeout=httpx.Timeout(300)
        ).raise_for_status()

        version_output = self._hub.execute(
            repositories.CreatePackageVersionAction(
                package_id=self.package_id,
                tags=[repositories.AddTagItem(tag=tag, reassign=True) for tag in tags],
                metadata={"imageVersion": image_version or self.built_version},
                base_version_id=base,
            )
        )
        self._version_ids.append(version_output.version_id)

        asset_metadata: dict[str, json_types.JsonValue] | None = None
        if self.bundle_ext == "rugixb" and bundle_content is None:
            hash_path = bundle_path.with_suffix(bundle_path.suffix + ".hash")
            asset_metadata = {"rugix": {"bundleHash": hash_path.read_text().strip()}}
        self._hub.execute(
            repositories.AddPackageVersionAssetAction(
                version_id=version_output.version_id,
                asset_id=asset_output.asset_id,
                filename=f"{self.image_id}.{self.bundle_ext}",
                metadata=asset_metadata,
            )
        )
        logger.info("published %s (version_id=%s)", tags, version_output.version_id)
        return version_output.version_id

    def publish_v2(
        self, bundle_content: bytes | None = None
    ) -> repositories.PackageVersionId:
        """Publish the built image as the new version of the channel."""
        return self.publish(
            tags=[self.test_id, self.built_version], bundle_content=bundle_content
        )

    def _find_bundle(self) -> Path:
        """Locate the bundle file in the deploy directory."""
        candidates = list(self._deploy_dir.glob(f"*.{self.bundle_ext}"))
        # Prefer non-timestamped symlinks.
        symlinks = [c for c in candidates if c.is_symlink()]
        result = symlinks[0] if symlinks else candidates[0] if candidates else None
        if result is None:
            raise FileNotFoundError(
                f"No .{self.bundle_ext} bundle found in {self._deploy_dir}"
            )
        return result


def _set_image_version(vm: VMHandle, version: str) -> None:
    vm.run(
        [
            "sed",
            "-i",
            f"s/^IMAGE_VERSION=.*/IMAGE_VERSION={version}/",
            "/etc/os-release",
        ],
        hide=True,
    )


def _os_release_field(vm: VMHandle, name: str) -> str:
    return vm.run(
        ["sh", "-c", f". /etc/os-release && echo ${name}"], hide=True
    ).stdout.strip()


def _detect_ota_variant(vm: VMHandle) -> tuple[str, str]:
    """Return the bundle extension and default path of the enabled integration."""
    config = tomllib.loads(vm.run(["cat", "/etc/nexigon/agent.toml"], hide=True).stdout)
    integrations = config.get("integrations", {})
    for engine, ext in [("rugix", "rugixb"), ("rauc", "raucb")]:
        updates = integrations.get(engine, {}).get("system-updates", {})
        if updates.get("enabled"):
            return ext, updates["path"]
    pytest.fail("no system update integration is enabled in the agent configuration")
    raise AssertionError


@pytest.fixture
def ota_test_env(
    hub: Client, vm: VMHandle, device_id: devices.DeviceId, deploy_dir: Path
) -> Generator[OtaTestEnv]:
    """Set up an isolated OTA test environment.

    Detects the enabled integration, creates a ``test-<id>`` channel tag with a
    version ``v1``, makes the device run ``v1``, and points its desired state at
    the channel tag.
    """
    test_id = f"test-{uuid.uuid4().hex[:12]}"
    bundle_ext, default_path = _detect_ota_variant(vm)
    repo_name, package_name, _tag = default_path.split("/")
    image_id = _os_release_field(vm, "IMAGE_ID")
    built_version = _os_release_field(vm, "IMAGE_VERSION")

    resolved = hub.execute(
        repositories.ResolvePackageByPathAction(
            repository=repo_name, package=package_name
        )
    )
    assert resolved.result == "Found"

    v1 = f"{test_id}-v1"
    version_output = hub.execute(
        repositories.CreatePackageVersionAction(
            package_id=resolved.package_id,
            tags=[
                repositories.AddTagItem(tag=test_id),
                repositories.AddTagItem(tag=v1),
            ],
            metadata={"imageVersion": v1},
        )
    )
    env = OtaTestEnv(
        test_id=test_id,
        repo_name=repo_name,
        package_name=package_name,
        repository_id=resolved.repository_id,
        package_id=resolved.package_id,
        device_id=device_id,
        image_id=image_id,
        bundle_ext=bundle_ext,
        built_version=built_version,
        v1_version_id=version_output.version_id,
        _version_ids=[version_output.version_id],
        _hub=hub,
        _deploy_dir=deploy_dir,
    )
    _set_image_version(vm, v1)
    env.set_config()
    logger.info("OTA env %s ready (v1=%s)", test_id, version_output.version_id)

    yield env

    # Delete dependent versions before their bases.
    for vid in reversed(env._version_ids):
        hub.execute(repositories.DeletePackageVersionAction(version_id=vid))
    hub.execute(
        devices.RemoveDevicePropertyAction(
            device_id=device_id, name="dev.nexigon.ota.config"
        )
    )


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

    journal = vm_handle.run(
        ["journalctl", "-u", "nexigon-agent", "--no-pager", "-o", "short-precise"],
        check=False,
        hide=True,
    ).stdout
    if journal:
        (artifact_dir / "nexigon-agent.journal").write_text(journal)
