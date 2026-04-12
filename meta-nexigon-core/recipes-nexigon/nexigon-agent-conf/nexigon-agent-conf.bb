DESCRIPTION = "Nexigon Agent Configuration"
LICENSE = "Apache-2.0 & MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10 \
                    file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://agent.toml \
           file://nexigon-device-fingerprint-machine-id \
           file://nexigon-device-fingerprint-random-uuid"

RDEPENDS:${PN} = "nexigon-agent-service"

NEXIGON_HUB_URL ??= ""
NEXIGON_TOKEN ??= ""
NEXIGON_COMMANDS_ENABLED ??= "0"
NEXIGON_TERMINAL_ENABLED ??= "0"
NEXIGON_TERMINAL_USER ??= "root"
NEXIGON_AGENT_SSL_DIR ??= ""
NEXIGON_AGENT_EXTRA_CONF ??= ""

# Device fingerprint source:
#   "machine-id"   - uses /etc/machine-id (default)
#   "random-uuid"  - generates a persistent UUID at NEXIGON_DEVICE_FINGERPRINT_FILE
#   <path>         - path to a custom fingerprint script
NEXIGON_DEVICE_FINGERPRINT ??= ""

# Path where the random-uuid fingerprint script stores its ID.
NEXIGON_DEVICE_FINGERPRINT_FILE ??= "/var/lib/nexigon/device-fingerprint-uuid"

python do_validate_config() {
    fp = d.getVar('NEXIGON_DEVICE_FINGERPRINT')
    if not fp:
        bb.fatal('NEXIGON_DEVICE_FINGERPRINT is not set - must be "machine-id", "random-uuid", or a path to a custom script')
    if fp == 'random-uuid' and not d.getVar('NEXIGON_DEVICE_FINGERPRINT_FILE'):
        bb.fatal('NEXIGON_DEVICE_FINGERPRINT_FILE must be set when using random-uuid fingerprint')
}
addtask validate_config before do_install

do_install() {
    install -d ${D}${sysconfdir}/nexigon
    install -m 0644 ${WORKDIR}/agent.toml ${D}${sysconfdir}/nexigon/agent.toml

    sed -i "s|@@HUB_URL@@|${NEXIGON_HUB_URL}|g" ${D}${sysconfdir}/nexigon/agent.toml
    sed -i "s|@@TOKEN@@|${NEXIGON_TOKEN}|g" ${D}${sysconfdir}/nexigon/agent.toml

    if [ -n "${NEXIGON_AGENT_SSL_DIR}" ]; then
        cat >> ${D}${sysconfdir}/nexigon/agent.toml <<EOF

ssl-cert = "${NEXIGON_AGENT_SSL_DIR}/cert.pem"
ssl-key = "${NEXIGON_AGENT_SSL_DIR}/key.pem"
EOF
        install -d ${D}${systemd_system_unitdir}/nexigon-agent.service.d
        cat > ${D}${systemd_system_unitdir}/nexigon-agent.service.d/ssl-dir.conf <<EOF
[Unit]
RequiresMountsFor=${NEXIGON_AGENT_SSL_DIR}
EOF
    fi

    if [ -n "${NEXIGON_AGENT_EXTRA_CONF}" ]; then
        printf '\n%b\n' "${NEXIGON_AGENT_EXTRA_CONF}" >> ${D}${sysconfdir}/nexigon/agent.toml
    fi

    if [ "${NEXIGON_COMMANDS_ENABLED}" = "1" ]; then
        cat >> ${D}${sysconfdir}/nexigon/agent.toml <<EOF

[commands]
enabled = true
EOF
    fi

    if [ "${NEXIGON_TERMINAL_ENABLED}" = "1" ]; then
        cat >> ${D}${sysconfdir}/nexigon/agent.toml <<EOF

[terminal]
enabled = true
user = "${NEXIGON_TERMINAL_USER}"
EOF
    fi

    install -d ${D}${libexecdir}/nexigon
    if [ "${NEXIGON_DEVICE_FINGERPRINT}" = "machine-id" ]; then
        install -m 0755 ${WORKDIR}/nexigon-device-fingerprint-machine-id \
            ${D}${libexecdir}/nexigon/nexigon-device-fingerprint
        sed -i "s|@@FINGERPRINT_SCRIPT@@|${libexecdir}/nexigon/nexigon-device-fingerprint|g" \
            ${D}${sysconfdir}/nexigon/agent.toml
    elif [ "${NEXIGON_DEVICE_FINGERPRINT}" = "random-uuid" ]; then
        install -m 0755 ${WORKDIR}/nexigon-device-fingerprint-random-uuid \
            ${D}${libexecdir}/nexigon/nexigon-device-fingerprint
        sed -i "s|@@NEXIGON_DEVICE_FINGERPRINT_FILE@@|${NEXIGON_DEVICE_FINGERPRINT_FILE}|g" \
            ${D}${libexecdir}/nexigon/nexigon-device-fingerprint
        sed -i "s|@@FINGERPRINT_SCRIPT@@|${libexecdir}/nexigon/nexigon-device-fingerprint|g" \
            ${D}${sysconfdir}/nexigon/agent.toml
    else
        sed -i "s|@@FINGERPRINT_SCRIPT@@|${NEXIGON_DEVICE_FINGERPRINT}|g" \
            ${D}${sysconfdir}/nexigon/agent.toml
    fi
}

FILES:${PN} += "${systemd_system_unitdir}/nexigon-agent.service.d"
