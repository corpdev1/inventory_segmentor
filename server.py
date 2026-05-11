"""MCP server: data inventory segmentation.

Exposes one tool: segment_inventory(input_path, output_path, ...).
Reads an .xlsx or .csv inventory, classifies each row via the Anthropic
API, and writes a multi-sheet workbook to output_path.
"""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

from checkpoint import append_checkpoint, checkpoint_path_for_output, load_checkpoint
from excel_io import load_inventory, write_company_inventory_workbook, write_segmented_workbook
from extractors.core import extract_snippet
from ingest import infer_source_system, iter_files
from inventory_writer import summarize_inventory_from_evidence
from pii import detect_pii
from artifact_summary import summarize_artifact
from segmenter import DEFAULT_BATCH_SIZE, DEFAULT_MODEL, classify_dataframe, classify_items


def _download_and_extract_repo(
    *,
    provider: str,
    repo_url: str,
    ref: str,
    token: str | None,
) -> Path:
    """Download a repo archive (GitHub/GitLab) and extract to a temp folder.

    Token is used only for the HTTP request and is never persisted.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="inventory-segmenter-repo-")).resolve()
    archive_path = tmpdir / "repo.tar.gz"
    extract_dir = tmpdir / "extract"
    extract_dir.mkdir(parents=True, exist_ok=True)

    url = repo_url.strip()
    if provider == "github":
        parsed = urllib.parse.urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError("GitHub repoUrl must look like https://github.com/<org>/<repo>")
        owner, repo = parts[0], parts[1].removesuffix(".git")
        # Use GitHub API tarball endpoint; this works for private repos with a token.
        # https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28#download-a-repository-archive-tar
        download_url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{urllib.parse.quote(ref)}"
        req = urllib.request.Request(download_url, method="GET")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "inventory-segmenter/0.1")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
    elif provider == "gitlab":
        parsed = urllib.parse.urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError("GitLab repoUrl must look like https://gitlab.com/<group>/<project>")
        project_path = "/".join(parts).removesuffix(".git")
        project_enc = urllib.parse.quote(project_path, safe="")
        sha = urllib.parse.quote(ref)
        download_url = f"{parsed.scheme}://{parsed.netloc}/api/v4/projects/{project_enc}/repository/archive.tar.gz?sha={sha}"
        req = urllib.request.Request(download_url, method="GET")
        if token:
            req.add_header("PRIVATE-TOKEN", token)
    else:
        raise ValueError("provider must be 'github' or 'gitlab'")

    try:
        with urllib.request.urlopen(req) as resp, archive_path.open("wb") as f:
            shutil.copyfileobj(resp, f)
    except urllib.error.HTTPError as e:
        # GitHub returns 404 for private repos when unauthenticated, and 404 for bad refs.
        hint = ""
        if provider == "github" and e.code == 404 and not token:
            hint = " (repo may be private; provide a GitHub token with access)"
        raise RuntimeError(f"Repo archive download failed: HTTP {e.code}{hint}") from e

    with tarfile.open(archive_path, "r:gz") as tf:
        tf.extractall(path=extract_dir)

    children = [p for p in extract_dir.iterdir() if p.is_dir()]
    return children[0] if len(children) == 1 else extract_dir


def segment_inventory(
    input_path: str,
    output_path: str,
    sheet_name: str | None = None,
    description_column: str | None = None,
    source_column: str | None = None,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> str:
    """Segment a data-inventory spreadsheet into seven buckets.

    Reads the inventory at input_path, classifies every row using the
    Anthropic API, and writes a workbook to output_path containing a
    Master sheet, one sheet per bucket, and a Summary sheet.

    Args:
        input_path: Absolute path to the input .xlsx or .csv file.
        output_path: Absolute path where the segmented .xlsx will be written.
        sheet_name: Optional sheet name to read (defaults to the first sheet).
        description_column: Override auto-detection of the description column.
        source_column: Override auto-detection of the source/system column.
        model: Anthropic model id. Defaults to claude-sonnet-4-6.
        batch_size: Rows per Anthropic API call. Defaults to 25.

    Returns:
        A short status string with row counts per bucket.
    """
    in_path = Path(input_path).expanduser().resolve()
    out_path = Path(output_path).expanduser().resolve()

    if not in_path.exists():
        raise FileNotFoundError(f"Input file not found: {in_path}")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set in the server's environment."
        )

    df, desc_col, src_col = load_inventory(
        str(in_path),
        sheet_name=sheet_name,
        description_column=description_column,
        source_column=source_column,
    )
    df = classify_dataframe(
        df,
        description_column=desc_col,
        source_column=src_col,
        model=model,
        batch_size=batch_size,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_segmented_workbook(df, str(out_path))

    counts = df["bucket_number"].value_counts().sort_index()
    lines = [
        f"Wrote {len(df)} classified items to {out_path}",
        f"Description column: {desc_col}",
        f"Source column: {src_col or '(none detected)'}",
        "Bucket counts:",
    ]
    for num, count in counts.items():
        lines.append(f"  {int(num)}: {int(count)}")
    return "\n".join(lines)


def build_inventory_from_dump(
    dump_path: str,
    output_path: str,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_files: int | None = None,
    strict_scan: bool = False,
) -> str:
    """Build the 7-row company inventory (desired format) from a dump folder.

    Scans files under dump_path, extracts short snippets, classifies each artifact
    into one of seven buckets via Anthropic, then writes an .xlsx to output_path
    containing:
      - Inventory (desired 4 columns)
      - Evidence (one row per artifact for auditability)
    """
    dump_root = Path(dump_path).expanduser().resolve()
    out_path = Path(output_path).expanduser().resolve()

    if not dump_root.exists():
        raise FileNotFoundError(f"Dump folder not found: {dump_root}")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set in the server's environment.")

    ckpt_path = checkpoint_path_for_output(str(out_path))
    existing = load_checkpoint(ckpt_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Stream files and classify in batches so we checkpoint early and can resume.
    evidence_rows: list[dict] = []
    pending: list[dict] = []
    processed = 0
    classified = 0

    exclude_dirs = () if strict_scan else (".venv", "__pycache__")
    include_hidden = bool(strict_scan)

    def flush_batch() -> None:
        nonlocal classified, pending, existing
        if not pending:
            return
        batch = pending
        pending = []
        batch_out = classify_items(batch, model=model, batch_size=len(batch))

        # Defensive: tolerate occasional malformed rows so large runs don't crash.
        cleaned: list[dict] = []
        for c in (batch_out or []):
            if not isinstance(c, dict):
                continue
            rid = c.get("row_id")
            try:
                rid_i = int(rid)
            except Exception:
                continue
            c["row_id"] = rid_i
            cleaned.append(c)

        append_checkpoint(ckpt_path, cleaned)
        for c in cleaned:
            try:
                existing[int(c.get("row_id"))] = c
            except Exception:
                continue
        classified += len(cleaned)
        print(
            f"[batch] classified={classified} checkpoint={ckpt_path.name}",
            flush=True,
        )

    for p in iter_files(
        str(dump_root),
        exclude_dirs=exclude_dirs,
        include_hidden=include_hidden,
    ):
        processed += 1
        if max_files is not None and processed > max_files:
            break

        stat = p.stat()
        rel_path = str(p.resolve().relative_to(dump_root)).replace("\\", "/")
        filename = p.name
        extension = p.suffix.lower().lstrip(".")
        source_guess = infer_source_system(str(p))

        snippet = extract_snippet(str(p))
        desc = f"{filename} ({extension or 'noext'}, {int(stat.st_size)} bytes)"
        if snippet:
            desc = desc + "\n" + snippet

        pii = detect_pii(snippet)
        content_summary = summarize_artifact(
            filename=filename,
            rel_path=rel_path,
            extension=extension,
            snippet=snippet,
        )

        artifact_id = processed  # deterministic due to sorted walk above

        evidence_rows.append(
            {
                "artifact_id": artifact_id,
                "path": rel_path,
                "filename": filename,
                "extension": extension,
                "size_bytes": int(stat.st_size),
                "modified_time_unix": float(stat.st_mtime),
                "source_guess": source_guess,
                "snippet": (snippet or "")[:800],
                "content_summary": content_summary,
                "pii_flag": "Yes" if pii.has_pii else "No",
                "pii_types": ", ".join(pii.types),
            }
        )

        if artifact_id not in existing:
            pending.append(
                {
                    "row_id": artifact_id,
                    "description": desc,
                    "source": source_guess,
                    "filename": filename,
                    "extension": extension,
                    "path_hint": rel_path,
                    "snippet": (snippet or ""),
                }
            )
            if len(pending) >= batch_size:
                flush_batch()

        if processed % 500 == 0:
            print(
                f"[progress] processed={processed} pending={len(pending)} classified={classified}",
                flush=True,
            )

    flush_batch()
    by_id = existing

    import pandas as pd

    evidence_df = pd.DataFrame(evidence_rows)
    evidence_df["bucket_number"] = evidence_df["artifact_id"].map(
        lambda rid: by_id.get(int(rid), {}).get("bucket_number")
    )
    evidence_df["bucket_name"] = evidence_df["artifact_id"].map(
        lambda rid: by_id.get(int(rid), {}).get("bucket_name")
    )
    evidence_df["confidence"] = evidence_df["artifact_id"].map(
        lambda rid: by_id.get(int(rid), {}).get("confidence")
    )
    evidence_df["rationale"] = evidence_df["artifact_id"].map(
        lambda rid: by_id.get(int(rid), {}).get("rationale")
    )

    inventory_df = summarize_inventory_from_evidence(evidence_df, model=model)

    write_company_inventory_workbook(
        inventory_df=inventory_df,
        evidence_df=evidence_df,
        output_path=str(out_path),
    )

    lines = [
        f"Wrote company inventory to {out_path}",
        f"Artifacts scanned: {processed}",
        "Sheets: Inventory, Overview, Sample Files, Evidence, + bucket tabs",
        f"Checkpoint: {ckpt_path}",
    ]
    return "\n".join(lines)


def build_inventory_from_repo(
    provider: str,
    repo_url: str,
    output_path: str,
    ref: str = "main",
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_files: int | None = None,
) -> str:
    """Build the clean multi-tab inventory workbook from a Git repo URL.

    Tokens (do NOT pass as args; set via env so they are not persisted):
      - GitHub: GITHUB_TOKEN
      - GitLab: GITLAB_TOKEN
    """
    token = None
    if provider == "github":
        token = os.environ.get("GITHUB_TOKEN")
    elif provider == "gitlab":
        token = os.environ.get("GITLAB_TOKEN")

    repo_root = _download_and_extract_repo(provider=provider, repo_url=repo_url, ref=ref, token=token)
    return build_inventory_from_dump(
        dump_path=str(repo_root),
        output_path=output_path,
        model=model,
        batch_size=batch_size,
        max_files=max_files,
    )


def _run_mcp() -> None:
    """Start the MCP server (imports `mcp` only when this entrypoint runs)."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("inventory-segmenter")
    mcp.tool()(segment_inventory)
    mcp.tool()(build_inventory_from_dump)
    mcp.tool()(build_inventory_from_repo)
    mcp.run()


if __name__ == "__main__":
    _run_mcp()
