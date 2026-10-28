#!/usr/bin/env python3
"""Exercise collection and upload across the build/publish job boundary."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


class ReleaseArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.log = self.work / "cli.jsonl"
        cli = self.work / "nexigon-cli"
        cli.write_text("""#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with Path(os.environ['CLI_LOG']).open('a') as log:
    log.write(json.dumps(args) + '\\n')
if args[:3] == ['repositories', 'assets', 'upload']:
    assert Path(args[4]).is_file(), args[4]
    print(json.dumps({'assetId': 'asset-' + Path(args[4]).name}))
elif args[:3] == ['repositories', 'versions', 'resolve']:
    print(json.dumps({'result': 'NotFound'}))
elif args[:3] == ['repositories', 'versions', 'create']:
    print(json.dumps({'versionId': 'version-test'}))
elif args[:4] == ['repositories', 'versions', 'assets', 'add']:
    print('{}')
else:
    raise AssertionError(args)
""")
        cli.chmod(0o755)
        self.env = os.environ | {
            "NEXIGON_CLI": str(cli),
            "CLI_LOG": str(self.log),
            "NEXIGON_OTA_REPOSITORY": "test-repository",
            "NEXIGON_OTA_PACKAGE": "test-package",
        }
        (self.work / ".release.env").write_text(
            "BUILD_TAG=build-test\nVERSION=build-test\nVERSION_ID=version-test\n"
        )

    def make_build(self, engine):
        deploy = self.work / "build/tmp/deploy/images/qemux86-64"
        deploy.mkdir(parents=True)
        image_id = f"example-{engine}"
        (deploy / "os-release").write_text(
            f'IMAGE_ID="{image_id}"\nIMAGE_VERSION="build-test"\n'
        )
        filenames = [
            "core-image-minimal-qemux86-64.rootfs.wic.xz",
            "core-image-minimal-qemux86-64.rootfs.spdx.json",
            "core-image-minimal-qemux86-64.rootfs.sbom-cve-check.spdx.json",
            (
                "bundle-qemux86-64.raucb"
                if engine == "rauc"
                else "core-image-minimal-qemux86-64.rootfs.rugixb"
            ),
        ]
        for index, filename in enumerate(filenames):
            target = deploy / f"payload-{index}"
            target.write_text(f"payload-{engine}-{index}")
            (deploy / filename).symlink_to(target.name)
        if engine == "rugix":
            (deploy / (filenames[-1] + ".hash")).write_text("sha512-256:test-hash")
        return deploy

    def collect(self, engine):
        deploy = self.make_build(engine)
        collected = self.work / "collected"
        subprocess.run(
            [str(SCRIPTS / "collect-release.sh"), "qemux86-64", str(collected)],
            cwd=self.work,
            check=True,
            capture_output=True,
        )
        shutil.copyfile(deploy / "os-release", collected / "os-release")
        downloaded = self.work / "downloaded"
        shutil.copytree(collected, downloaded)
        shutil.rmtree(self.work / "build")
        shutil.rmtree(collected)
        return downloaded

    def upload(self, *args):
        return subprocess.run(
            [str(SCRIPTS / "upload-release.sh"), "qemux86-64", *map(str, args)],
            cwd=self.work,
            check=False,
            env=self.env,
            text=True,
            capture_output=True,
        )

    def assert_uploads(self, engine):
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        uploads = [
            call for call in calls if call[:3] == ["repositories", "assets", "upload"]
        ]
        self.assertEqual(len(uploads), 4)
        image_id = f"example-{engine}"
        self.assertEqual(Path(uploads[0][4]).name, f"{image_id}.spdx.json")
        attached = {
            call[6]: json.loads(call[8]) if len(call) > 7 else {}
            for call in calls
            if call[:4] == ["repositories", "versions", "assets", "add"]
        }
        self.assertEqual(
            set(attached),
            {
                f"{image_id}.spdx.json",
                f"{image_id}.vex.spdx.json",
                f"{image_id}.img.wic.xz",
                f"{image_id}.{engine}b",
            },
        )
        for suffix in ("img.wic.xz", f"{engine}b"):
            self.assertEqual(
                attached[f"{image_id}.{suffix}"]["relations"],
                {
                    "sbom": [f"{image_id}.spdx.json"],
                },
            )
        if engine == "rugix":
            self.assertEqual(
                attached[f"{image_id}.rugixb"]["rugix"],
                {
                    "bundleHash": "sha512-256:test-hash",
                },
            )

    def test_prepare_branch_metadata(self):
        """Record the Yocto branch and keep build and channel tags distinct."""
        subprocess.run(
            ["git", "init", "-b", "scarthgap"],
            cwd=self.work,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Release Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--allow-empty",
                "-m",
                "Test release",
            ],
            cwd=self.work,
            check=True,
            capture_output=True,
        )
        for source, channel, expected_branch in [
            ("", None, "scarthgap"),
            ("main", "latest-pr15", "main"),
        ]:
            with self.subTest(source=source):
                self.log.unlink(missing_ok=True)
                env = self.env | {"BUILD_TAG": "build-test", "SOURCE_BRANCH": source}
                env.pop("FLOATING_TAG", None)
                if channel is not None:
                    env["FLOATING_TAG"] = channel
                subprocess.run(
                    [str(SCRIPTS / "prepare-release.sh")],
                    cwd=self.work,
                    env=env,
                    check=True,
                    text=True,
                    capture_output=True,
                )
                calls = [json.loads(line) for line in self.log.read_text().splitlines()]
                create = next(
                    call
                    for call in calls
                    if call[:3] == ["repositories", "versions", "create"]
                )
                metadata = json.loads(create[create.index("--metadata") + 1])
                self.assertEqual(
                    metadata,
                    {
                        "imageVersion": "build-test",
                        "sourceBranch": expected_branch,
                    },
                )
                tags = [
                    create[i + 1] for i, value in enumerate(create) if value == "--tag"
                ]
                self.assertEqual(
                    tags,
                    [
                        "build-test,locked",
                        (channel or "latest-scarthgap") + ",reassign",
                    ],
                )

    def test_transferred_rauc_artifacts(self):
        """Upload RAUC files after the originating build directory is gone."""
        downloaded = self.collect("rauc")
        result = self.upload(downloaded)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_uploads("rauc")
        self.assertTrue(downloaded.is_dir())

    def test_transferred_rugix_artifacts(self):
        """Preserve Rugix bundle hash and SBOM links across artifact transfer."""
        downloaded = self.collect("rugix")
        result = self.upload(downloaded)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_uploads("rugix")

    def test_local_build_upload(self):
        """Keep the existing one-argument local build upload working."""
        self.make_build("rugix")
        result = self.upload()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_uploads("rugix")

    def test_wrong_version(self):
        """Reject transferred artifacts for another release before uploading."""
        downloaded = self.collect("rauc")
        metadata = downloaded / "os-release"
        metadata.write_text(metadata.read_text().replace("build-test", "other-version"))
        result = self.upload(downloaded)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("version mismatch", result.stdout)
        self.assertFalse(self.log.exists())

    def test_missing_metadata(self):
        """Reject a transferred directory that cannot identify its image."""
        downloaded = self.collect("rauc")
        (downloaded / "os-release").unlink()
        result = self.upload(downloaded)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("os-release is missing", result.stdout)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
