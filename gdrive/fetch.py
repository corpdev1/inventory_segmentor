"""Download or export Google Drive files to a local temp path (quality ingest pipeline)."""

from __future__ import annotations

import io
import random
import time
from pathlib import Path
from typing import Any

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# Native Google files: export MIME (not get_media).
_GOOGLE_EXPORT_MIME: dict[str, str] = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
    "application/vnd.google-apps.drawing": "image/png",
}

# Skip these in the pipeline (no sensible single-file export for our extractors).
_GOOGLE_SKIP_MIME: frozenset[str] = frozenset(
    {
        "application/vnd.google-apps.folder",
        "application/vnd.google-apps.form",
        "application/vnd.google-apps.shortcut",
        "application/vnd.google-apps.map",
        "application/vnd.google-apps.site",
    }
)

# Binary formats where downloading yields no classification signal beyond filename/path.
# At 1TB scale, skipping these saves the vast majority of bandwidth.
_BINARY_SKIP_MIME_EXACT: frozenset[str] = frozenset(
    {
        "application/octet-stream",
        "application/zip",
        "application/x-zip-compressed",
        "application/x-tar",
        "application/x-gzip",
        "application/x-7z-compressed",
        "application/x-rar-compressed",
        "application/vnd.google-apps.drawing",
        # Creative tools
        "image/vnd.adobe.photoshop",
        "application/x-photoshop",
        "application/illustrator",
        # Executables / installers
        "application/x-msdownload",
        "application/x-apple-diskimage",
    }
)

# Mime-type prefixes that are always binary-skip regardless of subtype.
_BINARY_SKIP_PREFIXES: tuple[str, ...] = ("image/", "video/", "audio/")


def is_binary_skip_mime(mime_type: str) -> bool:
    """Return True for file types where downloading adds no classification value.

    These are classified from filename + path alone (metadata-only path in the
    1TB pipeline). This avoids downloading images, video, audio, and other binary
    blobs that provide no textual evidence for the LLM classifier.
    """
    if not mime_type:
        return False
    if mime_type in _BINARY_SKIP_MIME_EXACT:
        return True
    for prefix in _BINARY_SKIP_PREFIXES:
        if mime_type.startswith(prefix):
            return True
    return False


def _sleep_backoff(attempt: int, err: HttpError) -> None:
    if err.resp.status not in (403, 429, 500, 503):
        return
    base = 0.75 * (2**attempt)
    jitter = random.uniform(0.0, base * 0.25)
    time.sleep(min(120.0, base + jitter))


def _suffix_for_export(export_mime: str, display_name: str) -> str:
    ext = Path(display_name).suffix.lower()
    if export_mime == "text/plain":
        return ".txt" if ext not in (".txt", ".md", ".csv") else ext
    if export_mime == "text/csv":
        return ".csv"
    if export_mime == "image/png":
        return ".png"
    return ext or ".bin"


def suggested_local_suffix(mime_type: str, display_name: str) -> str:
    """File suffix for a temp download path (so extractors pick the right parser)."""
    export_mime = _GOOGLE_EXPORT_MIME.get(mime_type)
    if export_mime is not None:
        return _suffix_for_export(export_mime, display_name)
    ext = Path(display_name).suffix.lower()
    if ext:
        return ext
    if mime_type == "image/jpeg":
        return ".jpg"
    if mime_type == "image/png":
        return ".png"
    return ".bin"


def fetch_drive_file_to_path(
    service: Any,
    *,
    file_id: str,
    mime_type: str,
    display_name: str,
    dest: Path,
    max_retries: int = 8,
    max_export_bytes: int | None = None,
) -> str | None:
    """Write file bytes to ``dest`` (parent must exist). Returns error message or None on success.

    max_export_bytes
        When set, the written file is truncated to this many bytes after download.
        Useful in the 1TB pipeline where only a leading snippet is needed for
        classification — avoids storing/processing gigabytes of content per file.
        Only applied to Google Workspace exports (text/plain, text/csv) and binary
        downloads alike. For Workspace docs this is lossless for snippet extraction
        because extractors read from the start of the file.
    """
    if mime_type in _GOOGLE_SKIP_MIME:
        return f"unsupported_or_non_file_mime:{mime_type}"

    export_mime = _GOOGLE_EXPORT_MIME.get(mime_type)

    last_err: HttpError | None = None
    for attempt in range(max_retries + 1):
        fh = io.BytesIO()
        if export_mime is not None:
            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        chunksize = max(max_export_bytes, 8192) if max_export_bytes is not None else 1024 * 1024
        downloader = MediaIoBaseDownload(fh, request, chunksize=chunksize)
        try:
            done = False
            while not done:
                status, done = downloader.next_chunk()
                # Early-stop the download once we have enough bytes for a snippet.
                if max_export_bytes is not None and fh.tell() >= max_export_bytes:
                    break
            data = fh.getvalue()
            if max_export_bytes is not None:
                data = data[:max_export_bytes]
            dest.write_bytes(data)
            return None
        except HttpError as e:
            last_err = e
            if attempt >= max_retries:
                return f"HttpError {e.resp.status}: {e}"
            _sleep_backoff(attempt, e)
        except OSError as e:
            return f"OSError: {e}"
    return str(last_err) if last_err else "unknown_error"


def resolve_shortcut_target(service: Any, target_id: str) -> dict[str, Any] | None:
    """Return files().get fields for shortcut target, or None."""
    try:
        return (
            service.files()
            .get(
                fileId=target_id,
                fields="id,name,mimeType,size,modifiedTime,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError:
        return None
