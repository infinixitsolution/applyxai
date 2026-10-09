import { useEffect } from "react";

/** Adds `.is-in` to reference home.css reveal targets when they enter the viewport. */
export function useMarketingReveal(deps: unknown[] = []) {
  useEffect(() => {
    const nodes = document.querySelectorAll("[data-reveal], .live-stat, .home-mock");
    if (!nodes.length) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      nodes.forEach((n) => n.classList.add("is-in"));
      return;
    }
    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("is-in");
          obs.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -6% 0px", threshold: 0.06 },
    );
    nodes.forEach((n) => obs.observe(n));
    return () => obs.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-scan when landing CMS loads
  }, deps);
}
