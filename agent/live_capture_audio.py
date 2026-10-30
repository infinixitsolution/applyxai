"""WASAPI loopback + microphone capture for live interview (no GUI dependencies)."""

from __future__ import annotations

import io
import queue
import threading
import wave

RATE = 16000
CHUNK_SECONDS = 0.25
# Bursts shorter than this (clicks, coughs, fan noise) are not worth a transcription call.
MIN_VOICED_CHUNKS = 2
_CAPTURE_RATES = (48000, 44100, 16000)


def _mono(samples):
    import numpy as np

    arr = np.asarray(samples, dtype="float32")
    if arr.ndim < 2 or arr.shape[1] == 1:
        return arr.reshape(-1)
    energy = np.mean(np.square(arr), axis=0)
    return arr[:, int(np.argmax(energy))]


def _resample(samples, source_rate: int):
    import numpy as np

    arr = _mono(samples)
    if source_rate == RATE or arr.size == 0:
        return arr.astype("float32")
    if source_rate % RATE == 0:
        factor = source_rate // RATE
        usable = arr.size - (arr.size % factor)
        if usable <= 0:
            return arr.astype("float32")
        return arr[:usable].reshape(-1, factor).mean(axis=1).astype("float32")
    target = max(1, int(arr.shape[0] * RATE / source_rate))
    edges = np.linspace(0, arr.shape[0], target + 1).astype(int)
    out = np.empty(target, dtype="float32")
    for index in range(target):
        piece = arr[edges[index]:edges[index + 1]]
        out[index] = float(piece.mean()) if piece.size else 0.0
    return out


def _normalize(samples):
    import numpy as np

    arr = np.asarray(samples, dtype="float32")
    peak = float(np.max(np.abs(arr))) if arr.size else 0.0
    if 0.001 < peak < 0.25:
        arr = arr * (0.7 / peak)
    return np.clip(arr, -1.0, 1.0)


def _wav_bytes(samples, source_rate: int = RATE) -> bytes:
    import numpy as np

    arr = _normalize(_resample(samples, source_rate))
    pcm = (arr * 32767).astype("int16")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(pcm.tobytes())
    return buf.getvalue()


def _rms(samples) -> float:
    import numpy as np

    arr = np.asarray(samples, dtype="float32")
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(arr))))


def _prepare_com() -> None:
    """WASAPI calls fail with 0x800401f0 unless this thread has initialized COM."""
    import ctypes

    ole32 = ctypes.WinDLL("ole32")
    # Apartment-threaded matches Tk. RPC_E_CHANGED_MODE means COM is already up.
    for model in (0x2, 0x0):
        hr = ole32.CoInitializeEx(None, model) & 0xFFFFFFFF
        if hr in (0, 1) or hr == 0x80010106:
            return


def _loopback_devices():
    import soundcard as sc

    loopbacks = [mic for mic in sc.all_microphones(include_loopback=True) if getattr(mic, "isloopback", False)]
    ordered = list(loopbacks)
    try:
        speaker = sc.default_speaker()
        preferred = [mic for mic in loopbacks if mic.id == speaker.id or mic.name == speaker.name]
        ordered = preferred + [mic for mic in loopbacks if mic not in preferred]
        if not ordered:
            ordered = [sc.get_microphone(id=str(speaker.name), include_loopback=True)]
    except Exception:
        pass
    return ordered


def open_call_audio():
    """Return (microphone, sample_rate) for the default speaker loopback."""
    _prepare_com()
    errors: list[str] = []
    devices = _loopback_devices()
    if not devices:
        raise RuntimeError("No speaker loopback device. Check the default playback device.")
    for mic in devices:
        for rate in _CAPTURE_RATES:
            recorder = None
            try:
                recorder = mic.recorder(samplerate=rate, exclusive_mode=False)
                recorder.__enter__()
                recorder.record(numframes=max(1, int(rate * 0.05)))
                recorder.__exit__(None, None, None)
                return mic, rate
            except Exception as exc:
                errors.append(f"{getattr(mic, 'name', 'speaker')} at {rate} Hz: {exc}")
                if recorder is not None:
                    try:
                        recorder.__exit__(type(exc), exc, None)
                    except Exception:
                        pass
    detail = errors[0] if errors else "the playback device did not start"
    raise RuntimeError(detail)


def probe_call_audio() -> str | None:
    """None when speaker loopback can be recorded. Otherwise a short reason."""
    try:
        open_call_audio()
    except Exception as exc:
        return f"Couldn't capture call audio from the speakers. {exc}"
    return None


def _open_speech_mic():
    """A real microphone, never the speaker loopback, at a rate the device accepts."""
    import soundcard as sc

    mics = [mic for mic in sc.all_microphones(include_loopback=False) if not getattr(mic, "isloopback", False)]
    chosen = None
    try:
        default = sc.default_microphone()
        if default is not None and not getattr(default, "isloopback", False):
            chosen = default
    except Exception:
        chosen = None
    if chosen is None and mics:
        chosen = mics[0]
    if chosen is None:
        raise RuntimeError("No microphone found. Check the default recording device.")
    errors: list[str] = []
    for rate in _CAPTURE_RATES:
        recorder = None
        try:
            recorder = chosen.recorder(samplerate=rate, exclusive_mode=False)
            recorder.__enter__()
            recorder.record(numframes=max(1, int(rate * 0.05)))
            recorder.__exit__(None, None, None)
            return chosen, rate
        except Exception as exc:
            errors.append(str(exc))
            if recorder is not None:
                try:
                    recorder.__exit__(type(exc), exc, None)
                except Exception:
                    pass
    raise RuntimeError(errors[0] if errors else "The microphone did not start.")


class LiveCapture:
    """Cut speech on pauses and hand each clip to on_clip(speaker, wav_bytes)."""

    def __init__(self, on_clip, on_error=None):
        self.on_clip = on_clip
        self.on_error = on_error
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._level_lock = threading.Lock()
        self._loop_rms = 0.0
        self._outbox: queue.Queue = queue.Queue()

    def start(self) -> None:
        loopback, loop_rate = open_call_audio()
        mic, mic_rate = _open_speech_mic()
        self._threads = [
            threading.Thread(
                target=self._run,
                args=(loopback, loop_rate, "interviewer", 0.008, 2),
                daemon=True,
            ),
            threading.Thread(
                target=self._run,
                args=(mic, mic_rate, "candidate", 0.006, 6),
                daemon=True,
            ),
            threading.Thread(target=self._send_clips, daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._outbox.put(None)

    def _emit(self, speaker: str, chunks: list, sample_rate: int) -> None:
        import numpy as np

        self._outbox.put((speaker, _wav_bytes(np.concatenate(chunks, axis=0), sample_rate)))

    def _send_clips(self) -> None:
        """Uploads run here so recording never pauses while a clip is transcribed and answered."""
        while True:
            item = self._outbox.get()
            if item is None or self._stop.is_set():
                return
            speaker, audio = item
            try:
                self.on_clip(speaker, audio)
            except Exception as exc:
                if self.on_error:
                    self.on_error(str(exc))

    def _candidate_is_talking(self, rms: float) -> bool:
        with self._level_lock:
            loop = self._loop_rms
        if rms < 0.006:
            return False
        if loop >= 0.01 and rms < loop * 1.6:
            return False
        return True

    def _run(self, device, sample_rate: int, speaker: str, threshold: float, quiet_chunks: int) -> None:
        import numpy as np

        frames = int(sample_rate * CHUNK_SECONDS)
        speech: list = []
        voiced = 0
        quiet = 0

        def flush() -> None:
            nonlocal speech, voiced, quiet
            if voiced >= MIN_VOICED_CHUNKS:
                self._emit(speaker, speech, sample_rate)
            speech, voiced, quiet = [], 0, 0

        try:
            _prepare_com()
            with device.recorder(samplerate=sample_rate, exclusive_mode=False) as rec:
                while not self._stop.is_set():
                    chunk = np.asarray(rec.record(numframes=frames), dtype="float32")
                    rms = _rms(chunk)
                    if speaker == "interviewer":
                        with self._level_lock:
                            self._loop_rms = rms
                        loud = rms >= threshold
                    else:
                        loud = self._candidate_is_talking(rms)
                    if loud:
                        voiced += 1
                        quiet = 0
                        speech.append(chunk)
                    elif speech:
                        quiet += 1
                        speech.append(chunk)
                        if quiet >= quiet_chunks:
                            flush()
                    if len(speech) > int(25 / CHUNK_SECONDS):
                        flush()
        except Exception as exc:
            if self.on_error:
                self.on_error(f"{speaker} audio stopped: {exc}")
