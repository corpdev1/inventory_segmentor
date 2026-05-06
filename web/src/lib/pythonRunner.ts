import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { promises as fs } from "node:fs";
import path from "node:path";

export type SpawnResult = {
  pid: number;
  logPath: string;
};

function repoRootFromWebCwd() {
  // web/ is a subfolder inside the repo
  return path.resolve(process.cwd(), "..");
}

/** Absolute path to the Python binary. Relative `PYTHON_BIN` in `.env` is resolved from `web/` (not from `cwd` passed to `spawn`, which is repo root). */
function resolvePythonBin(repoRoot: string): string {
  const webDir = path.join(repoRoot, "web");
  const venvPython = path.join(repoRoot, ".venv", "bin", "python");
  const raw = process.env.PYTHON_BIN?.trim();

  if (raw) {
    const candidate = path.isAbsolute(raw) ? raw : path.resolve(webDir, raw);
    if (existsSync(candidate)) {
      return candidate;
    }
    const fromRepo = path.resolve(repoRoot, raw);
    if (existsSync(fromRepo)) {
      return fromRepo;
    }
    return candidate;
  }

  if (existsSync(venvPython)) {
    return venvPython;
  }

  return "python3";
}

export async function spawnPythonJob(opts: {
  jobId: string;
  pythonCode: string;
  env?: Record<string, string | undefined>;
}): Promise<SpawnResult> {
  const repoRoot = repoRootFromWebCwd();
  const logsDir = path.join(process.cwd(), ".data", "logs");
  await fs.mkdir(logsDir, { recursive: true });
  const logPath = path.join(logsDir, `${opts.jobId}.log.txt`);

  const pythonBin = resolvePythonBin(repoRoot);
  const child = spawn(pythonBin, ["-c", opts.pythonCode], {
    cwd: repoRoot,
    env: {
      ...process.env,
      ...opts.env,
      // Ensure python can import repo-root modules like server.py
      PYTHONPATH: repoRoot,
    },
  });

  const logStream = await fs.open(logPath, "a");
  child.stdout.on("data", async (d) => {
    await logStream.appendFile(d);
  });
  child.stderr.on("data", async (d) => {
    await logStream.appendFile(d);
  });
  child.on("close", async () => {
    await logStream.close();
  });

  return { pid: child.pid ?? -1, logPath };
}

