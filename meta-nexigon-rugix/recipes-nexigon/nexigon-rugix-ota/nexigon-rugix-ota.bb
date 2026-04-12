SUMMARY = "Nexigon Rugix OTA update service"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

RDEPENDS:${PN} = "bash jq rugix-ctrl nexigon-rugix-watchdog"

inherit systemd

SYSTEMD_SERVICE:${PN} = "nexigon-rugix-ota.timer nexigon-rugix-ota.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

NEXIGON_OTA_INTERVAL ??= "4h"
NEXIGON_OTA_TAG ??= "stable"
NEXIGON_OTA_REPOSITORY ??= ""
NEXIGON_OTA_PACKAGE ??= ""
NEXIGON_OTA_RUGIX_USE_BUNDLE_HASH ??= "0"

SRC_URI = " \
    file://nexigon-rugix-ota \
    file://nexigon-rugix-ota.service \
    file://nexigon-rugix-ota.timer \
    file://nexigon.ota.check.toml \
"

python do_validate_config() {
    repo = d.getVar('NEXIGON_OTA_REPOSITORY')
    pkg = d.getVar('NEXIGON_OTA_PACKAGE')
    if not repo:
        bb.fatal('NEXIGON_OTA_REPOSITORY is not set - required by nexigon-rugix-ota')
    if not pkg:
        bb.fatal('NEXIGON_OTA_PACKAGE is not set - required by nexigon-rugix-ota')
}
addtask validate_config before do_install

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/nexigon-rugix-ota ${D}${bindir}/

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/nexigon-rugix-ota.service ${D}${systemd_system_unitdir}/
    install -m 0644 ${WORKDIR}/nexigon-rugix-ota.timer ${D}${systemd_system_unitdir}/
    sed -i "s|@@INTERVAL@@|${NEXIGON_OTA_INTERVAL}|g" \
        ${D}${systemd_system_unitdir}/nexigon-rugix-ota.timer

    install -d ${D}${sysconfdir}/nexigon/agent/commands
    install -m 0644 ${WORKDIR}/nexigon.ota.check.toml ${D}${sysconfdir}/nexigon/agent/commands/

    install -d ${D}${sysconfdir}
    if [ "${NEXIGON_OTA_RUGIX_USE_BUNDLE_HASH}" = "1" ]; then
        _use_bundle_hash=true
    else
        _use_bundle_hash=false
    fi
    echo '{"path": "${NEXIGON_OTA_REPOSITORY}/${NEXIGON_OTA_PACKAGE}/${NEXIGON_OTA_TAG}", "rugix": {"useBundleHash": '${_use_bundle_hash}'}}' \
        > ${D}${sysconfdir}/nexigon-rugix-ota.json
}

CONFFILES:${PN} = "${sysconfdir}/nexigon-rugix-ota.json"
