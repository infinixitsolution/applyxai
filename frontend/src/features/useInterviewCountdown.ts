import { useEffect, useRef, useState } from "react";

export function formatInterviewCountdown(totalSeconds: number): string {
  const clamped = Math.max(0, totalSeconds);
  const m = Math.floor(clamped / 60);
  const s = clamped % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/** Count down to `endsAt` ISO string; calls `onElapsed` once when time hits zero. */
export function useInterviewCountdown(endsAt: string | undefined, enabled: boolean, onElapsed: () => void) {
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const onElapsedRef = useRef(onElapsed);
  onElapsedRef.current = onElapsed;

  useEffect(() => {
    if (!enabled || !endsAt) {
      setSecondsLeft(null);
      return;
    }
    let fired = false;
    const endMs = new Date(endsAt).getTime();

    const tick = () => {
      const left = Math.max(0, Math.ceil((endMs - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left <= 0 && !fired) {
        fired = true;
        onElapsedRef.current();
      }
    };

    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [endsAt, enabled]);

  return secondsLeft;
}
