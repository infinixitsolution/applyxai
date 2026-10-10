import { describe, expect, it } from "vitest";
import { mouthFromSpectrum } from "./interviewerMotion";

function fill(sampleRate: number, lo: number, hi: number, value: number): Uint8Array {
  const freq = new Uint8Array(512);
  const binHz = sampleRate / 2 / freq.length;
  for (let i = 0; i < freq.length; i += 1) {
    const hz = i * binHz;
    if (hz >= lo && hz < hi) freq[i] = value;
  }
  return freq;
}

describe("interviewer mouth", () => {
  it("stays nearly closed when the voice is silent", () => {
    const mouth = mouthFromSpectrum(new Uint8Array(512), 44100);
    expect(mouth.jaw).toBeLessThan(0.08);
  });

  it("opens the jaw when low voice energy is present", () => {
    const mouth = mouthFromSpectrum(fill(44100, 80, 900, 200), 44100);
    expect(mouth.jaw).toBeGreaterThan(0.4);
  });

  it("uses a narrow mouth for high-frequency sounds", () => {
    const mouth = mouthFromSpectrum(fill(44100, 2500, 6500, 180), 44100);
    expect(mouth.width).toBeGreaterThan(0.7);
    expect(mouth.jaw).toBeLessThan(0.25);
  });
});
