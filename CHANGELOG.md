# Changelog

## Unreleased

- Publish QEMU images to staging in separate jobs after all image builds succeed.
  Builds share one image version and retain downloadable artifacts. Staging
  publishing also runs for pull requests from this repository, updating a
  `pr<number>` tag. Only `main` moves `latest-build-main`.

- Select the latest Nexigon Agent from `main` by default, using `PV = "0+git"`
  and an explicit version preference. Release 0.6.1 remains available through
  `PREFERRED_VERSION_nexigon-agent = "0.6.1"`.
- Remove the `nexigon-rauc-ota` and `nexigon-rugix-ota` recipes. Replace these
  entries in `IMAGE_INSTALL` with `nexigon-agent-conf`. The configuration package
  now installs the enabled update engine and, for Rugix, the rollback watchdog.
  Setting `NEXIGON_SYSTEM_UPDATES = ""` disables the integration and omits these
  dependencies.
