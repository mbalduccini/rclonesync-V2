#! /bin/bash

cat <<EOF >/sdcard/Documents/setup-rclonesync.sh
cd /data/local/tmp/rclone-stuff/PYTHON
. ./env.sh
export PATH=/data/local/tmp/rclone-stuff:/data/local/tmp/rclone-stuff/rclonesync-V2:\$PATH
cd /data/local/tmp/rclone-stuff/rclonesync-V2
while [ 1 == 1 ]; do python3 ./rclonesync "GDrive:/" "/sdcard/AUTOSYNC/Google Drive/" -f ../rclonesync-filter.txt -vv --no-check-sync ; sleep 10m ; done
EOF
#adb shell "system/bin/sh -T- /sdcard/Documents/setup-rclonesync.sh </dev/null &>/dev/null &"
adb shell "system/bin/sh /sdcard/Documents/setup-rclonesync.sh"
