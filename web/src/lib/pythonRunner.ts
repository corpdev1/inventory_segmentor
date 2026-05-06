import { spawn } from "node:child_process";
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

export async function spawnPythonJob(opts: {
  jobId: string;
  pythonCode: string;
  env?: Record<string, string | undefined>;
}): Promise<SpawnResult> {
  const repoRoot = repoRootFromWebCwd();
  const logsDir = path.join(process.cwd(), ".data", "logs");
  await fs.mkdir(logsDir, { recursive: true });
  const logPath = path.join(logsDir, `${opts.jobId}.log.txt`);

  const pythonBin = process.env.PYTHON_BIN || "python3";
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

