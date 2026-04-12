SUMMARY = "Nexigon Rugix watchdog for auto-rollback of uncommitted system updates"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

RDEPENDS:${PN} = "bash jq rugix-ctrl"

inherit systemd

SYSTEMD_SERVICE:${PN} = "nexigon-rugix-watchdog.timer nexigon-rugix-watchdog.service"

NEXIGON_OTA_RUGIX_WATCHDOG_TIMEOUT ??= "1800s"

SRC_URI = " \
    file://nexigon-rugix-watchdog \
    file://nexigon-rugix-watchdog.service \
    file://nexigon-rugix-watchdog.timer \
"

do_install() {
    install -d ${D}${libexecdir}/nexigon
    install -m 0755 ${WORKDIR}/nexigon-rugix-watchdog ${D}${libexecdir}/nexigon/

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/nexigon-rugix-watchdog.service ${D}${systemd_system_unitdir}/
    install -m 0644 ${WORKDIR}/nexigon-rugix-watchdog.timer ${D}${systemd_system_unitdir}/
    sed -i "s|@@TIMEOUT@@|${NEXIGON_OTA_RUGIX_WATCHDOG_TIMEOUT}|g" \
        ${D}${systemd_system_unitdir}/nexigon-rugix-watchdog.timer
}
