# Deploys the os-release file to DEPLOY_DIR_IMAGE so that release tooling
# can read IMAGE_ID and other fields without extracting the rootfs.

nexigon_deploy_release_info() {
    if [ -f ${IMAGE_ROOTFS}${sysconfdir}/os-release ]; then
        install -m 0644 ${IMAGE_ROOTFS}${sysconfdir}/os-release \
            ${IMGDEPLOYDIR}/os-release
    fi
}

IMAGE_POSTPROCESS_COMMAND += "nexigon_deploy_release_info;"
