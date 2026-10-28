# Enable the Rugix system update integration of Nexigon Agent.
NEXIGON_SYSTEM_UPDATES ??= "rugix"

RDEPENDS:${PN}:append = "${@' rugix-ctrl nexigon-rugix-watchdog' if d.getVar('NEXIGON_SYSTEM_UPDATES') == 'rugix' else ''}"
