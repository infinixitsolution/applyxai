import { spawn, type ChildProcess } from "child_process";
import { workerExecutablePath } from "./agent-process";

const CLIP_MAGIC = Buffer.from("AXLC");

let captureProc: ChildProcess | null = null;
let stdoutBuffer = Buffer.alloc(0);
let clipHandler: ((speaker: string, wav: Buffer) => void) | null = null;
let stderrTail = "";

function drainStdout(): void {
  const handler = clipHandler;
  if (!handler) return;

  while (stdoutBuffer.length >= CLIP_MAGIC.length + 1 + 4) {
    const magicAt = stdoutBuffer.indexOf(CLIP_MAGIC);
    if (magicAt < 0) {
      stdoutBuffer = Buffer.alloc(0);
      return;
    }
    if (magicAt > 0) {
      stdoutBuffer = stdoutBuffer.subarray(magicAt);
    }
    if (stdoutBuffer.length < CLIP_MAGIC.length + 1) return;

    const speakerLen = stdoutBuffer[CLIP_MAGIC.length];
    const headerLen = CLIP_MAGIC.length + 1 + speakerLen + 4;
    if (stdoutBuffer.length < headerLen) return;

    const speaker = stdoutBuffer
      .subarray(CLIP_MAGIC.length + 1, CLIP_MAGIC.length + 1 + speakerLen)
      .toString("utf8");
    const wavLen = stdoutBuffer.readUInt32BE(CLIP_MAGIC.length + 1 + speakerLen);
    if (stdoutBuffer.length < headerLen + wavLen) return;

    const wav = stdoutBuffer.subarray(headerLen, headerLen + wavLen);
    stdoutBuffer = stdoutBuffer.subarray(headerLen + wavLen);
    handler(speaker, wav);
  }
}

function waitForReady(proc: ChildProcess, timeoutMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (err?: Error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      proc.stderr?.off("data", onStderr);
      proc.off("exit", onExit);
      if (err) reject(err);
      else resolve();
    };

    const onStderr = (chunk: Buffer) => {
      stderrTail += chunk.toString("utf8");
      if (stderrTail.includes("ready\n") || stderrTail.includes("ready\r\n")) {
        finish();
      }
    };

    const onExit = (code: number | null) => {
      const detail = stderrTail.trim() || `Capture process exited (${code ?? "?"})`;
      finish(new Error(detail));
    };

    const timer = setTimeout(() => {
      finish(new Error(stderrTail.trim() || "Timed out waiting for speaker loopback capture."));
    }, timeoutMs);

    if (!proc.stderr) {
      finish(new Error("Capture process has no stderr stream."));
      return;
    }
    proc.stderr.on("data", onStderr);
    proc.on("exit", onExit);
  });
}

export function isNativeCaptureRunning(): boolean {
  return captureProc !== null && !captureProc.killed;
}

export async function startNativeCapture(onClip: (speaker: string, wav: Buffer) => void): Promise<void> {
  await stopNativeCapture();
  clipHandler = onClip;
  stdoutBuffer = Buffer.alloc(0);
  stderrTail = "";

  const exe = workerExecutablePath();
  const proc = spawn(exe, ["--live-capture"], {
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  captureProc = proc;

  proc.stdout?.on("data", (chunk: Buffer) => {
    stdoutBuffer = Buffer.concat([stdoutBuffer, chunk]);
    drainStdout();
  });

  proc.stderr?.on("data", (chunk: Buffer) => {
    stderrTail += chunk.toString("utf8");
    if (stderrTail.length > 4000) stderrTail = stderrTail.slice(-4000);
  });

  proc.on("exit", () => {
    if (captureProc === proc) captureProc = null;
  });

  await waitForReady(proc, 20_000);
}

export async function stopNativeCapture(): Promise<void> {
  clipHandler = null;
  stdoutBuffer = Buffer.alloc(0);
  const proc = captureProc;
  captureProc = null;
  if (!proc || proc.killed) return;
  proc.kill();
  await new Promise<void>((resolve) => {
    proc.once("exit", () => resolve());
    setTimeout(resolve, 2000);
  });
}

export async function probeNativeCapture(): Promise<{ ok: boolean; message: string }> {
  const exe = workerExecutablePath();
  return new Promise((resolve) => {
    let errText = "";
    const proc = spawn(exe, ["--live-capture-probe"], {
      stdio: ["ignore", "ignore", "pipe"],
      windowsHide: true,
    });
    proc.stderr.on("data", (c: Buffer) => {
      errText += c.toString("utf8");
    });
    proc.on("exit", (code) => {
      if (code === 0) {
        resolve({
          ok: true,
          message: "Speaker loopback and microphone capture are available on this PC.",
        });
        return;
      }
      resolve({
        ok: false,
        message: errText.trim() || "Could not open speaker loopback. Check your default playback device.",
      });
    });
  });
}
