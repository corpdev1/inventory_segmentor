"""Recursive Google Drive folder listing (metadata)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

FOLDER_MIME = "application/vnd.google-apps.folder"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"

_FOLDER_ID_IN_URL = re.compile(r"/folders/([a-zA-Z0-9_-]+)")

# Fields requested from the Drive API per file entry.
# Includes owners and lastModifyingUser for attribution columns in the XLSX.
_LIST_FIELDS = (
    "nextPageToken, files("
    "id, name, mimeType, modifiedTime, size, "
    "webViewLink, md5Checksum, shortcutDetails, driveId, "
    "owners(emailAddress), lastModifyingUser(emailAddress)"
    ")"
)


def normalize_folder_id(raw: str) -> str:
    """Accept a raw folder ID or a ``drive.google.com`` folder URL.

    ``my-drive`` / ``root`` and common "My Drive" URLs resolve to the API root
    folder id ``root``.
    """
    s = (raw or "").strip()
    low = s.lower()
    if low in ("root", "my-drive", "mydrive"):
        return "root"
    if "drive.google.com" in low and "my-drive" in low:
        return "root"
    m = _FOLDER_ID_IN_URL.search(s)
    if m:
        return m.group(1)
    return s.split("?")[0].split("/")[0]


def _list_children(service, folder_id: str) -> list[dict[str, Any]]:
    q = f"'{folder_id}' in parents and trashed = false"
    out: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        resp = (
            service.files()
            .list(
                q=q,
                pageSize=200,
                fields=_LIST_FIELDS,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        out.extend(resp.get("files") or [])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def _row_from_file(f: dict[str, Any], path: str, *, is_folder: bool, is_shortcut: bool) -> dict[str, Any]:
    """Build a scan row dict from a Drive API file object."""
    return {
        "drive_file_id": f.get("id"),
        "path": path,
        "name": f.get("name") or "",
        "mime_type": f.get("mimeType") or "",
        "modified_time": f.get("modifiedTime"),
        "size_bytes": f.get("size"),
        "web_view_link": f.get("webViewLink"),
        "md5_checksum": f.get("md5Checksum"),
        "is_folder": is_folder,
        "is_shortcut": is_shortcut,
        "shortcut_target_id": (f.get("shortcutDetails") or {}).get("targetId"),
        # Attribution: first owner email; empty string when API doesn't return it.
        "owner_email": ((f.get("owners") or [{}])[0] or {}).get("emailAddress") or "",
        "last_modified_by": (f.get("lastModifyingUser") or {}).get("emailAddress") or "",
    }


def walk_drive_folder(
    service,
    folder_id: str,
    *,
    path_prefix: str = "",
    include_folders: bool = False,
    max_files: int | None = None,
    progress_log: Callable[[str], None] | None = None,
    progress_every: int = 500,
    scan_cache_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Depth-first walk from ``folder_id``; return flat rows (files and optionally folders).

    Each row: ``drive_file_id``, ``path``, ``name``, ``mime_type``, ``modified_time``,
    ``size_bytes``, ``web_view_link``, ``md5_checksum``, ``is_folder``, ``is_shortcut``,
    ``owner_email``, ``last_modified_by``.

    scan_cache_path
        If set, the complete walk result is saved to this JSONL file after the walk
        completes. On subsequent calls with the same path, the cache is loaded and
        the Drive API walk is skipped entirely — useful for large drives where the walk
        takes minutes and the downstream pipeline is what crashes/restarts.
        Delete the cache file to force a fresh walk.

    If ``max_files`` is set, stop after that many file rows (non-folder rows, including
    shortcuts). Folder rows from ``include_folders`` do not count toward the limit.

    If ``progress_log`` is set, it is called every ``progress_every`` **file** rows
    (shortcuts and regular files; not folder-only rows) with a short status line.
    """
    # --- cache load ---
    cache_path: Path | None = Path(scan_cache_path) if scan_cache_path else None
    if cache_path is not None and cache_path.is_file() and cache_path.stat().st_size > 0:
        rows: list[dict[str, Any]] = []
        with cache_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
        if rows:
            if progress_log:
                progress_log(f"[scan_cache] loaded {len(rows)} rows from {cache_path}")
            if max_files is not None:
                file_rows = [r for r in rows if not r.get("is_folder")]
                folder_rows = [r for r in rows if r.get("is_folder")]
                rows = (folder_rows if include_folders else []) + file_rows[:max_files]
            return rows

    # --- live walk ---
    folder_id = normalize_folder_id(folder_id)
    rows = []
    file_rows = 0
    stop = False

    def _emit_progress(path_hint: str) -> None:
        if progress_log and file_rows > 0 and file_rows % progress_every == 0:
            progress_log(f"files={file_rows} last={path_hint[:240]}")

    def visit(fid: str, rel_path: str) -> None:
        nonlocal file_rows, stop
        if stop:
            return
        children = _list_children(service, fid)
        # Stable order: folders first, then files, by name
        children.sort(
            key=lambda f: (0 if f.get("mimeType") == FOLDER_MIME else 1, (f.get("name") or "").lower())
        )
        for f in children:
            if stop:
                break
            name = f.get("name") or ""
            mid = f.get("mimeType") or ""
            sub = f"{rel_path}/{name}".strip("/") if rel_path else name
            is_folder = mid == FOLDER_MIME
            is_shortcut = mid == SHORTCUT_MIME

            if is_shortcut:
                rows.append(_row_from_file(f, sub, is_folder=False, is_shortcut=True))
                file_rows += 1
                _emit_progress(sub)
                if max_files is not None and file_rows >= max_files:
                    stop = True
                continue

            if is_folder:
                if include_folders:
                    rows.append(_row_from_file(f, sub, is_folder=True, is_shortcut=False))
                visit(f["id"], sub)
                continue

            rows.append(_row_from_file(f, sub, is_folder=False, is_shortcut=False))
            file_rows += 1
            _emit_progress(sub)
            if max_files is not None and file_rows >= max_files:
                stop = True
                return

    visit(folder_id, path_prefix)

    # --- cache save (only when walk completed without a max_files cap, so the cache is complete) ---
    if cache_path is not None and not stop:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        if progress_log:
            progress_log(f"[scan_cache] saved {len(rows)} rows to {cache_path}")

    return rows
