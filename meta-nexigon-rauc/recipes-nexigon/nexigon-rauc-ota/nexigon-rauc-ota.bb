SUMMARY = "Nexigon RAUC OTA update service"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

RDEPENDS:${PN} = "bash jq rauc"

inherit systemd

SYSTEMD_SERVICE:${PN} = "nexigon-rauc-ota.timer nexigon-rauc-ota.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

NEXIGON_OTA_INTERVAL ??= "4h"
NEXIGON_OTA_TAG ??= "stable"
NEXIGON_OTA_REPOSITORY ??= ""
NEXIGON_OTA_PACKAGE ??= ""

SRC_URI = " \
    file://nexigon-rauc-ota \
    file://nexigon-rauc-ota.service \
    file://nexigon-rauc-ota.timer \
    file://nexigon.ota.check.toml \
"

python do_validate_config() {
    repo = d.getVar('NEXIGON_OTA_REPOSITORY')
    pkg = d.getVar('NEXIGON_OTA_PACKAGE')
    if not repo:
        bb.fatal('NEXIGON_OTA_REPOSITORY is not set - required by nexigon-rauc-ota')
    if not pkg:
        bb.fatal('NEXIGON_OTA_PACKAGE is not set - required by nexigon-rauc-ota')
}
addtask validate_config before do_install

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/nexigon-rauc-ota ${D}${bindir}/

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/nexigon-rauc-ota.service ${D}${systemd_system_unitdir}/
    install -m 0644 ${WORKDIR}/nexigon-rauc-ota.timer ${D}${systemd_system_unitdir}/
    sed -i "s|@@INTERVAL@@|${NEXIGON_OTA_INTERVAL}|g" \
        ${D}${systemd_system_unitdir}/nexigon-rauc-ota.timer

    install -d ${D}${sysconfdir}/nexigon/agent/commands
    install -m 0644 ${WORKDIR}/nexigon.ota.check.toml ${D}${sysconfdir}/nexigon/agent/commands/

    install -d ${D}${sysconfdir}
    echo '{"path": "${NEXIGON_OTA_REPOSITORY}/${NEXIGON_OTA_PACKAGE}/${NEXIGON_OTA_TAG}"}' \
        > ${D}${sysconfdir}/nexigon-rauc-ota.json
}

CONFFILES:${PN} = "${sysconfdir}/nexigon-rauc-ota.json"
