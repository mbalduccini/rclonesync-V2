#!/usr/bin/env python3
"""
Copy a list of files from Google Drive (remote 'GDrive:') to the local root.

- Input file: one relative pathname per line (relative to the Drive root you used with `rclone lsf`)
- Only those files are copied (using --files-from-raw)
- Supports --dry-run to preview operations

Local root is fixed to: ~/storage/shared/AUTOSYNC/Google Drive/
"""

import argparse
import os
import subprocess
import sys

LOCAL_ROOT = os.path.expanduser("~/storage/shared/AUTOSYNC/Google Drive/")
REMOTE = "GDrive:"

def parse_args():
    p = argparse.ArgumentParser(description="Copy listed files from GDrive: to local root using rclone.")
    p.add_argument("list_file", help="Path to file containing relative pathnames (one per line).")
    p.add_argument("--dry-run", action="store_true", help="Run rclone in dry-run mode (no changes).")
    p.add_argument("--rclone", default="rclone", help="Path to rclone binary (default: rclone in PATH).")
    p.add_argument("--config", default=None, help="Optional path to rclone.conf.")
    p.add_argument("-v", "--verbose", action="count", default=0, help="Increase rclone verbosity (repeat for more).")
    return p.parse_args()

def main():
    args = parse_args()

    if not os.path.isfile(args.list_file):
        print(f"ERROR: list file not found: {args.list_file}", file=sys.stderr)
        sys.exit(2)

    if not os.path.isdir(LOCAL_ROOT):
        print(f"ERROR: local root does not exist: {LOCAL_ROOT}", file=sys.stderr)
        sys.exit(2)

    # Build rclone command
    cmd = [args.rclone, "copy", REMOTE, LOCAL_ROOT, "--files-from-raw", args.list_file]

    if args.config:
        cmd.extend(["--config", args.config])

    if args.dry_run:
        cmd.append("--dry-run")

    # Add verbosity flags to rclone if requested
    if args.verbose:
        cmd.extend(["-" + "v" * args.verbose])

#    # Nice to have for visibility
#    cmd.append("--progress")

    # Execute
    try:
        print("Running:", " ".join(f"'{c}'" if " " in c else c for c in cmd))
        rc = subprocess.call(cmd)
    except FileNotFoundError:
        print(f"ERROR: rclone not found at '{args.rclone}'.", file=sys.stderr)
        sys.exit(127)

    sys.exit(rc)

if __name__ == "__main__":
    main()
