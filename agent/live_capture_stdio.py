"""Stream live interview audio clips to stdout for ApplyXAI Desktop (Windows WASAPI loopback)."""

from __future__ import annotations

import struct
import sys
import threading
import time

from agent.live_capture_audio import LiveCapture, probe_call_audio

_CLIP_MAGIC = b"AXLC"


def _write_clip(speaker: str, wav: bytes) -> None:
    spk = speaker.encode("utf-8")
    if len(spk) > 200:
        spk = spk[:200]
    out = sys.stdout.buffer
    out.write(_CLIP_MAGIC)
    out.write(bytes([len(spk)]))
    out.write(spk)
    out.write(struct.pack(">I", len(wav)))
    out.write(wav)
    out.flush()


def run_capture() -> int:
    err = probe_call_audio()
    if err:
        sys.stderr.write(err + "\n")
        sys.stderr.flush()
        return 1

    stop = threading.Event()

    def on_error(msg: str) -> None:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()

    capture = LiveCapture(on_clip=lambda s, w: _write_clip(s, w), on_error=on_error)
    try:
        capture.start()
    except Exception as exc:
        sys.stderr.write(f"{exc}\n")
        sys.stderr.flush()
        return 1

    sys.stderr.write("ready\n")
    sys.stderr.flush()
    try:
        while not stop.wait(0.5):
            if not any(t.is_alive() for t in capture._threads):
                break
    finally:
        capture.stop()
    return 0


def run_probe() -> int:
    err = probe_call_audio()
    if err:
        sys.stderr.write(err + "\n")
        sys.stderr.flush()
        return 1
    sys.stderr.write("ok\n")
    sys.stderr.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        return 2
    if args[0] == "--live-capture-probe":
        return run_probe()
    if args[0] == "--live-capture":
        return run_capture()
    return 2
