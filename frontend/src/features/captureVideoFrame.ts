/** Grab a JPEG data URL from a live video element (for presentation analysis). */
export function captureVideoFrame(video: HTMLVideoElement, quality = 0.72): string | null {
  if (video.readyState < 2 || !video.videoWidth) return null;
  const maxW = 640;
  const scale = Math.min(1, maxW / video.videoWidth);
  const w = Math.round(video.videoWidth * scale);
  const h = Math.round(video.videoHeight * scale);
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(video, 0, 0, w, h);
  try {
    return canvas.toDataURL("image/jpeg", quality);
  } catch {
    return null;
  }
}

const MAX_STORED = 12;

export function pushPresentationFrame(frames: string[], frame: string | null): string[] {
  if (!frame) return frames;
  const next = [...frames, frame];
  if (next.length <= MAX_STORED) return next;
  return next.slice(-MAX_STORED);
}
