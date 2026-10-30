export type LiveInterviewStartOptions = {
  token: string;
  applicationId?: string | null;
  /** Reconnect to the in-memory desktop session without ending other server sessions. */
  resume?: boolean;
};

export type LiveInterviewStatus = { active: boolean; sessionId: string | null };

export type LiveInterviewCoachPhase = "idle" | "waiting" | "listening" | "answering" | "problem";

export type LiveInterviewTurn = { role: string; text: string; at?: string };

export type LiveInterviewDesktopEvent =
  | { type: "phase"; phase: LiveInterviewCoachPhase; message?: string }
  | { type: "session"; sessionId: string; transcript?: LiveInterviewTurn[]; startedAt?: string | null }
  | { type: "transcript"; transcript: LiveInterviewTurn[] }
  | { type: "answer"; text: string; done?: boolean }
  | { type: "ended"; message: string; ok: boolean }
  | { type: "coachUi"; panelOpen: boolean };
