SUMMARY = "Nexigon Rugix Apps lifecycle management commands"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

RDEPENDS:${PN} = "bash jq rugix-ctrl nexigon-agent python3-core python3-json python3-io python3-fcntl"

inherit systemd
SYSTEMD_SERVICE:${PN} = "nexigon-rugix-apps-reconcile.timer"
SYSTEMD_AUTO_ENABLE = "enable"
FILES:${PN} += "${systemd_system_unitdir}/nexigon-rugix-apps-reconcile.*"

SRC_URI = " \
    file://nexigon.rugix-apps.list.toml \
    file://nexigon.rugix-apps.info.toml \
    file://nexigon.rugix-apps.deploy.toml \
    file://nexigon.rugix-apps.start.toml \
    file://nexigon.rugix-apps.stop.toml \
    file://nexigon.rugix-apps.remove.toml \
    file://nexigon.rugix-apps.rollback.toml \
    file://nexigon-rugix-apps \
    file://nexigon-rugix-apps-deploy \
    file://nexigon-rugix-apps-reconcile \
    file://nexigon.rugix-apps.reconcile.toml \
    file://nexigon-rugix-apps-reconcile.service \
    file://nexigon-rugix-apps-reconcile.timer \
    file://nexigon-rugix-apps-state.toml \
"

do_install() {
    install -d ${D}${sysconfdir}/nexigon/agent/commands
    for f in ${WORKDIR}/nexigon.rugix-apps.*.toml; do
        install -m 0644 "$f" ${D}${sysconfdir}/nexigon/agent/commands/
    done

    install -d ${D}${libexecdir}/nexigon
    install -m 0755 ${WORKDIR}/nexigon-rugix-apps ${D}${libexecdir}/nexigon/
    install -m 0755 ${WORKDIR}/nexigon-rugix-apps-deploy ${D}${libexecdir}/nexigon/
    install -m 0755 ${WORKDIR}/nexigon-rugix-apps-reconcile ${D}${libexecdir}/nexigon/
    install -d ${D}${sysconfdir}/rugix/state
    install -m 0644 ${WORKDIR}/nexigon-rugix-apps-state.toml ${D}${sysconfdir}/rugix/state/nexigon-rugix-apps.toml
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/nexigon-rugix-apps-reconcile.service ${WORKDIR}/nexigon-rugix-apps-reconcile.timer ${D}${systemd_system_unitdir}/
}
