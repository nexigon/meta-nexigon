# Nexigon Yocto Layers

This repository provides Yocto layers for integrating [Nexigon](https://nexigon.dev) into a custom, [Yocto-based](https://www.yoctoproject.org) Linux distribution tailored to your embedded device.

## Layers

| Layer               | Compatible Releases | Description                    |
| ------------------- | ------------------- | ------------------------------ |
| `meta-nexigon-core` | Scarthgap           | Core recipes for Nexigon Agent |

### Recipes

- **`nexigon-agent`** — Builds the Nexigon Agent from source (Rust/Cargo).
- **`nexigon-agent-service`** — Systemd service unit and device fingerprint script.
- **`nexigon-agent-conf`** — Agent configuration (`/etc/nexigon/agent.toml`), templated with `NEXIGON_HUB_URL` and `NEXIGON_TOKEN`.

## Getting Started

The examples use [Kas](https://kas.readthedocs.io) for build configuration. A [justfile](https://just.systems) is provided for convenience.

## Configuration

To connect the agent to a Nexigon instance, set the following variables in your Kas configuration's `local_conf_header`:

```yaml
local_conf_header:
  nexigon: |
    NEXIGON_HUB_URL = "https://eu.nexigon.cloud"
    NEXIGON_TOKEN = "deployment_..."
```

## License

Licensed under either of [Apache License, Version 2.0](LICENSE-APACHE) or [MIT License](LICENSE-MIT), at your option.

---

Made with ❤️ by [Silitics](https://www.silitics.com)
