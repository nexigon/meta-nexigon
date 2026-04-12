# meta-nexigon

[Yocto](https://www.yoctoproject.org) layers for integrating [Nexigon](https://nexigon.cloud) into embedded Linux images.

## What's Included?

The **Core Layer** (`meta-nexigon-core`) is the foundation. It ships the Nexigon Agent, which connects your device to Nexigon Hub and enables remote terminal access, device commands (systemd management, power control), and device telemetry (properties, events).

On top of that, pick the OTA layer that matches your update engine:

- The **RAUC Layer** (`meta-nexigon-rauc`) orchestrates OTA updates on [RAUC](https://rauc.io)-based systems.
- The **Rugix Layer** (`meta-nexigon-rugix`) orchestrates OTA updates on [Rugix](https://rugix.org)-based systems.

Both OTA layers work the same way: a timer periodically resolves a version tag on Nexigon Hub. If the tagged version doesn't match what's running, the bundle is downloaded and installed. Throughout an update, telemetry is reported back using properties and events.

Using a different update engine? The RAUC and Rugix scripts serve as reference implementations. Nexigon Hub provides [composable primitives](https://nexigon.cloud/blog/2026-02-19-primitives-first-architecture) (repositories, versioned packages, device properties, events) that you can integrate with any update mechanism.

## Getting Started

The examples use [Kas](https://kas.readthedocs.io) for build configuration. A [justfile](https://just.systems) wraps common operations.

Set your Nexigon Hub URL and deployment token in a `.env` file:

```sh
NEXIGON_HUB_URL="https://eu.nexigon.cloud"
NEXIGON_TOKEN="deployment_..."
NEXIGON_OTA_REPOSITORY="your-repo"
NEXIGON_OTA_PACKAGE="your-package"
```

Build an example image:

```sh
# With Rugix
just build examples/qemu-x86_64-rugix.yaml

# With RAUC (generate signing keys first)
just generate-rauc-keys
just build examples/qemu-x86_64-rauc.yaml
```

Boot it in QEMU with `just run-qemu-x86_64` and SSH in with `just ssh-qemu`.

## Device Identity

Every device needs a stable fingerprint so Nexigon Hub can identify it across reboots and updates.

Set `NEXIGON_DEVICE_FINGERPRINT` to one of:

- `"machine-id"` — Uses `/etc/machine-id` to compute the device fingerprint. Works for single-rootfs systems and Rugix, which persists the machine ID across A/B slots (requires state management).
- `"random-uuid"` — Generates a UUID on first boot and stores it at `NEXIGON_DEVICE_FINGERPRINT_FILE`. Use this for RAUC or any A/B scheme where `/etc` differs between slots.
- A path to your own script — for hardware-backed identifiers like a TPM or board serial number.

For A/B systems where each slot has its own non-persistent `/etc`, also set `NEXIGON_AGENT_SSL_DIR` to a shared partition (e.g. `/data/nexigon/agent/ssl`) so the agent's TLS identity survives slot switches.

## Releasing Updates

The `scripts/` directory provides a three-step release workflow:

1. **`prepare-release.sh`** — Create a version in Nexigon Hub and pin it in `.release.env`.
2. **`build-release.sh <kas-config>`** — Build the image with the pinned version baked in.
3. **`upload-release.sh <machine>`** — Upload the image and update bundle to the hub.

The upload script auto-detects Rugix (`.rugixb`) and RAUC (`.raucb`) bundles and uploads whichever is present.

## Testing

```sh
just test
```

The test suite boots real QEMU images, talks to a live Nexigon Hub instance, and exercises the full OTA pipeline: bundle upload, version resolution, install, reboot, and commit/rollback. Tests auto-detect which update engine was built and skip the rest. Run a specific suite with `just test -m rugix` or `just test -m rauc`.

## Configuration Reference

See the example Kas configs under `examples/` for working setups. The key variables:

| Variable                     | Recipe               | Description                                        |
| ---------------------------- | -------------------- | -------------------------------------------------- |
| `NEXIGON_HUB_URL`            | `nexigon-agent-conf` | Nexigon Hub URL. Required.                         |
| `NEXIGON_TOKEN`              | `nexigon-agent-conf` | Deployment token. Required.                        |
| `NEXIGON_DEVICE_FINGERPRINT` | `nexigon-agent-conf` | Fingerprint mechanism. Required.                   |
| `NEXIGON_AGENT_SSL_DIR`      | `nexigon-agent-conf` | Persistent SSL cert/key directory for A/B systems. |
| `NEXIGON_OTA_REPOSITORY`     | `nexigon-*-ota`      | Repository on Nexigon Hub. Required.               |
| `NEXIGON_OTA_PACKAGE`        | `nexigon-*-ota`      | Package within the repository. Required.           |
| `NEXIGON_OTA_TAG`            | `nexigon-*-ota`      | Version tag to track (default: `"stable"`).        |
| `NEXIGON_OTA_INTERVAL`       | `nexigon-*-ota`      | Update check interval (default: `"4h"`).           |

## Licensing

This project is licensed under either [MIT](https://github.com/nexigon/meta-nexigon/blob/main/LICENSE-MIT) or [Apache 2.0](https://github.com/nexigon/meta-nexigon/blob/main/LICENSE-APACHE) at your option.

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in this project by you, as defined in the Apache 2.0 license, shall be dual licensed as above, without any additional terms or conditions.

---

Made with ❤️ for OSS by [Silitics](https://www.silitics.com)
