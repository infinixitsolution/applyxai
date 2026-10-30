import { renderHook, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useMockInterviewVoice } from "./useMockInterviewVoice";

describe("useMockInterviewVoice desktop STT", () => {
  const originalMediaDevices = navigator.mediaDevices;

  beforeEach(() => {
    vi.stubGlobal("window", {
      ...window,
      applyxaiDesktop: { isDesktop: true },
      speechSynthesis: { cancel: vi.fn() },
      requestAnimationFrame: (cb: FrameRequestCallback) => {
        cb(0);
        return 1;
      },
      cancelAnimationFrame: vi.fn(),
    });
    const speechStart = vi.fn();
    class MockSpeechRecognition {
      continuous = false;
      interimResults = false;
      lang = "en-IN";
      onresult = null;
      onerror = null;
      onend = null;
      start = speechStart;
      stop = vi.fn();
      abort = vi.fn();
    }
    vi.stubGlobal("SpeechRecognition", MockSpeechRecognition);
    vi.stubGlobal("webkitSpeechRecognition", MockSpeechRecognition);
    (globalThis as { __speechStart?: typeof speechStart }).__speechStart = speechStart;

    const stream = {
      getTracks: () => [{ readyState: "live", stop: vi.fn() }],
    } as unknown as MediaStream;
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });
    const recorderStart = vi.fn();
    global.MediaRecorder = vi.fn().mockImplementation(function MockRecorder(this: {
      mimeType: string;
      state: string;
      start: ReturnType<typeof vi.fn>;
      stop: ReturnType<typeof vi.fn>;
      ondataavailable: null;
    }) {
      this.mimeType = "audio/webm";
      this.state = "recording";
      this.start = recorderStart;
      this.stop = vi.fn();
      this.ondataavailable = null;
    }) as unknown as typeof MediaRecorder;
    (globalThis as { __recorderStart?: typeof recorderStart }).__recorderStart = recorderStart;
    global.AudioContext = vi.fn().mockImplementation(function MockAudioContext(this: {
      resume: ReturnType<typeof vi.fn>;
      close: ReturnType<typeof vi.fn>;
      createMediaStreamSource: ReturnType<typeof vi.fn>;
      createAnalyser: ReturnType<typeof vi.fn>;
    }) {
      this.resume = vi.fn().mockResolvedValue(undefined);
      this.close = vi.fn().mockResolvedValue(undefined);
      this.createMediaStreamSource = vi.fn().mockReturnValue({ connect: vi.fn() });
      this.createAnalyser = vi.fn().mockReturnValue({
        fftSize: 512,
        smoothingTimeConstant: 0.65,
        frequencyBinCount: 32,
        getByteFrequencyData: vi.fn(),
      });
    }) as unknown as typeof AudioContext;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: originalMediaDevices,
    });
    vi.restoreAllMocks();
  });

  it("uses server VAD path on desktop instead of Web Speech", async () => {
    const transcribe = vi.fn().mockResolvedValue("my answer");
    const onTranscript = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      useMockInterviewVoice({
        onTranscript,
        transcribe,
        preferServerStt: true,
        bargeInEnabled: false,
      }),
    );

    await act(async () => {
      result.current.startLiveMode();
    });

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
    expect((globalThis as { __recorderStart?: ReturnType<typeof vi.fn> }).__recorderStart).toHaveBeenCalled();
    expect((globalThis as { __speechStart?: ReturnType<typeof vi.fn> }).__speechStart).not.toHaveBeenCalled();
  });
});
