DESCRIPTION = "Nexigon Agent"
LICENSE = "CLOSED"

RDEPENDS:${PN} = ""

# The release binaries are already stripped.
INSANE_SKIP:${PN} = "already-stripped"

SRC_URI:append:x86_64 = " https://downloads.nexigon.dev/nexigon-agent/v${AGENT_VERSION}/assets/aarch64-unknown-linux-musl/nexigon-agent;name=x86_64"
SRC_URI:append:aarch64 = " https://downloads.nexigon.dev/nexigon-agent/v${AGENT_VERSION}/assets/aarch64-unknown-linux-musl/nexigon-agent;name=aarch64"

S = "${WORKDIR}"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${S}/nexigon-agent ${D}${bindir}/nexigon-agent
}
