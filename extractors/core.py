"""Best-effort text extraction for common file types.

The extractor returns a short text snippet suitable for classification and
summarization. It is intentionally capped to avoid huge token usage.
"""

from __future__ import annotations

import json
import re
import unicodedata
from html.parser import HTMLParser
from pathlib import Path


MAX_CHARS_DEFAULT = 4000
MAX_BYTES_READ_DEFAULT = 2_000_000  # 2 MB safety cap for text-like reads


_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"  # flags
    "\U0001F300-\U0001FAFF"  # emoji & symbols (broad)
    "\U00002700-\U000027BF"  # dingbats
    "\U00002600-\U000026FF"  # misc symbols
    "]+",
    flags=re.UNICODE,
)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n…(truncated)…"


def _normalize_extracted_text(text: str) -> str:
    """Normalize common extraction artifacts (PDFs/OCR/etc.)."""
    if not text:
        return text
    # Strip emoji/pictographs; they often appear in doc titles and look noisy in summaries.
    text = _EMOJI_RE.sub(" ", text)
    # Expand compatibility ligatures (ﬁ -> fi, ﬂ -> fl, etc.) for cleaner words.
    text = unicodedata.normalize("NFKC", text)
    # Fix hyphenation across line breaks: "exam-\nple" -> "example"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Convert newlines to spaces (later callers may re-split if needed)
    text = text.replace("\r", "\n")
    # Remove soft hyphen and zero-width spaces
    text = text.replace("\u00ad", "").replace("\u200b", "")
    # Normalize common ligatures
    text = (
        text.replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("\ufb03", "ffi")
        .replace("\ufb04", "ffl")
    )
    return text


def _pdf_text_quality_score(text: str) -> float:
    """Prefer extracts with more letters and fewer single-letter word fragments."""
    if not text or not text.strip():
        return -1.0
    letters = sum(1 for c in text if c.isalpha())
    toks = text.split()
    if not toks:
        return letters / max(len(text), 1)
    singles = sum(1 for t in toks if len(t) == 1 and t.isalpha())
    frag = singles / len(toks)
    return (letters / max(len(text), 1)) * 1.5 - frag


def _extract_pdf_pages(path: Path, *, max_pages: int) -> str | None:
    """Extract PDF text using PyMuPDF + pypdf; pick the better output per page.

    PyMuPDF defaults preserve ligatures, which often breaks badly when the PDF
    ToUnicode map is incomplete (missing ``t``/``f``/``fi`` etc.). We omit
    TEXT_PRESERVE_LIGATURES and compare against pypdf per page.
    """
    fitz_pages: list[str] = []
    pypdf_pages: list[str] = []

    try:
        import fitz  # type: ignore  # PyMuPDF

        flags = (
            int(fitz.TEXT_PRESERVE_WHITESPACE)
            | int(fitz.TEXT_MEDIABOX_CLIP)
            | int(fitz.TEXT_DEHYPHENATE)
            | int(fitz.TEXT_USE_CID_FOR_UNKNOWN_UNICODE)
        )
        doc = fitz.open(str(path))
        n = min(max_pages, doc.page_count)
        for i in range(n):
            page = doc.load_page(i)
            t = page.get_text("text", flags=flags) or ""
            fitz_pages.append(_normalize_extracted_text(t) if t.strip() else "")
        doc.close()
    except Exception:
        fitz_pages = []

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        n = min(max_pages, len(reader.pages))
        for i in range(n):
            t = reader.pages[i].extract_text() or ""
            pypdf_pages.append(_normalize_extracted_text(t) if t.strip() else "")
    except Exception:
        pypdf_pages = []

    if not any(fitz_pages) and not any(pypdf_pages):
        return None

    n = max(len(fitz_pages), len(pypdf_pages))
    merged: list[str] = []
    for i in range(n):
        a = fitz_pages[i] if i < len(fitz_pages) else ""
        b = pypdf_pages[i] if i < len(pypdf_pages) else ""
        if not a:
            chosen = b
        elif not b:
            chosen = a
        else:
            chosen = a if _pdf_text_quality_score(a) >= _pdf_text_quality_score(b) else b
        if chosen:
            merged.append(chosen)

    return "\n\n".join(merged) if merged else None


def _read_text_file(path: Path, *, max_bytes: int) -> str:
    data = path.read_bytes()[:max_bytes]
    return data.decode("utf-8", errors="replace")


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0  # inside script/style
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        t = (tag or "").lower()
        if t in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        t = (tag or "").lower()
        if t in {"script", "style"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if self._skip_depth > 0:
            return
        if data and data.strip():
            self._chunks.append(data)

    def text(self) -> str:
        joined = " ".join(self._chunks)
        joined = re.sub(r"[ \t\r\f\v]+", " ", joined)
        return joined.strip()


def _strip_html(html: str) -> str:
    # Regex-stripping HTML is fragile; use a real parser to avoid dropping characters.
    try:
        parser = _HTMLTextExtractor()
        parser.feed(html)
        parser.close()
        return parser.text()
    except Exception:
        # Fallback: best-effort regex strip.
        html = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html)
        html = re.sub(r"(?is)<[^>]+>", " ", html)
        html = re.sub(r"[ \t\r\f\v]+", " ", html)
        return html.strip()


def extract_snippet(
    file_path: str,
    *,
    max_chars: int = MAX_CHARS_DEFAULT,
    max_bytes: int = MAX_BYTES_READ_DEFAULT,
) -> str | None:
    """Return a short snippet (or None if not extractable)."""
    path = Path(file_path)
    ext = path.suffix.lower()

    try:
        if ext in {".txt", ".md", ".rst", ".log"}:
            return _truncate(_read_text_file(path, max_bytes=max_bytes), max_chars)

        if ext in {".html", ".htm"}:
            raw = _read_text_file(path, max_bytes=max_bytes)
            # HTML exports (e.g., Google Docs) often contain ligature glyphs (ﬁ, ﬂ, …)
            # that can look like “missing letters” downstream unless normalized.
            cleaned = _strip_html(raw)
            cleaned = _normalize_extracted_text(cleaned)
            return _truncate(cleaned, max_chars)

        if ext == ".json":
            raw = _read_text_file(path, max_bytes=max_bytes)
            try:
                obj = json.loads(raw)
                pretty = json.dumps(obj, ensure_ascii=False, indent=2)
                return _truncate(pretty, max_chars)
            except Exception:
                return _truncate(raw, max_chars)

        if ext in {".csv", ".tsv"}:
            raw = _read_text_file(path, max_bytes=max_bytes)
            lines = raw.splitlines()
            head = "\n".join(lines[:80])
            return _truncate(head, max_chars)

        if ext in {".xlsx", ".xlsm"}:
            try:
                import openpyxl  # type: ignore
            except Exception:
                return None
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            ws = wb[wb.sheetnames[0]]
            rows = []
            for r_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
                if r_idx > 20:
                    break
                rows.append([("" if v is None else str(v)) for v in row[:20]])
            txt = "\n".join(["\t".join(r) for r in rows if any(c.strip() for c in r)])
            return _truncate(txt, max_chars)

        if ext == ".pdf":
            raw = _extract_pdf_pages(path, max_pages=5)
            return _truncate(raw, max_chars) if raw else None

        if ext == ".docx":
            try:
                import docx  # type: ignore
            except Exception:
                return None
            doc = docx.Document(str(path))
            paras = [_normalize_extracted_text(p.text) for p in doc.paragraphs if p.text.strip()]
            return _truncate("\n".join(paras[:200]), max_chars) if paras else None

        if ext == ".pptx":
            # Optional dependency; keep graceful fallback.
            try:
                from pptx import Presentation  # type: ignore
            except Exception:
                return None
            prs = Presentation(str(path))
            parts: list[str] = []
            # python-pptx Slides collection doesn't support slicing reliably across versions.
            max_slides = min(20, len(prs.slides))
            for i in range(max_slides):
                slide = prs.slides[i]
                for shape in slide.shapes:
                    text = getattr(shape, "text", None)
                    if isinstance(text, str) and text.strip():
                        parts.append(_normalize_extracted_text(text.strip()))
                if sum(len(p) for p in parts) >= max_chars:
                    break
            return _truncate("\n\n".join(parts), max_chars) if parts else None

        # For unknown/binary formats: no snippet.
        return None
    except Exception:
        return None

