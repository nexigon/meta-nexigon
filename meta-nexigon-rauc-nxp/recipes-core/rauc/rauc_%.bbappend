FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " file://rauc-mark-good.conf"

do_install:append() {
    install -d ${D}${systemd_system_unitdir}/rauc-mark-good.service.d
    install -m 0644 ${UNPACKDIR}/rauc-mark-good.conf \
        ${D}${systemd_system_unitdir}/rauc-mark-good.service.d/nexigon.conf
}

FILES:${PN}-mark-good += "${systemd_system_unitdir}/rauc-mark-good.service.d"
