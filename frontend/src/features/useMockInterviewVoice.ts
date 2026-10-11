import { useCallback, useEffect, useRef, useState } from "react";
import { stopInterviewerAudio } from "./interviewerMotion";
import { type FetchInterviewerTts, playInterviewerSpeech } from "./mockInterviewSpeech";
export type VoicePhase = "idle" | "listening" | "processing" | "speaking" | "unsupported";

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((ev: { results: { isFinal: boolean; 0: { transcript: string } }[] }) => void) | null;
  onerror: ((ev: { error: string }) => void) | null;
  onend: (() => void) | null;
};

function speechRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** Silence after any speech (including mid-sentence pauses) before auto-send. */
const UTTERANCE_PAUSE_MS = 1600;
/** Extra wait when we only have a tiny fragment (browser split an answer early). */
const SHORT_FRAGMENT_PAUSE_MS = 2800;
const MIN_COMFORTABLE_CHARS = 28;

export function useMockInterviewVoice(options: {
  onTranscript: (text: string) => Promise<void>;
  /** Server Whisper fallback when browser speech recognition is unavailable. */
  transcribe?: (blob: Blob) => Promise<string>;
  /** When false, mic energy will not cut off interviewer TTS. */
  bargeInEnabled?: boolean;
  disabled?: boolean;
  /** Hands-free: listen continuously and send after you pause speaking. */
  continuous?: boolean;
}) {
  const [phase, setPhase] = useState<VoicePhase>("idle");
  const [interim, setInterim] = useState("");
  const [liveMode, setLiveMode] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  /** True when we heard you recently and are waiting for end-of-answer silence. */
  const [awaitingSilence, setAwaitingSilence] = useState(false);
  const [ttsBuffering, setTtsBuffering] = useState(false);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const liveRef = useRef(false);
  const processingRef = useRef(false);
  const speakingRef = useRef(false);
  const utteranceBufferRef = useRef("");
  const latestInterimRef = useRef("");
  const resultIndexRef = useRef(0);
  const lastSubmittedRef = useRef("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onTranscriptRef = useRef(options.onTranscript);
  const disabledRef = useRef(options.disabled);
  const fetchTtsRef = useRef<FetchInterviewerTts | undefined>(undefined);
  const forceSubmitRef = useRef(false);
  const shortWaitAttemptsRef = useRef(0);
  const speakSeqRef = useRef(0);
  const lastSpeakKeyRef = useRef("");
  const micPausedRef = useRef(false);
  const transcribeRef = useRef(options.transcribe);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recorderStreamRef = useRef<MediaStream | null>(null);
  const recorderChunksRef = useRef<Blob[]>([]);
  const serverSttRef = useRef(false);
  const bargeStreamRef = useRef<MediaStream | null>(null);
  const bargeAnalyserRef = useRef<AnalyserNode | null>(null);
  const bargeCtxRef = useRef<AudioContext | null>(null);
  const bargeRafRef = useRef(0);
  const bargeLoudMsRef = useRef(0);
  const bargeInEnabledRef = useRef(options.bargeInEnabled !== false);

  useEffect(() => {
    onTranscriptRef.current = options.onTranscript;
    disabledRef.current = options.disabled;
    transcribeRef.current = options.transcribe;
    bargeInEnabledRef.current = options.bargeInEnabled !== false;
  }, [options.onTranscript, options.disabled, options.transcribe, options.bargeInEnabled]);

  useEffect(() => {
    setSpeechSupported(Boolean(speechRecognitionCtor()) || Boolean(options.transcribe));
  }, [options.transcribe]);

  const clearDebounce = useCallback(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    setAwaitingSilence(false);
  }, []);

  const stopBargeInMonitor = useCallback(() => {
    if (bargeRafRef.current) {
      cancelAnimationFrame(bargeRafRef.current);
      bargeRafRef.current = 0;
    }
    bargeAnalyserRef.current = null;
    bargeLoudMsRef.current = 0;
  }, []);

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel();
    stopInterviewerAudio();
    stopBargeInMonitor();
    speakingRef.current = false;
  }, [stopBargeInMonitor]);

  const interruptSpeaking = useCallback(() => {
    if (!speakingRef.current) return;
    speakSeqRef.current += 1;
    stopSpeaking();
    if (liveRef.current && !micPausedRef.current) {
      setPhase("listening");
      setTimeout(() => beginListeningRef.current(), 200);
    }
  }, [stopSpeaking]);

  const startBargeInMonitor = useCallback(() => {
    if (!bargeInEnabledRef.current || micPausedRef.current || !liveRef.current || !speakingRef.current) return;
    stopBargeInMonitor();
    void (async () => {
      try {
        let stream = bargeStreamRef.current ?? recorderStreamRef.current;
        if (!stream) {
          stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          bargeStreamRef.current = stream;
        }
        const ctx = bargeCtxRef.current ?? new AudioContext();
        bargeCtxRef.current = ctx;
        await ctx.resume();
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = 0.65;
        source.connect(analyser);
        bargeAnalyserRef.current = analyser;
        const tick = () => {
          if (!speakingRef.current || micPausedRef.current) {
            stopBargeInMonitor();
            return;
          }
          const node = bargeAnalyserRef.current;
          if (!node) return;
          const buf = new Uint8Array(node.frequencyBinCount);
          node.getByteFrequencyData(buf);
          let sum = 0;
          for (let i = 0; i < buf.length; i += 1) sum += buf[i];
          const level = sum / buf.length / 255;
          if (level > 0.11) {
            bargeLoudMsRef.current += 18;
            if (bargeLoudMsRef.current >= 320) {
              interruptSpeaking();
              return;
            }
          } else {
            bargeLoudMsRef.current = Math.max(0, bargeLoudMsRef.current - 24);
          }
          bargeRafRef.current = requestAnimationFrame(tick);
        };
        bargeRafRef.current = requestAnimationFrame(tick);
      } catch {
        /* mic unavailable — user can still tap Interrupt */
      }
    })();
  }, [interruptSpeaking, stopBargeInMonitor]);

  const currentDraft = useCallback(() => {
    const merged = `${utteranceBufferRef.current} ${latestInterimRef.current}`.replace(/\s+/g, " ").trim();
    return merged;
  }, []);

  const stopServerRecording = useCallback(async (): Promise<string> => {
    const rec = recorderRef.current;
    if (!rec || rec.state === "inactive") return "";
    return new Promise((resolve) => {
      rec.onstop = async () => {
        recorderRef.current = null;
        const stream = recorderStreamRef.current;
        recorderStreamRef.current = null;
        stream?.getTracks().forEach((t) => t.stop());
        const blob = new Blob(recorderChunksRef.current, { type: rec.mimeType || "audio/webm" });
        recorderChunksRef.current = [];
        const transcribe = transcribeRef.current;
        if (!transcribe || blob.size < 800) {
          resolve("");
          return;
        }
        try {
          resolve((await transcribe(blob)).trim());
        } catch {
          resolve("");
        }
      };
      try {
        rec.stop();
      } catch {
        resolve("");
      }
    });
  }, []);

  const flushUtterance = useCallback(async () => {
    clearDebounce();
    let text = currentDraft();
    if (!text && serverSttRef.current) {
      setPhase("processing");
      text = await stopServerRecording();
      setInterim("");
    }
    utteranceBufferRef.current = "";
    latestInterimRef.current = "";
    setInterim("");
    if (!text || disabledRef.current || processingRef.current) return;

    const forced = forceSubmitRef.current;
    forceSubmitRef.current = false;

    if (!forced && text.length < MIN_COMFORTABLE_CHARS && shortWaitAttemptsRef.current < 1) {
      shortWaitAttemptsRef.current += 1;
      utteranceBufferRef.current = text;
      setInterim(text);
      scheduleEndOfTurnRef.current(true);
      return;
    }
    shortWaitAttemptsRef.current = 0;

    if (text === lastSubmittedRef.current) {
      if (liveRef.current && !speakingRef.current) beginListeningRef.current();
      return;
    }

    processingRef.current = true;
    lastSubmittedRef.current = text;
    lastSpeakKeyRef.current = "";
    recognitionRef.current?.stop();
    setPhase("processing");
    try {
      await onTranscriptRef.current(text);
    } catch {
      lastSubmittedRef.current = "";
      if (liveRef.current && !speakingRef.current) {
        setTimeout(() => beginListeningRef.current(), 350);
      }
    } finally {
      processingRef.current = false;
    }
  }, [clearDebounce, currentDraft, stopServerRecording]);

  const scheduleEndOfTurnRef = useRef<(shortFragment?: boolean) => void>(() => {});

  const scheduleEndOfTurn = useCallback(
    (shortFragment = false) => {
      if (disabledRef.current || processingRef.current || speakingRef.current) return;
      clearDebounce();
      const draft = currentDraft();
      if (!draft) return;

      const pause =
        shortFragment || draft.length < MIN_COMFORTABLE_CHARS ? SHORT_FRAGMENT_PAUSE_MS : UTTERANCE_PAUSE_MS;

      setAwaitingSilence(true);
      debounceRef.current = setTimeout(() => {
        void flushUtterance();
      }, pause);
    },
    [clearDebounce, currentDraft, flushUtterance],
  );

  scheduleEndOfTurnRef.current = scheduleEndOfTurn;

  const scheduleListenRef = useRef<() => void>(() => {});
  const beginListeningRef = useRef<() => void>(() => {});

  const beginListening = useCallback(() => {
    if (disabledRef.current || processingRef.current || speakingRef.current || micPausedRef.current) return;
    if (!liveRef.current) return;

    const Ctor = speechRecognitionCtor();
    if (!Ctor) {
      const transcribe = transcribeRef.current;
      if (!transcribe || !navigator.mediaDevices?.getUserMedia) {
        setPhase("unsupported");
        setSpeechSupported(false);
        return;
      }
      stopSpeaking();
      serverSttRef.current = true;
      setPhase("listening");
      setInterim("Recording — tap Done speaking when finished.");
      void (async () => {
        try {
          recorderRef.current?.stop();
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          recorderStreamRef.current = stream;
          recorderChunksRef.current = [];
          const rec = new MediaRecorder(stream);
          recorderRef.current = rec;
          rec.ondataavailable = (ev) => {
            if (ev.data.size > 0) recorderChunksRef.current.push(ev.data);
          };
          rec.start(250);
        } catch {
          setPhase("unsupported");
          setSpeechSupported(false);
        }
      })();
      return;
    }

    serverSttRef.current = false;
    stopSpeaking();
    recognitionRef.current?.abort();
    if (!utteranceBufferRef.current) {
      resultIndexRef.current = 0;
    }
    latestInterimRef.current = "";
    setInterim(utteranceBufferRef.current);
    setPhase("listening");

    const rec = new Ctor();
    recognitionRef.current = rec;
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-IN";

    rec.onresult = (ev) => {
      let finals = "";
      let partial = "";
      for (let i = resultIndexRef.current; i < ev.results.length; i++) {
        const r = ev.results[i];
        const t = r[0]?.transcript ?? "";
        if (r.isFinal) {
          finals += t;
          resultIndexRef.current = i + 1;
        } else {
          partial += t;
        }
      }
      if (finals) {
        const chunk = finals.replace(/\s+/g, " ").trim();
        if (chunk) utteranceBufferRef.current = `${utteranceBufferRef.current} ${chunk}`.trim();
        latestInterimRef.current = "";
      } else {
        latestInterimRef.current = partial.replace(/\s+/g, " ").trim();
      }

      const display = `${utteranceBufferRef.current} ${latestInterimRef.current}`.trim();
      setInterim(display);

      if (finals.trim() || partial.trim()) {
        const shortBurst = Boolean(finals.trim()) && display.length < MIN_COMFORTABLE_CHARS;
        scheduleEndOfTurn(shortBurst);
      }
    };

    rec.onerror = (ev) => {
      if (ev.error === "no-speech" && liveRef.current) {
        scheduleListenRef.current();
        return;
      }
      if (liveRef.current && !processingRef.current && !speakingRef.current) {
        setPhase("listening");
        scheduleListenRef.current();
      } else {
        setPhase("idle");
      }
    };

    rec.onend = () => {
      recognitionRef.current = null;
      if (liveRef.current && !processingRef.current && !speakingRef.current) {
        setTimeout(() => scheduleListenRef.current(), 400);
      }
    };

    try {
      rec.start();
    } catch {
      setTimeout(() => scheduleListenRef.current(), 500);
    }
  }, [scheduleEndOfTurn, stopSpeaking]);

  scheduleListenRef.current = beginListening;
  beginListeningRef.current = beginListening;

  const submitAnswer = useCallback(() => {
    forceSubmitRef.current = true;
    clearDebounce();
    void flushUtterance();
  }, [clearDebounce, flushUtterance]);

  const startLiveMode = useCallback(() => {
    lastSubmittedRef.current = "";
    shortWaitAttemptsRef.current = 0;
    if (disabledRef.current) return;
    liveRef.current = true;
    setLiveMode(true);
    beginListening();
  }, [beginListening]);

  const stopLiveMode = useCallback(() => {
    liveRef.current = false;
    setLiveMode(false);
    clearDebounce();
    recorderRef.current?.stop();
    recorderStreamRef.current?.getTracks().forEach((t) => t.stop());
    recorderRef.current = null;
    recorderStreamRef.current = null;
    bargeStreamRef.current?.getTracks().forEach((t) => t.stop());
    bargeStreamRef.current = null;
    stopBargeInMonitor();
    void bargeCtxRef.current?.close();
    bargeCtxRef.current = null;
    serverSttRef.current = false;
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    utteranceBufferRef.current = "";
    latestInterimRef.current = "";
    setInterim("");
    if (!processingRef.current && !speakingRef.current) setPhase("idle");
  }, [clearDebounce, stopBargeInMonitor]);

  useEffect(() => () => stopLiveMode(), [stopLiveMode]);

  const setFetchTts = useCallback((fn: FetchInterviewerTts | undefined) => {
    fetchTtsRef.current = fn;
  }, []);

  const setMicMuted = useCallback(
    (muted: boolean) => {
      micPausedRef.current = muted;
      if (muted) {
        clearDebounce();
        recognitionRef.current?.abort();
        recognitionRef.current = null;
        if (!processingRef.current && !speakingRef.current) setPhase("idle");
      } else if (liveRef.current && speakingRef.current) {
        startBargeInMonitor();
      } else if (liveRef.current && !processingRef.current && !speakingRef.current) {
        beginListening();
      }
    },
    [beginListening, clearDebounce, startBargeInMonitor],
  );

  const speak = useCallback(
    async (text: string, audioBase64?: string, mime?: string, messageId?: string) => {
      const key = audioBase64
        ? `audio:${audioBase64.slice(0, 64)}`
        : messageId
          ? `msg:${messageId}`
          : `text:${text.trim()}`;
      if (key.length > 8 && key === lastSpeakKeyRef.current) return;

      const seq = ++speakSeqRef.current;
      stopSpeaking();
      clearDebounce();
      recognitionRef.current?.abort();
      if (!text.trim() && !audioBase64) {
        if (liveRef.current && !micPausedRef.current) beginListening();
        return;
      }
      speakingRef.current = true;
      setPhase("speaking");
      setTtsBuffering(true);
      if (liveRef.current && !micPausedRef.current) startBargeInMonitor();
      try {
        await playInterviewerSpeech(text, audioBase64, mime, fetchTtsRef.current, messageId);
        if (seq === speakSeqRef.current) lastSpeakKeyRef.current = key;
      } finally {
        setTtsBuffering(false);
        stopBargeInMonitor();
        if (seq !== speakSeqRef.current) return;
        speakingRef.current = false;
        if (liveRef.current && !micPausedRef.current) {
          setPhase("listening");
          setTimeout(() => beginListening(), 400);
        } else if (micPausedRef.current) {
          setPhase("idle");
        } else {
          setPhase("idle");
        }
      }
    },
    [beginListening, clearDebounce, startBargeInMonitor, stopBargeInMonitor, stopSpeaking],
  );

  const replayLine = useCallback(
    async (messageId: string, text: string) => {
      lastSpeakKeyRef.current = "";
      await speak(text, undefined, undefined, messageId);
    },
    [speak],
  );

  return {
    phase,
    interim,
    liveMode,
    speechSupported,
    awaitingSilence,
    ttsBuffering,
    startLiveMode,
    stopLiveMode,
    speak,
    stopSpeaking,
    interruptSpeaking,
    replayLine,
    submitAnswer,
    setFetchTts,
    setMicMuted,
  };
}
