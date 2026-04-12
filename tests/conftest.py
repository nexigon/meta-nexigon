"""Shared pytest fixtures for Nexigon integration tests."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import shlex
import uuid
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest

from nexigon_hub_sdk import Client
from nexigon_hub_sdk.api_types import devices, digest, projects, repositories
from rugix_testkit import Drive, Pflash, VMConfig, VMHandle

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEPLOY_SUBDIR = "tmp/deploy/images/qemux86-64"
IMAGE_NAME = "core-image-minimal-qemux86-64.rootfs.wic"
BUNDLE_NAME = "core-image-minimal-qemux86-64.rootfs.rugixb"


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
            if "vm" in getattr(item, "fixturenames", ()) or "device_id" in getattr(
                item, "fixturenames", ()
            ):
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
        request.node._vm_handle = handle
        yield handle


@pytest.fixture
def device_id(vm: VMHandle) -> devices.DeviceId:
    """Ask the agent running on the VM for its device ID."""
    result = vm.run(["nexigon-agent", "device", "id"], hide=True)
    device_id = devices.DeviceId(result.stdout.strip())
    logger.info("VM device ID: %s", device_id)
    return device_id


@dataclasses.dataclass
class OtaTestEnv:
    """State created by the ``ota_test_env`` fixture."""

    test_id: str
    repo_name: str
    package_name: str
    repository_id: repositories.RepositoryId
    package_id: repositories.PackageId
    image_id: str
    v1_version_id: repositories.PackageVersionId
    _version_ids: list[repositories.PackageVersionId]
    _hub: Client
    _build_dir: Path

    @property
    def v1(self) -> str:
        return f"{self.test_id}-v1"

    def configure_vm(self, vm: VMHandle, version: str) -> None:
        """Write the OTA config and IMAGE_VERSION onto the VM."""
        config = json.dumps(
            {"path": f"{self.repo_name}/{self.package_name}/{self.test_id}"}
        )
        vm.run(
            ["sh", "-c", f"echo {shlex.quote(config)} > /etc/nexigon-rugix-ota.json"],
            hide=True,
        )
        vm.run(
            [
                "sed",
                "-i",
                f"s/^IMAGE_VERSION=.*/IMAGE_VERSION={version}/",
                "/etc/os-release",
            ],
            hide=True,
        )

    def publish_v2(self, bundle_content: bytes | None = None) -> str:
        """Create v2 with a rugix bundle and reassign the channel tag.

        If *bundle_content* is given it is uploaded as-is (useful for testing
        corrupt bundles).  Otherwise the real built bundle is used.
        """
        v2 = f"{self.test_id}-v2"
        bundle_path = self._build_dir / DEPLOY_SUBDIR / BUNDLE_NAME
        bundle_hash = (
            (self._build_dir / DEPLOY_SUBDIR / f"{BUNDLE_NAME}.hash")
            .read_text()
            .strip()
        )

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
            repositories.IssueAssetUploadUrlAction(
                asset_id=asset_output.asset_id,
            )
        )
        httpx.put(
            upload_url.url,
            content=bundle_data,
            timeout=httpx.Timeout(300),
        ).raise_for_status()

        version_output = self._hub.execute(
            repositories.CreatePackageVersionAction(
                package_id=self.package_id,
                tags=[
                    repositories.AddTagItem(tag=self.test_id, reassign=True),
                    repositories.AddTagItem(tag=v2),
                ],
            )
        )
        self._version_ids.append(version_output.version_id)

        self._hub.execute(
            repositories.AddPackageVersionAssetAction(
                version_id=version_output.version_id,
                asset_id=asset_output.asset_id,
                filename=f"{self.image_id}.rugixb",
                metadata={
                    "version": v2,
                    "rugix": {"bundleHash": bundle_hash},
                },
            )
        )
        logger.info(
            "OTA v2 %s published (version_id=%s)", v2, version_output.version_id
        )
        return v2


@pytest.fixture
def ota_test_env(hub: Client, vm: VMHandle, build_dir: Path) -> Generator[OtaTestEnv]:
    """Set up an isolated OTA test environment.

    Creates a ``test-<id>`` channel tag, a v1 version tagged with both
    ``test-<id>`` and ``test-<id>-v1``, rewrites the VM's OTA config to
    point at the channel tag, and sets ``IMAGE_VERSION`` to v1.
    """
    test_id = f"test-{uuid.uuid4().hex[:12]}"

    ota_config = json.loads(
        vm.run(["cat", "/etc/nexigon-rugix-ota.json"], hide=True).stdout
    )
    repo_name, package_name, _tag = ota_config["path"].split("/")

    image_id = vm.run(
        ["sh", "-c", ". /etc/os-release && echo $IMAGE_ID"], hide=True
    ).stdout.strip()

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
        )
    )
    version_ids: list[repositories.PackageVersionId] = [version_output.version_id]

    env = OtaTestEnv(
        test_id=test_id,
        repo_name=repo_name,
        package_name=package_name,
        repository_id=resolved.repository_id,
        package_id=resolved.package_id,
        image_id=image_id,
        v1_version_id=version_output.version_id,
        _version_ids=version_ids,
        _hub=hub,
        _build_dir=build_dir,
    )
    env.configure_vm(vm, v1)
    logger.info("OTA env %s ready (v1=%s)", test_id, version_output.version_id)

    yield env

    for vid in version_ids:
        hub.execute(repositories.DeletePackageVersionAction(version_id=vid))


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
