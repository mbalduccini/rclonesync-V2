#!/usr/bin/env python3
"""
Read a file of pathnames (one per line) and either:
- show-invalid: print those whose containing directory does NOT exist locally
- remove-invalid: print those whose containing directory DOES exist locally

The local root is fixed as:
    $HOME/storage/shared/AUTOSYNC/Google Drive/
"""

import os
import sys

LOCAL_ROOT = os.path.expanduser("~/storage/shared/AUTOSYNC/Google Drive/")

def usage():
    print(f"Usage: {sys.argv[0]} [show-invalid | remove-invalid] <pathlist.txt>")
    sys.exit(1)

def parent_exists_local(rel_path: str) -> bool:
    """Return True if the parent directory for rel_path exists under LOCAL_ROOT."""
    full_path = os.path.normpath(os.path.join(LOCAL_ROOT, rel_path))
    parent = os.path.dirname(full_path)
    return os.path.isdir(parent)

def main():
    if len(sys.argv) != 3:
        usage()

    command = sys.argv[1]
    list_file = sys.argv[2]

    if command not in ("show-invalid", "remove-invalid"):
        usage()

    try:
        with open(list_file, "r", encoding="utf-8") as f:
            paths = [line.strip() for line in f if line.strip()]
    except OSError as e:
        print(f"Error reading {list_file}: {e}", file=sys.stderr)
        sys.exit(2)

    show_invalid = (command == "show-invalid")

    any_output = False
    for rel in paths:
        exists = parent_exists_local(rel)
        if show_invalid and not exists:
            print(rel)
            any_output = True
        elif not show_invalid and exists:
            print(rel)
            any_output = True

    if not any_output:
        # Silent success if nothing to print
        pass

if __name__ == "__main__":
    main()
