SUMMARY = "Rugix state configuration for Nexigon persistent data"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://nexigon.toml"
S = "${UNPACKDIR}"

do_install() {
    install -d ${D}${sysconfdir}/rugix/state
    install -m 0644 ${UNPACKDIR}/nexigon.toml ${D}${sysconfdir}/rugix/state/
}
