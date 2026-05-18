"""Infer content modality tags per artifact."""

from __future__ import annotations

import zipfile
from pathlib import Path


# Controlled vocabulary (stable sort order).
CODE_EXTENSIONS = frozenset(
    {
        "py",
        "pyi",
        "pyx",
        "rs",
        "go",
        "java",
        "kt",
        "kts",
        "c",
        "cc",
        "cpp",
        "cxx",
        "h",
        "hpp",
        "cs",
        "swift",
        "rb",
        "php",
        "sh",
        "bash",
        "zsh",
        "sql",
        "r",
        "scala",
        "clj",
        "cljs",
        "ex",
        "exs",
        "erl",
        "hs",
        "ml",
        "mli",
        "elm",
        "lua",
        "pl",
        "pm",
        "vim",
        "js",
        "mjs",
        "cjs",
        "jsx",
        "ts",
        "tsx",
        "vue",
        "svelte",
        "dart",
        "jl",
    }
)

IMAGE_EXTENSIONS = frozenset(
    {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff", "ico", "heic", "svg"}
)

AUDIO_VIDEO_EXTENSIONS = frozenset(
    {"mp3", "wav", "aac", "flac", "ogg", "m4a", "mp4", "mov", "avi", "mkv", "webm"}
)

TABULAR_EXTENSIONS = frozenset({"csv", "tsv", "xlsx", "xlsm", "xls"})

STRUCTURED_EXTENSIONS = frozenset({"json", "yaml", "yml", "xml", "toml"})

TEXT_DOCUMENT_EXTENSIONS = frozenset({"txt", "md", "rst", "log"})


def _zip_has_prefix(path: Path, prefix: str) -> bool:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            return any(n.startswith(prefix) for n in zf.namelist())
    except (OSError, zipfile.BadZipFile, RuntimeError):
        return False


def _docx_has_embedded_media(path: Path) -> bool:
    return _zip_has_prefix(path, "word/media/")


def _pptx_has_embedded_media(path: Path) -> bool:
    return _zip_has_prefix(path, "ppt/media/")


def _xlsx_has_embedded_media(path: Path) -> bool:
    return _zip_has_prefix(path, "xl/media/")


def _html_has_img_tag(path: Path, *, max_bytes: int = 500_000) -> bool:
    try:
        data = path.read_bytes()[:max_bytes]
    except OSError:
        return False
    lower = data.lower()
    return b"<img" in lower or b"<picture" in lower


def _pdf_has_embedded_images(path: Path, *, max_pages: int = 3) -> bool:
    try:
        import fitz  # type: ignore  # PyMuPDF
    except ImportError:
        return False
    try:
        doc = fitz.open(str(path))
    except Exception:
        return False
    try:
        n = min(max_pages, len(doc))
        for i in range(n):
            if doc[i].get_images(full=True):
                return True
        return False
    except Exception:
        return False
    finally:
        doc.close()


def infer_modalities(path: Path) -> list[str]:
    """Return sorted unique modality labels for ``path``."""
    ext = path.suffix.lower().lstrip(".")
    out: set[str] = set()

    if ext in IMAGE_EXTENSIONS:
        out.add("image")
        return sorted(out)

    if ext in AUDIO_VIDEO_EXTENSIONS:
        out.add("audio_video")
        return sorted(out)

    if ext in CODE_EXTENSIONS:
        out.add("code")
        out.add("text")

    if ext in TABULAR_EXTENSIONS:
        out.add("tabular")
        if ext in {"xlsx", "xlsm", "xls"} and _xlsx_has_embedded_media(path):
            out.add("visual_embedded")

    if ext in STRUCTURED_EXTENSIONS:
        out.add("structured_data")

    if ext == "pptx":
        out.add("slides")
        out.add("text")
        if _pptx_has_embedded_media(path):
            out.add("visual_embedded")

    elif ext == "pdf":
        out.add("text")
        if _pdf_has_embedded_images(path):
            out.add("visual_embedded")

    elif ext == "docx":
        out.add("text")
        if _docx_has_embedded_media(path):
            out.add("visual_embedded")

    elif ext in ("html", "htm"):
        out.add("text")
        if _html_has_img_tag(path):
            out.add("visual_embedded")

    elif ext in TEXT_DOCUMENT_EXTENSIONS:
        out.add("text")

    if not out:
        out.add("text")

    return sorted(out)


def format_modalities_cell(modalities: list[str]) -> str:
    """Serialize modalities for spreadsheet cells (multi-value)."""
    return "; ".join(modalities)
