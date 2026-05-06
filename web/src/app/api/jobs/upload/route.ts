import { NextResponse } from "next/server";
import path from "node:path";
import { promises as fs } from "node:fs";
import { createJob, newJobId, updateJob } from "@/lib/jobs";
import { spawnPythonJob } from "@/lib/pythonRunner";
import { autoOutputPath, ensureDownloadsDir } from "@/lib/paths";

/** Strip traversal; keep nested paths from folder uploads (webkitRelativePath). */
function safeRelPath(raw: string) {
  let s = raw.replaceAll("\\", "/").trim();
  if (s.startsWith("/")) s = s.slice(1);
  const parts = s.split("/").filter((p) => p && p !== ".." && p !== ".");
  return parts.join("/");
}

export async function POST(req: Request) {
  const form = await req.formData();
  const files = form.getAll("files").filter((x) => x instanceof File) as File[];

  const maxFilesRaw = String(form.get("maxFiles") ?? "");
  const maxFiles = maxFilesRaw.trim() === "" ? null : Number(maxFilesRaw);

  if (!files.length) {
    return NextResponse.json({ error: "No files uploaded" }, { status: 400 });
  }

  const job = await createJob({
    id: newJobId(),
    type: "build_inventory_from_upload",
    status: "queued",
    input: {
      uploadedFiles: files.length,
      maxFiles,
    },
  });

  const uploadsRoot = path.join(process.cwd(), ".data", "uploads", job.id);
  await ensureDownloadsDir();
  const outPath = autoOutputPath(job.id, "upload");
  await fs.mkdir(uploadsRoot, { recursive: true });

  // Write files to uploadsRoot (flat or nested when client sends relative paths as filenames).
  const seen = new Set<string>();
  for (const f of files) {
    let rel = safeRelPath(f.name || "file");
    if (!rel) rel = `upload-${seen.size}`;
    let destRel = rel;
    let i = 2;
    while (seen.has(destRel.toLowerCase())) {
      const ext = path.extname(rel);
      const stem = rel.slice(0, rel.length - ext.length);
      destRel = `${stem}-${i}${ext}`;
      i += 1;
    }
    seen.add(destRel.toLowerCase());
    const buf = Buffer.from(await f.arrayBuffer());
    const dest = path.join(uploadsRoot, destRel);
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.writeFile(dest, buf);
  }

  // Spawn python job against uploads folder
  const pythonCode =
    "from server import build_inventory_from_dump; " +
    `print(build_inventory_from_dump(dump_path=${JSON.stringify(uploadsRoot)}, output_path=${JSON.stringify(outPath)}, max_files=${maxFiles ?? "None"}))`;

  const { pid, logPath } = await spawnPythonJob({
    jobId: job.id,
    pythonCode,
  });

  await updateJob(job.id, { status: "running", pid, logPath, outputPath: outPath });

  const base = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
  return NextResponse.json({
    jobId: job.id,
    outputPath: outPath,
    downloadUrl: `${base}/api/jobs/${job.id}/download`,
  });
}

