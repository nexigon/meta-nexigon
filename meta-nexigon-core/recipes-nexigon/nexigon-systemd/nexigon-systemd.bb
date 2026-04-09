SUMMARY = "Nexigon systemd service management commands"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

RDEPENDS:${PN} = "bash jq"

SRC_URI = " \
    file://nexigon.systemd.status.toml \
    file://nexigon.systemd.restart.toml \
    file://nexigon.systemd.list-units.toml \
    file://nexigon-systemd-status \
    file://nexigon-systemd-restart \
    file://nexigon-systemd-list-units \
"

do_install() {
    install -d ${D}${sysconfdir}/nexigon/agent/commands
    install -m 0644 ${WORKDIR}/nexigon.systemd.status.toml ${D}${sysconfdir}/nexigon/agent/commands/
    install -m 0644 ${WORKDIR}/nexigon.systemd.restart.toml ${D}${sysconfdir}/nexigon/agent/commands/
    install -m 0644 ${WORKDIR}/nexigon.systemd.list-units.toml ${D}${sysconfdir}/nexigon/agent/commands/

    install -d ${D}${libexecdir}/nexigon
    install -m 0755 ${WORKDIR}/nexigon-systemd-status ${D}${libexecdir}/nexigon/
    install -m 0755 ${WORKDIR}/nexigon-systemd-restart ${D}${libexecdir}/nexigon/
    install -m 0755 ${WORKDIR}/nexigon-systemd-list-units ${D}${libexecdir}/nexigon/
}
