SUMMARY = "Nexigon OTA updates with Rugix"
DESCRIPTION = "Installs Rugix Ctrl and the commit watchdog for the Rugix system \
update integration of Nexigon Agent. The agent configuration enables the \
integration, see NEXIGON_SYSTEM_UPDATES in nexigon-agent-conf."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

ALLOW_EMPTY:${PN} = "1"
RDEPENDS:${PN} = "rugix-ctrl nexigon-rugix-watchdog nexigon-agent-conf"
