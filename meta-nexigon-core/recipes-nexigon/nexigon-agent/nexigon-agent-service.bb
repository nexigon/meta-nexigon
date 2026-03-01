DESCRIPTION = "Nexigon Agent Systemd Service"
LICENSE = "Apache-2.0 & MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10 \
                    file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://nexigon-agent.service \
           file://nexigon-device-fingerprint"

RDEPENDS:${PN} = "nexigon-agent"

inherit systemd

SYSTEMD_SERVICE:${PN} = "nexigon-agent.service"

do_install() {
    # Install systemd service file.
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/nexigon-agent.service ${D}${systemd_system_unitdir}/nexigon-agent.service

    # Install default fingerprint script.
    install -d ${D}${libexecdir}/nexigon
    install -m 0755 ${WORKDIR}/nexigon-device-fingerprint ${D}${libexecdir}/nexigon/nexigon-device-fingerprint
}
