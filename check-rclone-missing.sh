#!/usr/bin/env bash
set -euo pipefail

# --- CONFIGURATION ---
# Path to your local folder (note the spaces)
LOCAL_DIR="$HOME/storage/shared/AUTOSYNC/Google Drive/MOBILE/OBSIDIAN NOTES"
#LOCAL_DIR="$HOME/storage/shared/AUTOSYNC/Google Drive/"
#LOCAL_DIR="$HOME/storage/shared/AUTOSYNC/SJU Vault/"

# rclone remote path and the rclone.conf location
RCLONE_CONF="$HOME/storage/shared/Android/media/net.asklab.gdrivesmartsync/rclone.conf"
#
REMOTE="GDrive:/MOBILE/OBSIDIAN NOTES"
#REMOTE="GDrive:"
#REMOTE="gsecure:"

# Temporary files for listings
LOCAL_LIST="$(mktemp)"
REMOTE_LIST="$(mktemp)"
LOCAL_SORTED="$(mktemp)"
REMOTE_SORTED="$(mktemp)"

cleanup() {
  rm -f "$LOCAL_LIST" "$REMOTE_LIST" "$LOCAL_SORTED" "$REMOTE_SORTED"
}
trap cleanup EXIT

# 1. List all files under the remote (only file-paths, one per line)
rclone lsf \
  --config="$RCLONE_CONF" \
  --recursive \
  --files-only \
  "$REMOTE" > "$REMOTE_LIST"

# 2. List all files under the local directory (relative paths, one per line)
#    - 'find . -type f' will output './path/to/file', so we strip the leading './'
cd "$LOCAL_DIR"
find . -type f \
  | sed 's|^\./||' \
  > "$LOCAL_LIST"

# 3. Sort both lists (comm requires sorted input)
sort "$LOCAL_LIST" > "$LOCAL_SORTED"
sort "$REMOTE_LIST" > "$REMOTE_SORTED"

# 4. Use `comm` to compare:
#    - Files only in REMOTE (i.e. in remote_sorted, not in local_sorted): comm -23
#    - Files only in LOCAL  (i.e. in local_sorted, not in remote_sorted): comm -13

echo "===== Files present on REMOTE but MISSING LOCALLY ====="
comm -23 "$REMOTE_SORTED" "$LOCAL_SORTED" || true

echo
echo "===== Files present LOCALLY but MISSING on REMOTE ====="
comm -13 "$REMOTE_SORTED" "$LOCAL_SORTED" || true
