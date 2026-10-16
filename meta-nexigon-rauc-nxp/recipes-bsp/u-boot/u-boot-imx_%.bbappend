FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " \
    file://boot.cmd.in \
    file://fw_env.config \
    file://rauc-uboot.cfg \
"

# Compile boot.cmd into boot.scr and deploy it for the FAT partition.
UBOOT_ENV = "boot"
UBOOT_ENV_SUFFIX = "scr"

# Device tree that the boot script loads, by default the first one of the
# machine.
NEXIGON_RAUC_KERNEL_DTB ?= "${@os.path.basename(d.getVar('KERNEL_DEVICETREE').split()[0])}"

do_compile:prepend() {
    sed -e "s|@@KERNEL_IMAGETYPE@@|${KERNEL_IMAGETYPE}|" \
        -e "s|@@KERNEL_DTB@@|${NEXIGON_RAUC_KERNEL_DTB}|" \
        ${UNPACKDIR}/boot.cmd.in > ${UNPACKDIR}/boot.cmd
}
