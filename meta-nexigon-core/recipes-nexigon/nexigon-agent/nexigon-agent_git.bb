# The `main` branch of the layer builds the agent from the `main` branch of
# nexigon/nexigon, so that the examples use the latest agent. The version sorts
# after the release recipe, which `PREFERRED_VERSION_nexigon-agent` selects.
PV = "0.6.0+git"
SRCREV = "${AUTOREV}"

require nexigon-agent.inc
