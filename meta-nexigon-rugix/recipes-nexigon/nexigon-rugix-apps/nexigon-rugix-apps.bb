SUMMARY = "Nexigon Rugix Apps lifecycle management commands"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

RDEPENDS:${PN} = "bash jq"

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
"

do_install() {
    install -d ${D}${sysconfdir}/nexigon/agent/commands
    for f in ${WORKDIR}/nexigon.rugix-apps.*.toml; do
        install -m 0644 "$f" ${D}${sysconfdir}/nexigon/agent/commands/
    done

    install -d ${D}${libexecdir}/nexigon
    install -m 0755 ${WORKDIR}/nexigon-rugix-apps ${D}${libexecdir}/nexigon/
    install -m 0755 ${WORKDIR}/nexigon-rugix-apps-deploy ${D}${libexecdir}/nexigon/
}
