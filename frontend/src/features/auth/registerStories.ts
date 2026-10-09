import type { AuthHighlight } from "./AuthPageLayout";

export const REGISTER_STORY = {
  candidate: {
    kicker: "Free to start",
    title: "Create a candidate account in under a minute.",
    lead: "Upload a master resume, set LinkedIn search preferences, and install the agent when you're ready to apply.",
    highlights: [
      { title: "AI tailoring", description: "Optional per-job resume — no invented experience" },
      { title: "Smart skipping", description: "Blacklists and low match scores before any form opens" },
      { title: "Full history", description: "Export applications and screening answers anytime" },
    ] as AuthHighlight[],
    trustSub: "Built for LinkedIn job search",
  },
  institute: {
    kicker: "Campus & training",
    title: "Give students a guided path to LinkedIn applications.",
    lead: "Institute accounts manage seats, invite students, and see adoption — while each student runs automation on their own machine.",
    highlights: [
      { title: "Seat management", description: "Bulk invites from an institute dashboard" },
      { title: "Student-owned data", description: "Each student keeps their own login and applications" },
      { title: "Partner codes", description: "Referral codes supported at signup" },
    ] as AuthHighlight[],
    trustLabel: "Institute program",
    trustSub: "Reviewed applications · campus onboarding",
    showLinkedInTrust: false,
  },
  partner: {
    kicker: "Referral network",
    title: "Partner with ApplyXAI and earn on referred institutes.",
    lead: "Submit your organisation details. Our team reviews partner applications and enables referral tools after approval.",
    highlights: [
      { title: "Referral links", description: "Unique codes for institute signups" },
      { title: "Commissions", description: "Tracking in the partner workspace" },
      { title: "Co-branded onboarding", description: "Smoother campus rollouts for referred institutes" },
    ] as AuthHighlight[],
    trustLabel: "Partner program",
    trustSub: "Application review · referral dashboard",
    showLinkedInTrust: false,
  },
} as const;
