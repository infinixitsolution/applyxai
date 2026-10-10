/** Mascot PNG (same asset as app sidebar Logo) for jsPDF. */
export async function loadApplyXaiMascotDataUrl(): Promise<string | null> {
  try {
    const base = import.meta.env.BASE_URL || "/";
    const path = `${base}mascot.png`.replace(/\/{2,}/g, "/");
    const url = path.startsWith("http") ? path : new URL(path, window.location.origin).href;
    const res = await fetch(url);
    if (!res.ok) return null;
    const blob = await res.blob();
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : null);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

export const PDF_WATERMARK_TEXT = "ApplyXAI";
