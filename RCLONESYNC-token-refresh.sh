#! /bin/bash

FILE="/sdcard/Documents/rclonesync-token-refresh.sh"
cat <<EOF >"$FILE"
cd /data/local/tmp/rclone-stuff/PYTHON
. ./env.sh
export PATH=/data/local/tmp/rclone-stuff:/data/local/tmp/rclone-stuff/rclonesync-V2:\$PATH
cd /data/local/tmp/rclone-stuff/rclonesync-V2
rclone config reconnect "GDrive:/"
EOF
#adb shell "system/bin/sh -T- /sdcard/Documents/setup-rclonesync.sh </dev/null &>/dev/null &"
adb shell "system/bin/sh $FILE"
