FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:remove = "file://system.conf"
SRC_URI:append = " file://system.conf.in"

# The configuration names the machine as the compatible.
PACKAGE_ARCH = "${MACHINE_ARCH}"

# RAUC reads and writes the boot counters with fw_setenv, which needs the
# fw_env.config of the bootloader.
RDEPENDS:${PN} += "u-boot-default-env"
# RAUC grows the installed root filesystem to the slot with resize2fs.
RDEPENDS:${PN} += "e2fsprogs-resize2fs"

do_install:prepend() {
    sed -e "s|@@MACHINE@@|${MACHINE}|" \
        -e "s|@@KEYRING@@|$(basename ${RAUC_KEYRING_FILE})|" \
        ${UNPACKDIR}/system.conf.in > ${UNPACKDIR}/system.conf
}
