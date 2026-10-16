# RAUC NXP Demo Layer

> [!WARNING]
> This layer is a demo for evaluating Nexigon with RAUC on NXP i.MX boards. It is not meant for production devices. See [Limitations](#limitations) for what a production integration needs on top.

`meta-nexigon-rauc-nxp` adds RAUC A/B system updates to 64-bit NXP i.MX 8 and i.MX 9 boards that use NXP's i.MX BSP (`meta-imx`) with U-Boot. Together with `meta-nexigon-rauc`, which enables the RAUC integration of Nexigon Agent, it lets you install updates from Nexigon Hub on a board.

The example `examples/frdm-imx91-rauc.yaml` builds an image for the [NXP FRDM-IMX91](https://www.nxp.com/design/design-center/development-boards-and-designs/FRDM-IMX91) on NXP's i.MX Linux release LF6.18.37-2.1.0. The image uses [provisioning](https://docs.nexigon.dev/guides/provisioning/): you flash it to a board and then pair the board with a project in Nexigon Hub.

## How Updates Work

RAUC installs an update into the inactive one of two slots and then tells the bootloader to try it. If the new system does not come up, the bootloader falls back to the previous slot. The layer uses the following partition layout:

| Partition | Name       | Contents                                                                        |
| --------- | ---------- | ------------------------------------------------------------------------------- |
| 1         | `uboot`    | FAT partition with the boot script `boot.scr` and its boot counters `rauc.env`. |
| 2         | `rootfs_a` | Root filesystem of slot A, including the kernel and device tree in `/boot`.     |
| 3         | `rootfs_b` | Root filesystem of slot B, empty until the first update.                        |
| 4         | `data`     | Data that persists across updates, mounted at `/data`.                          |

The BootROM loads `imx-boot`, which contains U-Boot. On an SD card, `imx-boot` sits at 32 KiB in front of the partitions.

U-Boot runs `boot.scr` from the FAT partition. The script implements the boot counting scheme of [RAUC's U-Boot integration](https://rauc.readthedocs.io/en/latest/integration.html#u-boot): `BOOT_ORDER` lists the slots in the order to try, and `BOOT_A_LEFT` and `BOOT_B_LEFT` count the remaining boot attempts of each slot. On every boot, the script picks the first slot with attempts left, decrements its counter, and boots the kernel from that slot. After an installation, RAUC puts the new slot first in `BOOT_ORDER`. Once all services, including Nexigon Agent, have started, RAUC's `rauc-mark-good` service resets the counter of the booted slot.

A slot that fails to boot three times is skipped. To make failures count, the board resets when U-Boot cannot boot a slot, when the kernel panics or does not find the root filesystem, and, through the hardware watchdog, when the system hangs.

The script stores the counters in `rauc.env` on the FAT partition instead of in U-Boot's environment storage, which is fixed to one MMC device. This way, the same image works from an SD card and from eMMC. Linux mounts the FAT partition at `/uboot`, where RAUC reads and writes the counters with `fw_printenv` and `fw_setenv`.

Nexigon Agent keeps its device fingerprint, its TLS identity, and the credentials obtained through provisioning in `/data/nexigon/agent`, so that the device keeps its identity across updates.

## Before You Start

You need:

- A project in [Nexigon Hub](https://nexigon.cloud).
- [mise](https://mise.jdx.dev) and Podman, which the build uses to run [kas](https://kas.readthedocs.io) in a container. The first build of the NXP BSP takes several hours and more than 100 GB of disk space.
- An NXP FRDM-IMX91 board, a USB cable for its debug console (115200 baud), and an Ethernet connection with DHCP.
- A microSD card with at least 4 GB, unless you flash the eMMC.

## Building the FRDM-IMX91 Image

The build signs update bundles with a development key and installs the certificate of the CA that issued it on the image. Bundles install only on images that trust their CA, so keep the keys in `rauc-keys/` for future builds. Generate them once:

```sh
mise run generate-rauc-keys
```

To share development keys between machines, set `RAUC_DEV_CA_CERT`, `RAUC_DEV_SIGNING_CERT`, and `RAUC_DEV_SIGNING_KEY` to the PEM contents of the CA certificate, the signing certificate, and the signing key, for example in `.env`. The task then writes these keys to `rauc-keys/` instead of generating new ones.

Then build the image and the update bundle:

```sh
mise run build examples/frdm-imx91-rauc.yaml
```

The example accepts the NXP EULA on your behalf (`ACCEPT_FSL_EULA`). Read the `EULA` file of [meta-freescale](https://github.com/Freescale/meta-freescale/blob/wrynose/EULA) before building. To give the image a default update path, set `NEXIGON_OTA_REPOSITORY` and `NEXIGON_OTA_PACKAGE` in `.env` before building. Without them, set the path with **Configure Updates** on the device page after pairing.

The build writes these artifacts to `build/tmp/deploy/images/imx91-11x11-lpddr4-frdm/`:

| File                                                         | Purpose                           |
| ------------------------------------------------------------ | --------------------------------- |
| `core-image-minimal-imx91-11x11-lpddr4-frdm.rootfs.wic.bz2`  | Disk image to flash.              |
| `core-image-minimal-imx91-11x11-lpddr4-frdm.rootfs.wic.bmap` | Block map for `bmaptool`.         |
| `imx-boot-imx91-11x11-lpddr4-frdm-sd.bin-flash_singleboot`   | Bootloader for flashing with UUU. |
| `nexigon-demo-bundle-imx91-11x11-lpddr4-frdm.raucb`          | RAUC update bundle.               |

## Flashing the Board

Write the image to an SD card, for example with [bmaptool](https://github.com/yoctoproject/bmaptool), replacing `/dev/sdX` with your SD card:

```sh
bmaptool copy core-image-minimal-imx91-11x11-lpddr4-frdm.rootfs.wic.bz2 /dev/sdX
```

Alternatively, write the image to the eMMC with NXP's [UUU](https://github.com/nxp-imx/mfgtools) while the board is in serial download mode. UUU writes `imx-boot` to the boot partition of the eMMC:

```sh
uuu -b emmc_all imx-boot-imx91-11x11-lpddr4-frdm-sd.bin-flash_singleboot \
    core-image-minimal-imx91-11x11-lpddr4-frdm.rootfs.wic.bz2/*
```

Set the boot mode switches for the medium you flashed, as described in NXP's [Getting Started with FRDM-IMX91](https://www.nxp.com/document/guide/getting-started-with-frdm-imx91-development-board:GS-FRDM-IMX91) guide. Do not keep the image on both the SD card and the eMMC. U-Boot prefers the eMMC, and Linux would see duplicate partition names.

## Pairing the Board

Connect the board to the network and power it on. Nexigon Agent then waits for a provisioning token on port 6947. To find the board's IP address, log in as `root` without a password on the debug console and run `ip addr`.

In Nexigon Hub, open **Devices** in your project, choose **Add Device**, and copy the command from the **Provisioning Token** tab. The token expires after five minutes. Replace `DEVICE_ADDRESS` with the board's IP address and run the command from a machine on the same network:

```sh
curl --fail-with-body --data "eu.nexigon.cloud,PAIRING_KEY" http://DEVICE_ADDRESS:6947/pair
```

The board appears in the device list and stays paired across updates. See [Device Provisioning](https://docs.nexigon.dev/guides/provisioning/) for details.

## Publishing Updates

The release scripts of meta-nexigon create a version in Nexigon Hub, build the image with that version, and upload the disk image and the update bundle. They need [Nexigon CLI](https://docs.nexigon.dev/cli/), authenticated for your organization, and `jq`. Set `NEXIGON_OTA_REPOSITORY` and `NEXIGON_OTA_PACKAGE` in `.env` to the package that receives the releases. Then run:

```sh
mise run prepare-release
mise run build-release examples/frdm-imx91-rauc.yaml
mise run upload-release imx91-11x11-lpddr4-frdm
```

Use **Configure Updates** on the device page to select the release for a board. See [Deploy System Updates](https://docs.nexigon.dev/guides/system-updates/).

## Using the Layer on Other Boards

The layer works with boards whose NXP BSP uses `u-boot-imx` with standard boot, which sets `devtype` and `devnum` for boot scripts. Start from `examples/frdm-imx91-rauc.yaml` and change `machine` to your board. The example includes the layers that the demo layer depends on and sets the image configuration of the layer:

```bitbake
WKS_FILE = "nexigon-rauc-nxp.wks.in"
IMAGE_BOOT_FILES = "boot.scr"
IMAGE_FSTYPES = "ext4 wic.bz2 wic.bmap"
IMAGE_INSTALL:append = " kernel-image kernel-devicetree"
```

The bundle installs the `ext4` image of the root filesystem. The boot script loads the first device tree of `KERNEL_DEVICETREE`. To use another device tree in `/boot`, set `NEXIGON_RAUC_KERNEL_DTB` to its file name. Build `nexigon-demo-bundle` for the update bundle. It contains `core-image-minimal` unless you set `RAUC_SLOT_rootfs`.

## Limitations

The demo leaves out several parts of a production integration:

- **Development access.** The root account has no password, and SSH accepts logins as root.
- **Provisioning.** Every image, including the images that updates install, accepts a provisioning token while the board is unpaired. Whoever reaches port 6947 first pairs the board with their Nexigon Hub and gets its remote terminal as root. Pair boards on a trusted network. The [provisioning guide](https://docs.nexigon.dev/guides/provisioning/) recommends a dedicated provisioning image.
- **Signing keys.** The build signs bundles with development keys from `rauc-keys/`. Production devices need keys that are managed securely.
- **Verified boot.** U-Boot does not verify the boot script, the kernel, or the root filesystem, and the root filesystem is writable.
- **Health checks.** RAUC marks a slot as good once its services have started, without checking that the device can still reach Nexigon Hub. An update that breaks the network connection stays installed.
- **Boot counters.** U-Boot rewrites `rauc.env` on every boot. If power fails during the write, the counters reset to their defaults, and the board boots slot A even if slot B has the newer system.
- **Bootloader and boot script.** Updates replace the root filesystem only. They do not change `imx-boot` or `boot.scr`.
- **Partition sizes.** The root filesystem slots have 1.5 GiB each and the data partition has 512 MiB, regardless of the size of the SD card or eMMC. RAUC grows an installed root filesystem to the size of its slot.
