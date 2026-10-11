"""Hear a live call (system audio + microphone) and show a conversation popup."""

from __future__ import annotations

import io
import queue
import threading
import wave
from datetime import datetime, timezone

import tkinter as tk

RATE = 16000
CHUNK_SECONDS = 0.25
# Bursts shorter than this (clicks, coughs, fan noise) are not worth a transcription call.
MIN_VOICED_CHUNKS = 3
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
                args=(loopback, loop_rate, "interviewer", 0.01, 3),
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


def _latest_turn(transcript: list[dict], role: str) -> dict:
    for turn in reversed(transcript):
        if turn.get("role") == role:
            return turn
    return {}


def _latest(transcript: list[dict], role: str) -> str:
    return str(_latest_turn(transcript, role).get("text") or "").strip()


def _parse_time(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _clock(at, started_at) -> str:
    """mm:ss since the session started, or the local time when the start is unknown."""
    moment = _parse_time(at)
    if moment is None:
        return ""
    start = _parse_time(started_at)
    if start is None:
        return moment.astimezone().strftime("%H:%M")
    seconds = max(0, int((moment - start).total_seconds()))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


# Windows draws this exact colour as see-through, so nothing else may use it.
_PAGE = "#fe01fe"
_TEXT = "#111111"
_HEADER = "#172c5a"
_ACCENT = "#7b93ff"
_QUESTION = {"fill": "#f2f6ff", "outline": "#c6d6f4", "label": "#2459d8", "time": "#55617a", "avatar": "#4f6ef0"}
_ANSWER = {"fill": "#f1fbf7", "outline": "#b9e3d3", "label": "#11804f", "time": "#55617a", "avatar": "#1fa37a"}


def _round_rect(canvas: tk.Canvas, x1, y1, x2, y2, radius, **kwargs):
    r = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class _RoundCard(tk.Canvas):
    """A rounded, bordered card. `body` holds the content; `stretch` cards fill the height they are given."""

    def __init__(
        self, parent: tk.Misc, *, fill: str, outline: str, bg: str,
        stretch: bool = False, pad: int = 14, radius: int = 16,
    ):
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0, height=40)
        self._fill, self._outline, self._pad, self._stretch = fill, outline, pad, stretch
        self._radius = radius
        self.body = tk.Frame(self, bg=fill)
        self._window = self.create_window(pad, pad, anchor="nw", window=self.body)
        self.bind("<Configure>", self._redraw)
        if not stretch:
            self.body.bind("<Configure>", self._fit_height, add="+")

    def _fit_height(self, _event=None) -> None:
        wanted = self.body.winfo_reqheight() + self._pad * 2
        if int(self.cget("height")) != wanted:
            self.configure(height=wanted)

    def _redraw(self, event) -> None:
        self.delete("shape")
        _round_rect(
            self, 1, 1, event.width - 2, event.height - 2, self._radius,
            fill=self._fill, outline=self._outline, width=1, tags="shape",
        )
        self.tag_lower("shape")
        options = {"width": max(10, event.width - self._pad * 2)}
        if self._stretch:
            options["height"] = max(10, event.height - self._pad * 2)
        self.itemconfigure(self._window, **options)


def _avatar_canvas(parent: tk.Misc, bg: str, scale: float) -> tk.Canvas:
    size = round(40 * scale)
    return tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0, bd=0)


def _person_avatar(parent: tk.Misc, bg: str, color: str, scale: float = 1.0) -> tk.Canvas:
    c = _avatar_canvas(parent, bg, scale)
    c.create_oval(1, 1, 39, 39, fill=color, outline=color)
    c.create_oval(14, 9, 26, 21, fill="white", outline="white")
    c.create_arc(9, 22, 31, 42, start=0, extent=180, fill="white", outline="white")
    c.create_oval(1, 1, 39, 39, outline=color, width=3)
    c.scale("all", 0, 0, scale, scale)
    return c


def _robot_avatar(parent: tk.Misc, bg: str, color: str, scale: float = 1.0) -> tk.Canvas:
    c = _avatar_canvas(parent, bg, scale)
    c.create_oval(1, 1, 39, 39, fill=color, outline=color)
    c.create_line(20, 8, 20, 13, fill="white", width=2)
    c.create_oval(18, 6, 22, 10, fill="white", outline="white")
    _round_rect(c, 10, 13, 30, 29, 5, fill="white", outline="white")
    c.create_rectangle(7, 18, 10, 24, fill="white", outline="white")
    c.create_rectangle(30, 18, 33, 24, fill="white", outline="white")
    c.create_oval(14, 17, 18, 21, fill=color, outline=color)
    c.create_oval(22, 17, 26, 21, fill=color, outline=color)
    c.create_line(17, 25, 23, 25, fill=color, width=2)
    c.scale("all", 0, 0, scale, scale)
    return c


def _work_area(win: tk.Misc) -> tuple[int, int, int, int]:
    """Screen area above the taskbar as (left, top, right, bottom)."""
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        pass
    return 0, 0, win.winfo_screenwidth(), win.winfo_screenheight() - 48


_LAUNCHER = "#2459d8"
_MAX_BUBBLES = 40
_YOU = {"fill": "#ffffff", "outline": "#d6dbe4", "label": "#475569"}


class ConversationPopup:
    """Chat-style assistant: a round button in the bottom-right corner opens and hides the conversation."""

    def __init__(self, root: tk.Misc, started_at: str | None = None):
        self._started_at = started_at
        self._answer = ""
        self._shown = 0
        self._open = True
        self._unread = False
        self._empty: tk.Widget | None = None
        self._pending: tk.Frame | None = None

        self.launcher = tk.Toplevel(root)
        self.win = tk.Toplevel(root)
        for window in (self.launcher, self.win):
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            try:
                window.attributes("-transparentcolor", _PAGE)
            except tk.TclError:
                pass
            window.configure(bg=_PAGE)
        self.win.title("ApplyXAI Interview Assistant")
        self._k = k = max(1.0, self.win.winfo_fpixels("1i") / 96)
        self._s = lambda value: round(value * k)

        self._build_launcher()
        self._build_panel()
        self._place()
        self._show_empty("Hi! I'm listening. When the interviewer asks a question, an English answer will appear here.")

    def _build_launcher(self) -> None:
        size = self._s(60)
        self._button = tk.Canvas(
            self.launcher, width=size, height=size, bg=_PAGE, highlightthickness=0, bd=0, cursor="hand2",
        )
        self._button.pack()
        self._button.bind("<Button-1>", lambda _e: self.toggle())
        self._draw_launcher()

    def _draw_launcher(self) -> None:
        c, s = self._button, self._s
        size = s(60)
        c.delete("all")
        c.create_oval(2, 2, size - 2, size - 2, fill=_LAUNCHER, outline=_LAUNCHER)
        if self._open:
            mid = size / 2
            c.create_line(mid - s(9), mid - s(4), mid, mid + s(5), mid + s(9), mid - s(4),
                          fill="white", width=max(2, s(3)), capstyle="round", joinstyle="round")
        else:
            _round_rect(c, s(16), s(17), s(44), s(39), s(8), fill="white", outline="white")
            c.create_polygon(s(21), s(37), s(19), s(45), s(28), s(38), fill="white", outline="white")
            for x in (s(23), s(30), s(37)):
                c.create_oval(x - s(2), s(26), x + s(2), s(30), fill=_LAUNCHER, outline=_LAUNCHER)
        if self._unread:
            c.create_oval(size - s(18), s(3), size - s(4), s(17), fill="#22c55e", outline="white", width=2)

    def _build_panel(self) -> None:
        s = self._s
        header = tk.Canvas(self.win, height=s(62), bg=_PAGE, highlightthickness=0, bd=0)
        header.pack(fill="x")
        avatar = _robot_avatar(header, _HEADER, "#1fa37a", self._k)
        header.create_window(s(14), s(31), anchor="w", window=avatar)
        brand = ("Segoe UI", 13, "bold")
        apply_id = header.create_text(s(64), s(22), text="Apply", anchor="w", fill="white", font=brand)
        header.create_text(header.bbox(apply_id)[2] + s(5), s(22), text="XAI", anchor="w", fill=_ACCENT, font=brand)
        self._status_id = header.create_text(
            s(64), s(43), text="● Waiting for the interview", anchor="w", fill="#fcd34d", font=("Segoe UI", 9),
        )
        self._hide_id = header.create_text(0, s(31), text="—", anchor="e", fill="white", font=("Segoe UI", 13, "bold"))
        header.tag_bind(self._hide_id, "<Button-1>", lambda _e: self.toggle())
        header.tag_bind(self._hide_id, "<Enter>", lambda _e: header.configure(cursor="hand2"))
        header.tag_bind(self._hide_id, "<Leave>", lambda _e: header.configure(cursor=""))
        header.bind("<Configure>", self._draw_header)
        self._header = header

        foot = _RoundCard(self.win, fill="#ffffff", outline=_YOU["outline"], bg=_PAGE, pad=s(8), radius=s(14))
        foot.pack(side="bottom", fill="x", pady=(s(8), 0))
        tk.Label(
            foot.body, text="Scroll up for earlier questions",
            bg="#ffffff", fg="#475569", font=("Segoe UI", 9),
        ).pack(side="left", padx=(s(4), 0))
        copy = tk.Label(
            foot.body, text="Copy last answer", bg=_ANSWER["fill"], fg=_ANSWER["label"],
            font=("Segoe UI", 9, "bold"), padx=s(10), pady=s(3), cursor="hand2",
        )
        copy.pack(side="right")
        copy.bind("<Button-1>", lambda _e: self._copy())

        self.chat = tk.Canvas(self.win, bg=_PAGE, highlightthickness=0, bd=0)
        self.chat.pack(fill="both", expand=True, pady=(s(10), 0))
        self.feed = tk.Frame(self.chat, bg=_PAGE)
        self._feed_id = self.chat.create_window(0, 0, anchor="nw", window=self.feed)
        self.feed.bind("<Configure>", lambda _e: self.chat.configure(scrollregion=self.chat.bbox("all")))
        self.chat.bind("<Configure>", lambda e: self.chat.itemconfigure(self._feed_id, width=e.width))
        self._bind_wheel(self.chat)

    def _draw_header(self, event) -> None:
        s = self._s
        self._header.delete("bar")
        _round_rect(self._header, 0, 0, event.width - 1, event.height - 1, s(16),
                    fill=_HEADER, outline=_HEADER, tags="bar")
        self._header.tag_lower("bar")
        self._header.coords(self._hide_id, event.width - s(18), s(29))

    def _place(self) -> None:
        s = self._s
        left, top, right, bottom = _work_area(self.win)
        margin, button = s(20), s(60)
        self.launcher.geometry(f"{button}x{button}+{right - margin - button}+{bottom - margin - button}")
        width = min(s(400), right - left - margin * 2)
        height = min(s(600), bottom - top - button - margin * 3)
        x = right - margin - width
        y = bottom - margin - button - s(12) - height
        self.win.geometry(f"{width}x{height}+{x}+{y}")

    def _bind_wheel(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._wheel)
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def _wheel(self, event) -> None:
        self.chat.yview_scroll(int(-event.delta / 120) or (-1 if event.delta > 0 else 1), "units")

    def _scroll_to_end(self) -> None:
        self.chat.update_idletasks()
        self.chat.configure(scrollregion=self.chat.bbox("all"))
        self.chat.yview_moveto(1.0)

    def _bubble(self, *, role: str, title: str, text: str, at=None) -> tk.Frame:
        s, k = self._s, self._k
        styles = {"interviewer": _QUESTION, "suggestion": _ANSWER}
        style = styles.get(role, _YOU)
        row = tk.Frame(self.feed, bg=_PAGE)
        row.pack(fill="x", pady=(0, s(10)))
        if role == "interviewer":
            _person_avatar(row, _PAGE, _QUESTION["avatar"], k * 0.8).pack(side="left", anchor="n")
            card_pad = (s(8), s(36))
        elif role == "suggestion":
            _robot_avatar(row, _PAGE, _ANSWER["avatar"], k * 0.8).pack(side="left", anchor="n")
            card_pad = (s(8), 0)
        else:
            card_pad = (s(72), 0)
        card = _RoundCard(row, fill=style["fill"], outline=style["outline"], bg=_PAGE, pad=s(11), radius=s(14))
        card.pack(side="left", fill="x", expand=True, padx=card_pad)
        body = card.body
        body.columnconfigure(0, weight=1)
        tk.Label(body, text=title, bg=style["fill"], fg=style["label"], font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w",
        )
        stamp = _clock(at, self._started_at)
        if role == "suggestion":
            copy = tk.Label(
                body, text="Copy", bg=style["fill"], fg=style["label"], font=("Segoe UI", 8, "underline"),
                cursor="hand2",
            )
            copy.grid(row=0, column=1, sticky="e", padx=(0, s(8)))
            copy.bind("<Button-1>", lambda _e: self._copy(row.message.cget("text")))
        if stamp:
            tk.Label(body, text=stamp, bg=style["fill"], fg="#55617a", font=("Segoe UI", 8)).grid(
                row=0, column=2, sticky="e",
            )
        size = 12 if role == "suggestion" else 11 if role == "interviewer" else 10
        paragraphs = [part.strip() for part in text.replace("\r", "").split("\n") if part.strip()]
        message = tk.Label(
            body, text="\n\n".join(paragraphs) or text, bg=style["fill"], fg=_TEXT,
            font=("Segoe UI", size), justify="left", anchor="w", wraplength=s(260),
        )
        message.grid(row=1, column=0, columnspan=3, sticky="we", pady=(s(3), 0))
        body.bind("<Configure>", lambda e: message.configure(wraplength=max(s(120), e.width - s(4))), add="+")
        row.message = message
        self._bind_wheel(row)
        return row

    def begin_answer(self) -> None:
        """Open an answer bubble that update_answer fills in while the answer streams."""
        if not self.win.winfo_exists():
            return
        if self._empty is not None:
            self._empty.destroy()
            self._empty = None
        self._pending = self._bubble(role="suggestion", title="AI Assistant · say this", text="…")
        self._set_status("Writing your answer…", "#fcd34d")
        self._scroll_to_end()

    def update_answer(self, text: str) -> None:
        if self._pending is None or not self._pending.winfo_exists():
            return
        self._pending.message.configure(text=text.strip() or "…")
        self._answer = text.strip()
        self._scroll_to_end()

    def finish_answer(self) -> None:
        if not self.win.winfo_exists():
            return
        if self._pending is not None and self._answer:
            self._set_status("Answer ready", "#86efac")
            if not self._open:
                self._unread = True
                self._draw_launcher()

    def _show_empty(self, text: str) -> None:
        if self._shown:
            return
        if self._empty is not None:
            self._empty.destroy()
        self._empty = self._bubble(role="suggestion", title="AI Assistant", text=text)

    def _set_status(self, text: str, color: str) -> None:
        self._header.itemconfigure(self._status_id, text="● " + text, fill=color)

    def toggle(self) -> None:
        self._open = not self._open
        if self._open:
            self.win.deiconify()
            self.win.lift()
            self._unread = False
            self._scroll_to_end()
        else:
            self.win.withdraw()
        self._draw_launcher()

    def set_lines(self, transcript: list[dict]) -> None:
        if not self.win.winfo_exists():
            return
        if len(transcript) < self._shown:
            for child in self.feed.winfo_children():
                child.destroy()
            self._shown = 0
        new_turns = transcript[max(self._shown, len(transcript) - _MAX_BUBBLES):]
        if new_turns and self._empty is not None:
            self._empty.destroy()
            self._empty = None
        titles = {"interviewer": "Interviewer", "suggestion": "AI Assistant · say this", "candidate": "You said"}
        for turn in new_turns:
            text = str(turn.get("text") or "").strip()
            role = str(turn.get("role") or "")
            if role == "suggestion" and self._pending is not None and self._pending.winfo_exists():
                self._pending.message.configure(text=text)
                self._pending = None
                continue
            if text:
                self._bubble(role=role, title=titles.get(role, "Note"), text=text, at=turn.get("at"))
        rows = self.feed.winfo_children()
        for row in rows[: max(0, len(rows) - _MAX_BUBBLES)]:
            row.destroy()
        self._shown = len(transcript)
        self._answer = _latest(transcript, "suggestion")
        if new_turns:
            self._scroll_to_end()
            if not self._open and any(turn.get("role") == "suggestion" for turn in new_turns):
                self._unread = True
                self._draw_launcher()
        last = transcript[-1].get("role") if transcript else ""
        if last == "suggestion":
            self._set_status("Answer ready", "#86efac")
        elif transcript:
            self._set_status("Listening", "#86efac")

    def set_waiting(self) -> None:
        if not self.win.winfo_exists():
            return
        self._set_status("Waiting for the interview audio", "#fcd34d")
        self._show_empty("The session is open. An English answer will appear here when the interviewer speaks.")

    def set_listening(self) -> None:
        if not self.win.winfo_exists():
            return
        self._set_status("Listening", "#86efac")
        self._show_empty("Hi! I'm listening. When the interviewer asks a question, an English answer will appear here.")

    def set_problem(self, message: str) -> None:
        if not self.win.winfo_exists():
            return
        self._set_status(message[:70], "#fca5a5")

    def _copy(self, value: str | None = None) -> None:
        text = value or self._answer
        if not text:
            return
        self.win.clipboard_clear()
        self.win.clipboard_append(text)

    def close(self) -> None:
        for window in (self.win, self.launcher):
            if window.winfo_exists():
                window.destroy()
