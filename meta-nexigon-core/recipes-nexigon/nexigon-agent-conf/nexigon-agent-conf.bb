DESCRIPTION = "Nexigon Agent Configuration"
LICENSE = "Apache-2.0 & MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10 \
                    file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://agent.toml \
           file://nexigon-device-fingerprint"

RDEPENDS:${PN} = "nexigon-agent-service"

NEXIGON_HUB_URL ??= ""
NEXIGON_TOKEN ??= ""
NEXIGON_COMMANDS_ENABLED ??= "0"
NEXIGON_TERMINAL_ENABLED ??= "0"
NEXIGON_TERMINAL_USER ??= "root"
NEXIGON_AGENT_EXTRA_CONF ??= ""

do_install() {
    install -d ${D}${sysconfdir}/nexigon
    install -m 0644 ${WORKDIR}/agent.toml ${D}${sysconfdir}/nexigon/agent.toml

    sed -i "s|@@HUB_URL@@|${NEXIGON_HUB_URL}|g" ${D}${sysconfdir}/nexigon/agent.toml
    sed -i "s|@@TOKEN@@|${NEXIGON_TOKEN}|g" ${D}${sysconfdir}/nexigon/agent.toml

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

    if [ -n "${NEXIGON_AGENT_EXTRA_CONF}" ]; then
        printf '\n%b\n' "${NEXIGON_AGENT_EXTRA_CONF}" >> ${D}${sysconfdir}/nexigon/agent.toml
    fi

    install -d ${D}${libexecdir}/nexigon
    install -m 0755 ${WORKDIR}/nexigon-device-fingerprint ${D}${libexecdir}/nexigon/
}
