set dotenv-load

export KAS_CONTAINER_ENGINE := env("KAS_CONTAINER_ENGINE", "podman")
export KAS_WORK_DIR := env("KAS_WORK_DIR", justfile_directory() + "/_kas")
export KAS_BUILD_DIR := env("KAS_BUILD_DIR", justfile_directory() + "/build")
export SSTATE_DIR := env("SSTATE_DIR", justfile_directory() + "/cache/sstate-cache")
export DL_DIR := env("DL_DIR", justfile_directory() + "/cache/downloads")

_uv_run := "uv run --with 'rugix-testkit @ git+https://github.com/rugix/rugix-testkit.git' --with 'nexigon-hub-sdk @ git+https://github.com/silitics/nexigon.git#subdirectory=sdks/python' --with pytest --with pytest-timeout"

_kas_env := "-e IMAGE_VERSION -e NEXIGON_HUB_URL -e NEXIGON_TOKEN -e NEXIGON_OTA_REPOSITORY -e NEXIGON_OTA_PACKAGE"

_deploy_dir := KAS_BUILD_DIR + "/tmp/deploy/images"

_ssh_opts := "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

[private]
_default:
    @just --list

# Remove all build artifacts.
clean:
    rm -rf "{{KAS_WORK_DIR}}" "{{KAS_BUILD_DIR}}"

# Remove all build artifacts and the cache.
clean-all:
    @just clean
    rm -rf "{{justfile_directory()}}/cache"

# Run an arbitrary kas-container command.
[positional-arguments]
kas *args:
    mkdir -p "{{KAS_WORK_DIR}}"
    mkdir -p "{{KAS_BUILD_DIR}}"
    kas-container --runtime-args "{{_kas_env}}" "$@"

# Build a Yocto image with kas-container.
[positional-arguments]
build *args:
    mkdir -p "{{KAS_WORK_DIR}}"
    mkdir -p "{{KAS_BUILD_DIR}}"
    kas-container --runtime-args "{{_kas_env}}" build "$@"

# Run the QEMU x86-64 Rugix image.
[positional-arguments]
run-qemu-x86_64 *args:
    {{ _uv_run }} rugix-testkit run --arch x86_64 --ssh-port 2222 \
        --drive {{ _deploy_dir }}/qemux86-64/core-image-minimal-qemux86-64.rootfs.wic,overlay=true,size=16G \
        --pflash {{ _deploy_dir }}/qemux86-64/ovmf.code.qcow2,format=qcow2,readonly=true \
        --pflash {{ _deploy_dir }}/qemux86-64/ovmf.vars.qcow2,format=qcow2 \
        "$@"

# SSH into a running QEMU VM.
ssh-qemu:
    ssh {{ _ssh_opts }} -p 2222 root@localhost

# Copy a file into a running QEMU VM.
scp-qemu file dest="/root":
    scp {{ _ssh_opts }} -P 2222 "{{file}}" "root@localhost:{{dest}}"

# Run all integration tests.
[positional-arguments]
test *args:
    {{ _uv_run }} pytest tests/ "$@"
