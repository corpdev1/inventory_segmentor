"""Deterministic, evidence-based content summaries for dump artifacts.

Goal: produce clean, short "Content Summary" strings without guessing.
We rely on filename/path cues and only use snippet text when it contains
high-signal markers (e.g. secrets).
"""

from __future__ import annotations

import re

_PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")
_KUBECONFIG_RE = re.compile(r"apiVersion:\s*v1\s*\n.*?clusters:", re.IGNORECASE | re.DOTALL)
_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"  # flags
    "\U0001F300-\U0001FAFF"  # emoji & symbols (broad)
    "\U00002700-\U000027BF"  # dingbats
    "\U00002600-\U000026FF"  # misc symbols
    "]+",
    flags=re.UNICODE,
)

_MONTH_YEAR_RE = re.compile(
    r"(?:(?:0?[1-9]|1[0-2])[-_/](?:20)?\d{2})|(?:(?:20)?\d{2}[-_/](?:0?[1-9]|1[0-2]))"
)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _compact(s: str, limit: int = 120) -> str:
    s = " ".join((s or "").replace("\r", " ").replace("\n", " ").split())
    s = _EMOJI_RE.sub(" ", s)
    # Extra cleanup for weird word breaks and glyphs.
    s = s.replace("\u00ad", "").replace("\u200b", "")
    return (s[: limit - 1] + "...") if len(s) > limit else s


def _looks_like_title(line: str) -> bool:
    # Skip very short headings / boilerplate.
    t = line.strip()
    if len(t) < 12:
        return True
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return True
    upper = sum(1 for c in letters if c.isupper())
    # Mostly uppercase and short -> likely a title/header.
    if upper / max(1, len(letters)) > 0.85 and len(t.split()) <= 6:
        return True
    return False


def _summary_from_snippet(snip: str) -> str | None:
    """Pick a single, meaningful line from extracted text (no guessing)."""
    if not snip or not snip.strip():
        return None

    lines = [ln.strip() for ln in snip.replace("\r", "\n").split("\n")]
    # Drop empties
    lines = [ln for ln in lines if ln]
    if not lines:
        return None

    # Prefer the first non-title line with some substance.
    for ln in lines[:40]:
        if _looks_like_title(ln):
            continue
        # Avoid pure URLs or code-ish noise
        if ln.lower().startswith(("http://", "https://")):
            continue
        if len(ln) >= 18:
            return _compact(ln, limit=160)

    # As a fallback, take the first non-empty line even if it's a header.
    for ln in lines[:10]:
        if ln.lower().startswith(("http://", "https://")):
            continue
        return _compact(ln, limit=160)
    return None


def _guess_month_year(text: str) -> str | None:
    m = _MONTH_YEAR_RE.search(text)
    if m:
        return m.group(0).replace("_", "-").replace("/", "-")
    y = _YEAR_RE.search(text)
    return y.group(1) if y else None


def summarize_artifact(*, filename: str, rel_path: str, extension: str, snippet: str | None) -> str:
    """Return a short, clean summary string (no newlines)."""
    lower = f"{rel_path}/{filename}".lower()
    ext = (extension or "").lower()
    snip = snippet or ""

    # Explicit security warnings only when we have concrete markers.
    if _PRIVATE_KEY_RE.search(snip) or "private key" in lower:
        return "WARNING: Private key material detected. Exclude from licensing."
    if _KUBECONFIG_RE.search(snip) or "kubeconfig" in lower or "k8s" in lower:
        return "WARNING: Kubernetes cluster credentials detected. Exclude from licensing."

    # If we extracted text, prefer using it directly (genuine, non-speculative).
    snip_summary = _summary_from_snippet(snip)
    if snip_summary:
        return snip_summary

    # HR / legal / finance doc types
    if "bulletin" in lower or "payslip" in lower:
        d = _guess_month_year(filename) or _guess_month_year(rel_path)
        return _compact(f"Payslip{f' ({d})' if d else ''}.")
    if "dsn" in lower:
        d = _guess_month_year(filename) or _guess_month_year(rel_path)
        return _compact(f"Monthly social declaration (DSN){f' ({d})' if d else ''}.")
    if "urssaf" in lower:
        d = _guess_month_year(filename) or _guess_month_year(rel_path)
        return _compact(f"URSSAF contribution declaration{f' ({d})' if d else ''}.")
    if "rib" in lower or "iban" in lower:
        return "Bank details document."
    if "cni" in lower or "passport" in lower or "carte vitale" in lower:
        return "Personal identity document."
    if "cv" in lower or "resume" in lower:
        return "Team member CV / resume."
    if "contrat" in lower or "contract" in lower or "cdi" in lower:
        if "avenant" in lower or "amend" in lower:
            return "Employment contract amendment."
        if "stage" in lower or "intern" in lower:
            return "Internship agreement."
        return "Employment contract."
    if "mutuelle" in lower or "prevoyance" in lower or "insurance" in lower:
        return "Health / insurance documentation."
    if ext in {"xlsx", "xls"} and ("bspce" in lower or "bsa" in lower or "cap" in lower):
        return "Equity / options tracking spreadsheet."

    # Fallback: file type summary without guessing content.
    if ext in {"pdf", "docx", "pptx", "xlsx", "csv", "png", "jpg", "jpeg"}:
        return f"{ext.upper()} document."
    return "File."

