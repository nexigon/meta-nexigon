# Mount the FAT partition with the boot counters and the data partition. The
# partition names come from the wks file of this layer.
do_install:append() {
    install -d ${D}/uboot ${D}/data
    cat >> ${D}${sysconfdir}/fstab <<EOF
/dev/disk/by-partlabel/uboot /uboot vfat defaults 0 0
/dev/disk/by-partlabel/data /data ext4 defaults 0 0
EOF
}

FILES:${PN} += "/uboot /data"
