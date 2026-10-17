# meta-nexigon

[Yocto](https://www.yoctoproject.org) layers for integrating [Nexigon](https://nexigon.cloud) into embedded Linux images.

## What's Included?

The **Core Layer** (`meta-nexigon-core`) is the foundation. It ships the Nexigon Agent, which connects your device to Nexigon Hub and enables remote terminal access, device commands (systemd management, power control), and device telemetry (properties, events).

On top of that, pick the OTA layer that matches your update engine:

- The **RAUC Layer** (`meta-nexigon-rauc`) enables OTA updates on [RAUC](https://rauc.io)-based systems.
- The **Rugix Layer** (`meta-nexigon-rugix`) enables OTA updates on [Rugix](https://rugix.org)-based systems.

The `main` branch supports Yocto 6.0 (wrynose). For Yocto 5.0 (scarthgap), use the [`scarthgap`](https://github.com/nexigon/meta-nexigon/tree/scarthgap) branch.

On the `main` branch, the Core Layer builds Nexigon Agent from the `main` branch of [nexigon/nexigon](https://github.com/nexigon/nexigon). The OTA layers need its system update integration, which no release includes yet. Without the OTA layers, you can build the latest release with `PREFERRED_VERSION_nexigon-agent = "0.6.0"`.

Both OTA layers enable the system update integration of the agent for their update engine as soon as the layer is included. Set `NEXIGON_SYSTEM_UPDATES = ""` to include a layer without enabling updates. The agent periodically resolves a version tag on Nexigon Hub. If the tagged version doesn't match what's running, it downloads and installs the bundle, reboots, and reports the outcome in the `dev.nexigon.ota.status` device property. The `dev.nexigon.ota.config` device property can hold updates, restrict them to maintenance windows, and limit retries. See [OTA Updates](https://docs.nexigon.dev/reference/ota-updates/) for the full update model.

Using a different update engine? Nexigon Hub provides [composable primitives](https://nexigon.cloud/blog/2026-02-19-primitives-first-architecture) (repositories, versioned packages, device properties, events) that you can integrate with any update mechanism.

## Getting Started

The examples use [Kas](https://kas.readthedocs.io) for build configuration. Toolchain and tasks are managed with [mise](https://mise.jdx.dev).

Build an example image:

```sh
# With Rugix
mise run build examples/qemu-x86_64-rugix.yaml

# With RAUC (generate signing keys first)
mise run generate-rauc-keys
mise run build examples/qemu-x86_64-rauc.yaml
```

Boot it in QEMU with `mise run run-qemu-x86_64` and SSH in with `mise run ssh-qemu`.

The example images contain no credentials. Instead, a device pairs with a project on Nexigon Hub after its first boot. Create a pairing key in the project and send it to the device together with the domain of your Hub. For the QEMU VM, run:

```sh
mise run pair-qemu eu.nexigon.cloud,<pairing key>
```

The images also contain no update package, so you choose one for each device under **Configure Updates** in Nexigon Hub. To build a package into the image, set `NEXIGON_OTA_REPOSITORY` and `NEXIGON_OTA_PACKAGE`, for example in a `.env` file.

## Credentials

Nexigon Agent connects to Nexigon Hub with static credentials or with credentials obtained through provisioning:

- **Static credentials.** Set `NEXIGON_HUB_URL` to the URL of Nexigon Hub and `NEXIGON_TOKEN` to a deployment token. Every device built from the image connects on its first boot.
- **Provisioning.** Set `NEXIGON_PROVISIONING = "1"` and leave `NEXIGON_HUB_URL` and `NEXIGON_TOKEN` empty. Until it is paired, the agent accepts a one-time pairing key on port 6947 and then saves the credentials that it receives. Anyone who can reach the port can pair an unpaired device. See [Device Provisioning](https://docs.nexigon.dev/guides/provisioning/). To configure the listener, for example its port, leave `NEXIGON_PROVISIONING` at `"0"` and add a `[provisioning]` table to `NEXIGON_AGENT_EXTRA_CONF` instead.

The examples use provisioning. To build them with static credentials, set `NEXIGON_PROVISIONING = "0"` together with the credentials in `local.conf`, for example through an additional Kas configuration.

With neither, the agent uses credentials saved by an earlier provisioning and fails to start if there are none. A production image installed by an update after provisioning works this way.

## Device Identity

Every device needs a stable fingerprint so Nexigon Hub can identify it across reboots and updates.

Set `NEXIGON_DEVICE_FINGERPRINT` to one of:

- `"machine-id"` — Uses `/etc/machine-id` to compute the device fingerprint. Works for single-rootfs systems and Rugix, which persists the machine ID across A/B slots (requires state management).
- `"random-uuid"` — Generates a UUID on first boot and stores it at `NEXIGON_DEVICE_FINGERPRINT_FILE`. Use this for RAUC or any A/B scheme where `/etc` differs between slots.
- A path to your own script — for hardware-backed identifiers like a TPM or board serial number.

For A/B systems where each slot has its own non-persistent `/etc`, also set `NEXIGON_AGENT_SSL_DIR` to a shared partition (e.g. `/data/nexigon/agent/ssl`) so the agent's TLS identity survives slot switches. Also set `NEXIGON_AGENT_DATA_DIR` to a shared partition (e.g. `/data/nexigon/agent`) for the data of the agent, which includes the credentials saved by provisioning. The RAUC examples keep the fingerprint, the TLS identity, and the agent data on the data partition. On Rugix, `meta-nexigon-rugix` persists these directories with Rugix state management.

## Releasing Updates

The `scripts/` directory provides a three-step release workflow:

1. **`prepare-release.sh`** — Create a version in Nexigon Hub and pin it in `.release.env`.
2. **`build-release.sh <kas-config>`** — Build the image with the pinned version baked in.
3. **`upload-release.sh <machine>`** — Upload the image and update bundle to the hub.

The upload script auto-detects Rugix (`.rugixb`) and RAUC (`.raucb`) bundles and uploads whichever is present.

## Testing

```sh
mise run test
```

The test suite boots real QEMU images, talks to a live Nexigon Hub instance, and exercises the full OTA pipeline: bundle upload, version resolution, install, reboot, commit, and rollback detection, as well as holds, maintenance windows, retries, and checkpoint releases. The OTA tests detect the update engine and the package from the agent configuration of the built image, so build the image with `NEXIGON_OTA_REPOSITORY` and `NEXIGON_OTA_PACKAGE`.

Set `NEXIGON_HUB_URL`, `TESTS_API_TOKEN`, and `TESTS_PROJECT_ID` for the Hub and the project. The tests pair each VM with the project through provisioning.

## Configuration Reference

See the example Kas configs under `examples/` for working setups. The key variables:

| Variable                     | Recipe               | Description                                        |
| ---------------------------- | -------------------- | -------------------------------------------------- |
| `NEXIGON_HUB_URL`            | `nexigon-agent-conf` | Nexigon Hub URL for static credentials.            |
| `NEXIGON_TOKEN`              | `nexigon-agent-conf` | Deployment token for static credentials.           |
| `NEXIGON_PROVISIONING`       | `nexigon-agent-conf` | Accept a provisioning token while unpaired (default: `"0"`). |
| `NEXIGON_DEVICE_FINGERPRINT` | `nexigon-agent-conf` | Fingerprint mechanism. Required.                   |
| `NEXIGON_AGENT_SSL_DIR`      | `nexigon-agent-conf` | Persistent SSL cert/key directory for A/B systems. |
| `NEXIGON_AGENT_DATA_DIR`     | `nexigon-agent-conf` | Data directory of the agent, including saved credentials (default: `/var/lib/nexigon/agent`). |
| `NEXIGON_SYSTEM_UPDATES`     | `nexigon-agent-conf` | Update engine of the agent: `"rugix"`, `"rauc"`, or `""` for none. The OTA layers set it. |
| `NEXIGON_OTA_REPOSITORY`     | `nexigon-agent-conf` | Repository on Nexigon Hub.                         |
| `NEXIGON_OTA_PACKAGE`        | `nexigon-agent-conf` | Package within the repository.                     |
| `NEXIGON_OTA_TAG`            | `nexigon-agent-conf` | Version tag to track (default: `"stable"`).        |
| `NEXIGON_OTA_INTERVAL`       | `nexigon-agent-conf` | Update check interval, such as `"1h 30min"` (default: `"4h"`). |
| `NEXIGON_OTA_RANDOMIZED_DELAY` | `nexigon-agent-conf` | Maximum random delay of scheduled update checks, which keeps devices from reaching Nexigon Hub at once (default: `"5min"`). |
| `NEXIGON_OTA_RUGIX_USE_BUNDLE_HASH` | `nexigon-agent-conf` | Verify Rugix bundles with the hash from the asset metadata when present (default: `"0"`). |

Without `NEXIGON_OTA_REPOSITORY` and `NEXIGON_OTA_PACKAGE`, devices do not update until the `dev.nexigon.ota.config` device property supplies a path. The `nexigon.ota.check` command, which triggers an immediate update check, requires `NEXIGON_COMMANDS_ENABLED = "1"`.

## Licensing

This project is licensed under either [MIT](https://github.com/nexigon/meta-nexigon/blob/main/LICENSE-MIT) or [Apache 2.0](https://github.com/nexigon/meta-nexigon/blob/main/LICENSE-APACHE) at your option.

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in this project by you, as defined in the Apache 2.0 license, shall be dual licensed as above, without any additional terms or conditions.

---

Made with ❤️ for OSS by [Silitics](https://www.silitics.com)
