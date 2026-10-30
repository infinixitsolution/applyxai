import { useEffect } from "react";
import { LiveInterviewCoachHost, LiveInterviewCoachProvider } from "../../features/LiveInterviewCoach";
import { liveInterviewDesktop } from "../../lib/liveInterviewDesktop";

/** Desktop-only route: frameless Electron window for the floating coach (not inside the main app). */
export function LiveInterviewCoachOverlayPage() {
  useEffect(() => {
    const html = document.documentElement;
    const body = document.body;
    const prevHtml = html.style.background;
    const prevBody = body.style.background;
    html.style.background = "transparent";
    body.style.background = "transparent";
    return () => {
      html.style.background = prevHtml;
      body.style.background = prevBody;
    };
  }, []);

  useEffect(() => {
    void liveInterviewDesktop()?.sync?.();
  }, []);

  return (
    <LiveInterviewCoachProvider>
      <div className="relative h-screen w-screen overflow-hidden bg-transparent">
        <LiveInterviewCoachHost detached />
      </div>
    </LiveInterviewCoachProvider>
  );
}
