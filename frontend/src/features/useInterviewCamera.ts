import { useEffect, useRef, useState } from "react";

export type CameraStatus = "pending" | "active" | "denied" | "unavailable" | "insecure" | "unsupported";

export type CameraIssue =
  | "permission_denied"
  | "not_found"
  | "in_use"
  | "not_secure"
  | "unknown";

function classifyGetUserMediaError(error: unknown): CameraIssue {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") return "permission_denied";
    if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") return "not_found";
    if (error.name === "NotReadableError" || error.name === "TrackStartError") return "in_use";
    if (error.name === "SecurityError") return "not_secure";
  }
  return "unknown";
}

function statusForIssue(issue: CameraIssue): CameraStatus {
  switch (issue) {
    case "permission_denied":
      return "denied";
    case "not_found":
      return "unavailable";
    case "in_use":
      return "unavailable";
    case "not_secure":
      return "insecure";
    default:
      return "denied";
  }
}

async function openCamera(): Promise<MediaStream> {
  const ideal: MediaStreamConstraints = {
    video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: false,
  };
  try {
    return await navigator.mediaDevices.getUserMedia(ideal);
  } catch (first) {
    if (first instanceof DOMException && first.name === "OverconstrainedError") {
      return navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    }
    throw first;
  }
}

/** Local camera preview for the candidate panel (video only; mic stays with speech recognition). */
export function useInterviewCamera(enabled = true) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [status, setStatus] = useState<CameraStatus>(enabled ? "pending" : "unsupported");
  const [issue, setIssue] = useState<CameraIssue | null>(null);
  const [streamTick, setStreamTick] = useState(0);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled || typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setStatus("unsupported");
      setIssue(null);
      return;
    }
    if (typeof window !== "undefined" && !window.isSecureContext) {
      setStatus("insecure");
      setIssue("not_secure");
      return;
    }
    let cancelled = false;
    setStatus("pending");
    setIssue(null);

    void (async () => {
      try {
        const stream = await openCamera();
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        setStreamTick((n) => n + 1);
        setStatus("active");
        setIssue(null);
      } catch (error) {
        if (!cancelled) {
          const kind = classifyGetUserMediaError(error);
          setIssue(kind);
          setStatus(statusForIssue(kind));
        }
      }
    })();

    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      const el = videoRef.current;
      if (el) el.srcObject = null;
    };
  }, [enabled, attempt]);

  useEffect(() => {
    const el = videoRef.current;
    const stream = streamRef.current;
    if (!el || !stream) return;
    el.srcObject = stream;
    void el.play().catch(() => {});
  }, [streamTick, status]);

  const retry = () => {
    if (!enabled) return;
    setStatus("pending");
    setIssue(null);
    setAttempt((n) => n + 1);
  };

  return { videoRef, status, issue, retry };
}

export function cameraStatusMessage(status: CameraStatus, issue: CameraIssue | null): string {
  if (status === "denied" && issue === "permission_denied") {
    return "Camera blocked — click the camera icon in the address bar, choose Allow, then Try again.";
  }
  if (status === "insecure" || issue === "not_secure") {
    return "Camera needs a secure page — open the app at http://127.0.0.1:5173 (not an IP or http://localhost mismatch).";
  }
  if (issue === "not_found") {
    return "No camera found on this device. You can turn video off and continue the interview.";
  }
  if (issue === "in_use") {
    return "Camera is in use by another app. Close it, then Try again.";
  }
  if (status === "denied") {
    return "Could not start the camera. Check browser site permissions for this site.";
  }
  if (status === "unavailable") {
    return "Camera unavailable. Turn video off to continue without on-camera feedback.";
  }
  return "Starting camera…";
}
