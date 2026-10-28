# Enable the RAUC system update integration of Nexigon Agent.
NEXIGON_SYSTEM_UPDATES ??= "rauc"

RDEPENDS:${PN}:append = "${@' rauc' if d.getVar('NEXIGON_SYSTEM_UPDATES') == 'rauc' else ''}"
