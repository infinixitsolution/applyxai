/** Mouth and head pose driven by the interviewer voice, not by a timer alone. */

export type MouthShape = {
  jaw: number;
  width: number;
  round: number;
};

export type InterviewerPose = MouthShape & {
  speaking: boolean;
  blink: number;
  nod: number;
  tilt: number;
  /** 0–1 subtle expression intensity (brows / engagement). */
  expression: number;
};

const IDLE: InterviewerPose = {
  speaking: false, jaw: 0.04, width: 0.22, round: 0.08, blink: 0, nod: 0, tilt: 0, expression: 0.35,
};

type Mode = "idle" | "audio" | "estimate";

let mode: Mode = "idle";
let analyser: AnalyserNode | null = null;
let audioCtx: AudioContext | null = null;
let currentAudio: HTMLAudioElement | null = null;
let estimateStarted = 0;
let estimateDuration = 1;
const listeners = new Set<(pose: InterviewerPose) => void>();
let pose: InterviewerPose = IDLE;
let raf = 0;

function band(freq: Uint8Array, sampleRate: number, lo: number, hi: number): number {
  const binHz = sampleRate / 2 / freq.length;
  let sum = 0;
  let count = 0;
  for (let i = 0; i < freq.length; i += 1) {
    const hz = i * binHz;
    if (hz >= lo && hz < hi) {
      sum += freq[i];
      count += 1;
    }
  }
  return count ? sum / count / 255 : 0;
}

/** Map a frequency snapshot to how open, wide, and round the mouth should be. */
export function mouthFromSpectrum(freq: Uint8Array, sampleRate: number): MouthShape {
  const low = band(freq, sampleRate, 80, 350);
  const mid = band(freq, sampleRate, 350, 900);
  const high = band(freq, sampleRate, 900, 2500);
  const fric = band(freq, sampleRate, 2500, 6500);
  const energy = Math.min(1, low * 0.55 + mid * 0.4 + high * 0.28);
  if (energy < 0.045 && fric < 0.08) return { jaw: 0.03, width: 0.2, round: 0.08 };
  if (fric > mid * 1.15 && fric > 0.12 && low < 0.18) {
    return { jaw: 0.1, width: 0.9, round: 0.05 };
  }
  return {
    jaw: Math.min(1, energy * 1.35),
    width: Math.min(1, 0.15 + high / (mid + 0.08)),
    round: Math.min(1, mid / (high + 0.08)),
  };
}

function blinkAt(t: number): number {
  const phase = t % 4.4;
  return phase > 4.22 ? 1 : 0;
}

function publish(next: InterviewerPose) {
  pose = next;
  listeners.forEach((fn) => fn(next));
}

function frame() {
  if (listeners.size === 0) {
    raf = 0;
    return;
  }
  const t = performance.now() / 1000;
  const blink = blinkAt(t);
  if (mode === "audio" && analyser && audioCtx) {
    const freq = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(freq);
    const mouth = mouthFromSpectrum(freq, audioCtx.sampleRate);
    publish({
      speaking: true,
      ...mouth,
      blink,
      nod: Math.sin(t * 1.7) * 0.55 * mouth.jaw,
      tilt: Math.sin(t * 0.65) * 0.18,
      expression: Math.min(1, 0.45 + mouth.jaw * 0.45),
    });
  } else if (mode === "estimate") {
    const elapsed = performance.now() - estimateStarted;
    if (elapsed >= estimateDuration) {
      mode = "idle";
    } else {
      const syllable = Math.floor(elapsed / 140) % 4;
      const shapes: MouthShape[] = [
        { jaw: 0.55, width: 0.35, round: 0.2 },
        { jaw: 0.22, width: 0.75, round: 0.1 },
        { jaw: 0.7, width: 0.25, round: 0.8 },
        { jaw: 0.15, width: 0.85, round: 0.05 },
      ];
      publish({
        speaking: true,
        ...shapes[syllable],
        blink,
        nod: Math.sin(t * 1.7) * 0.25,
        tilt: Math.sin(t * 0.65) * 0.12,
        expression: 0.55,
      });
    }
  }
  if (mode === "idle") {
    publish({
      ...IDLE,
      blink,
      nod: Math.sin(t * 0.8) * 0.08,
      tilt: Math.sin(t * 0.35) * 0.05,
      expression: 0.32 + Math.sin(t * 0.5) * 0.04,
    });
  }
  raf = requestAnimationFrame(frame);
}

function ensureLoop() {
  if (!raf && listeners.size) raf = requestAnimationFrame(frame);
}

export function subscribeInterviewerPose(fn: (pose: InterviewerPose) => void): () => void {
  listeners.add(fn);
  fn(pose);
  ensureLoop();
  return () => {
    listeners.delete(fn);
  };
}

function context(): AudioContext {
  if (!audioCtx) audioCtx = new AudioContext();
  return audioCtx;
}

/** Play a clip through an analyser so the face follows this exact audio. */
export function playAnalysedAudio(audioBase64: string, mime: string): Promise<void> {
  const audio = new Audio(`data:${mime || "audio/mpeg"};base64,${audioBase64}`);
  currentAudio = audio;
  return new Promise((resolve, reject) => {
    let source: MediaElementAudioSourceNode | null = null;
    const finish = () => {
      if (currentAudio !== audio) {
        resolve();
        return;
      }
      currentAudio = null;
      mode = "idle";
      analyser = null;
      try { source?.disconnect(); } catch { /* already closed */ }
      resolve();
    };
    audio.onended = finish;
    audio.onerror = () => {
      mode = "idle";
      analyser = null;
      reject(new Error("playback"));
    };
    try {
      const ctx = context();
      void ctx.resume();
      source = ctx.createMediaElementSource(audio);
      const node = ctx.createAnalyser();
      node.fftSize = 2048;
      node.smoothingTimeConstant = 0.55;
      source.connect(node);
      node.connect(ctx.destination);
      analyser = node;
      mode = "audio";
      ensureLoop();
    } catch {
      mode = "estimate";
      estimateStarted = performance.now();
      estimateDuration = 4000;
      ensureLoop();
    }
    void audio.play().catch((err) => {
      mode = "idle";
      analyser = null;
      reject(err instanceof Error ? err : new Error("playback"));
    });
  });
}

/** Approximate mouth shapes while the browser voice speaks (no audio samples to analyse). */
export function beginEstimatedSpeech(text: string) {
  mode = "estimate";
  analyser = null;
  estimateStarted = performance.now();
  estimateDuration = Math.max(900, text.trim().length * 62);
  ensureLoop();
}

export function endEstimatedSpeech() {
  if (mode === "estimate") mode = "idle";
}

export function stopInterviewerAudio() {
  const audio = currentAudio;
  currentAudio = null;
  mode = "idle";
  analyser = null;
  audio?.pause();
}

/** Active TTS playback analyser, when lip sync is driven from real audio samples. */
export function getInterviewerAnalyser(): AnalyserNode | null {
  return analyser;
}

export function getInterviewerAudioContext(): AudioContext | null {
  return audioCtx;
}
