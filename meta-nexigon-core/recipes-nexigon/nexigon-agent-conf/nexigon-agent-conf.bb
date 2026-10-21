DESCRIPTION = "Nexigon Agent Configuration"
LICENSE = "Apache-2.0 & MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10 \
                    file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://agent.toml \
           file://nexigon-device-fingerprint-machine-id \
           file://nexigon-device-fingerprint-random-uuid"
S = "${UNPACKDIR}"

RDEPENDS:${PN} = "nexigon-agent-service"

# Static credentials. Without them, the agent uses the credentials saved by
# provisioning.
NEXIGON_HUB_URL ??= ""
NEXIGON_TOKEN ??= ""
# Accept a provisioning token on the local network while the device has no
# credentials. Requires empty static credentials.
NEXIGON_PROVISIONING ??= "0"
NEXIGON_COMMANDS_ENABLED ??= "0"
NEXIGON_TERMINAL_ENABLED ??= "0"
NEXIGON_TERMINAL_USER ??= "root"
NEXIGON_AGENT_SSL_DIR ??= ""
# Data directory of the agent, including the credentials saved by
# provisioning. Empty uses the agent default (/var/lib/nexigon/agent).
NEXIGON_AGENT_DATA_DIR ??= ""
NEXIGON_AGENT_EXTRA_CONF ??= ""

# Device fingerprint source:
#   "machine-id"   - uses /etc/machine-id (default)
#   "random-uuid"  - generates a persistent UUID at NEXIGON_DEVICE_FINGERPRINT_FILE
#   <path>         - path to a custom fingerprint script
NEXIGON_DEVICE_FINGERPRINT ??= ""

# Path where the random-uuid fingerprint script stores its ID.
NEXIGON_DEVICE_FINGERPRINT_FILE ??= "/var/lib/nexigon/device-fingerprint-uuid"

# System update integration of the agent:
#   ""       - no system updates (default)
#   "rugix"  - updates with Rugix Ctrl (default of meta-nexigon-rugix)
#   "rauc"   - updates with RAUC (default of meta-nexigon-rauc)
NEXIGON_SYSTEM_UPDATES ??= ""
# Default update path `<repository>/<package>/<tag>` built into the image.
# Without a repository and package, the device does not update until the
# `dev.nexigon.ota.config` device property supplies a path.
NEXIGON_OTA_REPOSITORY ??= ""
NEXIGON_OTA_PACKAGE ??= ""
NEXIGON_OTA_TAG ??= "stable"
# Time between update checks, such as "4h" or "1h 30min". Empty uses the
# agent default (4 hours).
NEXIGON_OTA_INTERVAL ??= ""
# Maximum random delay of scheduled update checks, such as "5min", which keeps
# devices from reaching Nexigon Hub at once. Empty uses the agent default
# (5 minutes).
NEXIGON_OTA_RANDOMIZED_DELAY ??= ""
# Verify Rugix bundles with the hash from the asset metadata when present.
NEXIGON_OTA_RUGIX_USE_BUNDLE_HASH ??= "0"

python do_validate_config() {
    fp = d.getVar('NEXIGON_DEVICE_FINGERPRINT')
    if not fp:
        bb.fatal('NEXIGON_DEVICE_FINGERPRINT is not set - must be "machine-id", "random-uuid", or a path to a custom script')
    if fp == 'random-uuid' and not d.getVar('NEXIGON_DEVICE_FINGERPRINT_FILE'):
        bb.fatal('NEXIGON_DEVICE_FINGERPRINT_FILE must be set when using random-uuid fingerprint')
    if bool(d.getVar('NEXIGON_HUB_URL')) != bool(d.getVar('NEXIGON_TOKEN')):
        bb.fatal('NEXIGON_HUB_URL and NEXIGON_TOKEN must be set together')
    if d.getVar('NEXIGON_PROVISIONING') not in ('0', '1'):
        bb.fatal('NEXIGON_PROVISIONING must be "0" or "1"')
    if d.getVar('NEXIGON_PROVISIONING') == '1' and d.getVar('NEXIGON_HUB_URL'):
        bb.fatal('NEXIGON_PROVISIONING requires empty NEXIGON_HUB_URL and NEXIGON_TOKEN')
    if d.getVar('NEXIGON_PROVISIONING') == '1' and '[provisioning]' in (d.getVar('NEXIGON_AGENT_EXTRA_CONF') or ''):
        bb.fatal('NEXIGON_AGENT_EXTRA_CONF must not contain [provisioning] when NEXIGON_PROVISIONING is "1"')
    updates = d.getVar('NEXIGON_SYSTEM_UPDATES')
    if updates not in ('', 'rugix', 'rauc'):
        bb.fatal('NEXIGON_SYSTEM_UPDATES must be "", "rugix", or "rauc"')
    if bool(d.getVar('NEXIGON_OTA_REPOSITORY')) != bool(d.getVar('NEXIGON_OTA_PACKAGE')):
        bb.fatal('NEXIGON_OTA_REPOSITORY and NEXIGON_OTA_PACKAGE must be set together')
    if d.getVar('NEXIGON_OTA_REPOSITORY') and not d.getVar('NEXIGON_OTA_TAG'):
        bb.fatal('NEXIGON_OTA_TAG must not be empty')
    import re
    for var in ('NEXIGON_OTA_REPOSITORY', 'NEXIGON_OTA_PACKAGE', 'NEXIGON_OTA_TAG'):
        if re.search(r'["\\/\s\x00-\x1f]', d.getVar(var) or ''):
            bb.fatal('%s must not contain quotes, backslashes, slashes, or whitespace' % var)
    if nexigon_timespan_secs(d.getVar('NEXIGON_OTA_INTERVAL')) == '0':
        bb.fatal('NEXIGON_OTA_INTERVAL must be positive')
    nexigon_timespan_secs(d.getVar('NEXIGON_OTA_RANDOMIZED_DELAY'))
}
addtask validate_config before do_install

# Convert a time span like "4h" or "1h 30min" to seconds, keeping it empty.
def nexigon_timespan_secs(span):
    import re
    units = {'': 1, 's': 1, 'sec': 1, 'm': 60, 'min': 60, 'h': 3600, 'd': 86400}
    parts = (span or '').split()
    total = 0
    for part in parts:
        match = re.fullmatch(r'([0-9]+)(s|sec|m|min|h|d)?', part)
        if not match:
            bb.fatal('invalid time span "%s"' % span)
        total += int(match.group(1)) * units[match.group(2) or '']
    return str(total) if parts else ''

NEXIGON_OTA_INTERVAL_SECS = "${@nexigon_timespan_secs(d.getVar('NEXIGON_OTA_INTERVAL'))}"
NEXIGON_OTA_RANDOMIZED_DELAY_SECS = "${@nexigon_timespan_secs(d.getVar('NEXIGON_OTA_RANDOMIZED_DELAY'))}"

do_install() {
    install -d ${D}${sysconfdir}/nexigon
    install -m 0644 ${UNPACKDIR}/agent.toml ${D}${sysconfdir}/nexigon/agent.toml

    if [ -n "${NEXIGON_HUB_URL}" ]; then
        cat >> ${D}${sysconfdir}/nexigon/agent.toml <<EOF
hub-url = "${NEXIGON_HUB_URL}"
token = "${NEXIGON_TOKEN}"
EOF
    fi

    # Directories that the agent needs mounted before it starts.
    mounts=""
    if [ -n "${NEXIGON_AGENT_SSL_DIR}" ]; then
        cat >> ${D}${sysconfdir}/nexigon/agent.toml <<EOF
ssl-cert = "${NEXIGON_AGENT_SSL_DIR}/cert.pem"
ssl-key = "${NEXIGON_AGENT_SSL_DIR}/key.pem"
EOF
        mounts="$mounts ${NEXIGON_AGENT_SSL_DIR}"
    fi
    if [ -n "${NEXIGON_AGENT_DATA_DIR}" ]; then
        echo "data-path = \"${NEXIGON_AGENT_DATA_DIR}\"" >> ${D}${sysconfdir}/nexigon/agent.toml
        mounts="$mounts ${NEXIGON_AGENT_DATA_DIR}"
    fi
    if [ -n "$mounts" ]; then
        install -d ${D}${systemd_system_unitdir}/nexigon-agent.service.d
        printf '[Unit]\nRequiresMountsFor=%s\n' "$mounts" \
            > ${D}${systemd_system_unitdir}/nexigon-agent.service.d/persistent-dirs.conf
    fi

    if [ -n "${NEXIGON_AGENT_EXTRA_CONF}" ]; then
        printf '\n%b\n' "${NEXIGON_AGENT_EXTRA_CONF}" >> ${D}${sysconfdir}/nexigon/agent.toml
    fi

    if [ "${NEXIGON_PROVISIONING}" = "1" ]; then
        printf '\n[provisioning]\nenabled = true\n' >> ${D}${sysconfdir}/nexigon/agent.toml
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

    if [ -n "${NEXIGON_SYSTEM_UPDATES}" ]; then
        printf '\n[integrations.%s.system-updates]\nenabled = true\n' "${NEXIGON_SYSTEM_UPDATES}" \
            >> ${D}${sysconfdir}/nexigon/agent.toml
        if [ -n "${NEXIGON_OTA_REPOSITORY}" ]; then
            echo "path = \"${NEXIGON_OTA_REPOSITORY}/${NEXIGON_OTA_PACKAGE}/${NEXIGON_OTA_TAG}\"" \
                >> ${D}${sysconfdir}/nexigon/agent.toml
        fi
        if [ -n "${NEXIGON_OTA_INTERVAL_SECS}" ]; then
            echo "check-interval-secs = ${NEXIGON_OTA_INTERVAL_SECS}" >> ${D}${sysconfdir}/nexigon/agent.toml
        fi
        if [ -n "${NEXIGON_OTA_RANDOMIZED_DELAY_SECS}" ]; then
            echo "check-jitter-secs = ${NEXIGON_OTA_RANDOMIZED_DELAY_SECS}" >> ${D}${sysconfdir}/nexigon/agent.toml
        fi
        if [ "${NEXIGON_SYSTEM_UPDATES}" = "rugix" ] && [ "${NEXIGON_OTA_RUGIX_USE_BUNDLE_HASH}" = "1" ]; then
            echo "use-bundle-hash = true" >> ${D}${sysconfdir}/nexigon/agent.toml
        fi
    fi

    install -d ${D}${libexecdir}/nexigon
    if [ "${NEXIGON_DEVICE_FINGERPRINT}" = "machine-id" ]; then
        install -m 0755 ${UNPACKDIR}/nexigon-device-fingerprint-machine-id \
            ${D}${libexecdir}/nexigon/nexigon-device-fingerprint
        sed -i "s|@@FINGERPRINT_SCRIPT@@|${libexecdir}/nexigon/nexigon-device-fingerprint|g" \
            ${D}${sysconfdir}/nexigon/agent.toml
    elif [ "${NEXIGON_DEVICE_FINGERPRINT}" = "random-uuid" ]; then
        install -m 0755 ${UNPACKDIR}/nexigon-device-fingerprint-random-uuid \
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
