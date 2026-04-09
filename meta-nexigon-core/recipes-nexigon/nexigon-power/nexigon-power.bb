SUMMARY = "Nexigon power management commands"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://nexigon.power.reboot.toml \
    file://nexigon.power.shutdown.toml \
"

do_install() {
    install -d ${D}${sysconfdir}/nexigon/agent/commands
    install -m 0644 ${WORKDIR}/nexigon.power.reboot.toml ${D}${sysconfdir}/nexigon/agent/commands/
    install -m 0644 ${WORKDIR}/nexigon.power.shutdown.toml ${D}${sysconfdir}/nexigon/agent/commands/
}
