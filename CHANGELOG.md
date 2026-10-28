# Changelog

## Unreleased

- Publish QEMU images to staging in separate jobs after all image builds succeed.
  Builds share one image version and retain downloadable artifacts. Published builds
  get an immutable `build-<timestamp>-<hash>` tag and a moving `latest-main` or
  `latest-pr<number>` tag. Local release tooling defaults to `latest-<branch>`.
  Version metadata records `sourceBranch`, using the base branch for PR builds.
- Run CI on pushes to `main` and pull requests, with staging publishing for pull
  requests from this repository. Git tags no longer trigger builds, uploads, or
  GitHub releases.

- Select the latest Nexigon Agent from `main` by default, using `PV = "0+git"`
  and an explicit version preference. Release 0.6.1 remains available through
  `PREFERRED_VERSION_nexigon-agent = "0.6.1"`.
- Remove the `nexigon-rauc-ota` and `nexigon-rugix-ota` recipes. Replace these
  entries in `IMAGE_INSTALL` with `nexigon-agent-conf`. The configuration package
  now installs the enabled update engine and, for Rugix, the rollback watchdog.
  Setting `NEXIGON_SYSTEM_UPDATES = ""` disables the integration and omits these
  dependencies.
