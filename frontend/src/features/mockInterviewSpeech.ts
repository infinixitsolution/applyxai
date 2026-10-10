import { beginEstimatedSpeech, endEstimatedSpeech, playAnalysedAudio } from "./interviewerMotion";

const ttsCache = new Map<string, Promise<{ audio_base64: string; audio_mime: string }>>();

function playBase64Audio(audioBase64: string, mime: string): Promise<void> {
  endEstimatedSpeech();
  return playAnalysedAudio(audioBase64, mime);
}

function speakWithBrowser(text: string): Promise<void> {
  return new Promise((resolve) => {
    const synth = window.speechSynthesis;
    if (!synth || !text.trim()) {
      resolve();
      return;
    }
    synth.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "en-IN";
    utter.rate = 0.96;
    utter.pitch = 1.05;
    const voices = synth.getVoices();
    const preferred =
      voices.find((v) => /en-IN/i.test(v.lang) && /female|zira|neerja|heera/i.test(v.name)) ??
      voices.find((v) => /en-IN/i.test(v.lang)) ??
      voices.find((v) => /en-GB/i.test(v.lang));
    if (preferred) utter.voice = preferred;
    utter.onend = () => {
      endEstimatedSpeech();
      resolve();
    };
    utter.onerror = () => {
      endEstimatedSpeech();
      resolve();
    };
    beginEstimatedSpeech(text);
    synth.speak(utter);
  });
}

export type FetchInterviewerTts = (args: {
  messageId: string;
  text: string;
}) => Promise<{ audio_base64: string; audio_mime: string }>;

async function fetchTtsCached(cacheKey: string, fetchTts: FetchInterviewerTts, args: { messageId: string; text: string }) {
  let pending = ttsCache.get(cacheKey);
  if (!pending) {
    pending = fetchTts(args);
    ttsCache.set(cacheKey, pending);
    pending.catch(() => ttsCache.delete(cacheKey));
  }
  return pending;
}

/** Single audio path: server TTS when available; browser voice only as fallback (no parallel playback). */
export async function playInterviewerSpeech(
  text: string,
  audioBase64: string | undefined,
  mime: string | undefined,
  fetchTts?: FetchInterviewerTts,
  messageId?: string,
): Promise<void> {
  window.speechSynthesis?.cancel();
  endEstimatedSpeech();

  if (audioBase64) {
    await playBase64Audio(audioBase64, mime || "audio/mpeg");
    return;
  }

  const line = text.trim();
  if (!line) return;

  if (fetchTts && messageId) {
    try {
      const t = await fetchTtsCached(messageId, fetchTts, { messageId, text: line });
      if (t.audio_base64) {
        await playBase64Audio(t.audio_base64, t.audio_mime || "audio/mpeg");
        return;
      }
    } catch {
      await speakWithBrowser(line);
      return;
    }
  }

  await speakWithBrowser(line);
}
