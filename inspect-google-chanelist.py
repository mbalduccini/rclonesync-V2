#!/usr/bin/env python3
"""
Display Google Drive changes with resolved paths (parent chain -> path),
using the SAME credential method as your program (rclone.conf).

No side effects (no merges, no writes).

Usage:
  python show_changes_with_paths.py \
    --config /path/to/rclone.conf \
    --path "MyDrive:" \
    --token <START_PAGE_TOKEN> \
    [--page-size 1000] [--include-removed] [--all-space] [--verbose]
"""

import argparse
import configparser
import json
import logging
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# -------- rclone.conf-based credential loader (same approach as your program) --------

_aux_service = {}
def googleapi_service(path: str, rcconfig: str):
    """
    Build a Drive v3 client from rclone.conf (supports crypt remotes by following 'remote=').
    Returns (service, original_path_string) or (None,None) on failure.
    """
    global _aux_service
    key = path.split(":", 1)[0]
    if key in _aux_service:
        return _aux_service[key], path

    if not os.path.exists(rcconfig):
        logging.error("rclone config not found: %s", rcconfig)
        return None, None

    c = configparser.ConfigParser()
    with open(rcconfig, "r") as fp:
        c.read_file(fp)

    # Follow crypt -> underlying drive
    if c[key].get("type") == "crypt":
        wrapped = c[key]["remote"]
        return googleapi_service(wrapped, rcconfig)

    if c[key].get("type") != "drive":
        logging.error("Remote [%s] is type '%s', expected 'drive'.", key, c[key].get("type"))
        return None, None

    tok = json.loads(c[key]["token"])
    data = {
        "token": tok.get("access_token"),
        "refresh_token": tok.get("refresh_token"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": c[key].get("client_id"),
        "client_secret": c[key].get("client_secret"),
        "expiry": tok.get("expiry"),
    }

    scopes = ["https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_authorized_user_info(data, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            logging.error("Unable to create/refresh credentials from %s", rcconfig)
            return None, None

    service = build("drive", "v3", credentials=creds, static_discovery=False)
    _aux_service[key] = service
    return service, path

# -------- Extracted path resolution helpers (trimmed from your code) --------

_ID_CACHE = {}  # id -> (name, parents)

def getPath(service, f):
    """
    Build parent chain up to root for file `f` (expects fields id,name,parents).
    Returns a list like [{'id': <id>, 'name': <name>}, ... root], or [None, True/False] on specific errors.
    """
    parent = f.get("parents")
    path = [{'id': f.get('id'), 'name': f.get('name')}]
    if parent:
        try:
            while True:
                old_id = parent[0]
                if old_id in _ID_CACHE:
                    name, parent = _ID_CACHE[old_id]
                    path.append({'id': parent[0] if parent else None, 'name': name})
                else:
                    folder = service.files().get(
                        fileId=old_id, fields='id, name, parents'
                    ).execute()
                    parent = folder.get('parents')
                    if parent is None:
                        break
                    path.append({'id': parent[0], 'name': folder.get('name')})
                    _ID_CACHE[old_id] = (folder.get('name'), parent)
        except HttpError as e:
            logging.error("getPath(): HTTP error; file info was: %s", f)
            logging.info("message: %s", e)
            return [None, True]  # keep going
        except Exception as e:
            logging.error("getPath(): network error; file info was: %s", f)
            logging.info("message: %s", e)
            return [None, False]  # stop
    path.reverse()
    return path

def pathToStr(p):
    if p is None:
        return None
    if len(p) == 2 and p[0] is None:  # special error sentinel from getPath()
        return p
    return "/".join(d['name'] for d in list(p) if d.get('name'))

def _escape_for_q(s: str) -> str:
    # Drive query literals use single quotes; escape embedded single quotes.
    return s.replace("'", "\\'")

def file_exists(service, folder_id: str, name: str, include_all_drives: bool = True) -> bool:
    """True if a non-trashed item with this name exists directly under folder_id."""
    q = (
        f"'{folder_id}' in parents and "
        f"name = '{_escape_for_q(name)}' and "
        f"trashed = false"
    )
    resp = service.files().list(
        q=q,
        fields="files(id)",            # minimal
        pageSize=1,                    # we only care if at least one exists
        includeItemsFromAllDrives=include_all_drives,
        supportsAllDrives=include_all_drives,
    ).execute()
    return bool(resp.get("files"))

# -------- Change listing (adds resolvedPath + conflict check) --------

def list_changes_only(start_token: str,
                      path: str,
                      rcconfig: str,
                      page_size: int = 1000,
                      include_removed: bool = False,
                      restrict_to_my_drive: bool = True):
    """
    List Google Drive changes, adding:
      - resolvedPath: human path built from parents
      - checkReason: 'trashed' | 'removed' when we perform a live-path check
      - livePathExists: True/False/None (None = not enough metadata to check)
      - conflict: True/False/None (True = says trashed/removed but a live path exists)
    No side effects.
    """
    service, _ = googleapi_service(path, rcconfig)
    if service is None:
        sys.exit(1)

    page_token = start_token
    saved_start_page_token = None

    try:
        while page_token is not None:
            resp = service.changes().list(
                pageToken=page_token,
                spaces='drive',
                restrictToMyDrive=restrict_to_my_drive,
                includeRemoved=include_removed,
                pageSize=page_size,
                fields=(
                    "nextPageToken,newStartPageToken,"
                    "changes(fileId,removed,"
                    "        file(id,name,trashed,mimeType,md5Checksum,parents))"
                ),
            ).execute()

            for ch in resp.get("changes", []):
                f = ch.get("file") or {}
                # Resolve parents -> path
                p = getPath(service, f) if f else None
                path_str = pathToStr(p)

                # Prepare output
                out = dict(ch)  # shallow copy of change dict
                out["resolvedPath"] = path_str

                # Decide if we should run the existence check
                check_reason = None
                if f and f.get("trashed"):
                    check_reason = "trashed"
                elif ch.get("removed"):
                    check_reason = "removed"

                live_exists = None
                if check_reason:
                    # Try to get (parentId, name) for a live-path existence check.
                    parent_id = None
                    name = None

                    if f:
                        name = f.get("name")
                        # Prefer direct parents from the change's file section
                        if f.get("parents"):
                            parent_id = f["parents"][0]
                        # Fallback: infer parent from resolved path chain if available
                        if not parent_id and isinstance(p, list) and len(p) >= 2:
                            parent = p[-2]  # [..., parent, file]
                            parent_id = parent.get("id")

                    if parent_id and name:
                        live_exists = file_exists(
                            service,
                            parent_id,
                            name,
                            include_all_drives=(not restrict_to_my_drive),
                        )

                if check_reason:
                    out["checkReason"] = check_reason
                    out["livePathExists"] = live_exists
                    out["conflict"] = (live_exists is True)

                print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))

            if "newStartPageToken" in resp:
                saved_start_page_token = resp["newStartPageToken"]
                print(f"# newStartPageToken={saved_start_page_token}")

            page_token = resp.get("nextPageToken")
            print(f"# nextPageToken={page_token}")

    except HttpError as e:
        logging.error("HTTP error listing changes: %s", e)
        sys.exit(1)
    except Exception as e:
        logging.error("Error listing changes: %s", e)
        sys.exit(1)

    return saved_start_page_token

# -------- CLI --------

def main():
    ap = argparse.ArgumentParser(description="Display Drive changes with resolved paths (no side effects).")
    ap.add_argument("--config", required=True, help="Path to rclone.conf")
    ap.add_argument("--path",   required=True, help="Drive remote, e.g. 'MyDrive:' (crypt remotes supported)")
    ap.add_argument("--token",  required=True, help="Start page token to begin from")
    ap.add_argument("--page-size", type=int, default=1000, help="changes.list page size (default 1000)")
    ap.add_argument("--include-removed", action="store_true",
                    help="Include removed/trashed items (default: false)")
    ap.add_argument("--all-space", action="store_true",
                    help="Don’t restrict to My Drive (default is restrict)")
    ap.add_argument("--verbose", action="store_true", help="Enable INFO logging")
    args = ap.parse_args()

    logging.basicConfig(level=(logging.INFO if args.verbose else logging.WARNING),
                        format="%(message)s")

    final_token = list_changes_only(
        start_token=args.token,
        path=args.path,
        rcconfig=args.config,
        page_size=args.page_size,
        include_removed=args.include_removed,
        restrict_to_my_drive=(not args.all_space),
    )

    if final_token:
        print(f"# FINAL newStartPageToken={final_token}")

if __name__ == "__main__":
    main()
