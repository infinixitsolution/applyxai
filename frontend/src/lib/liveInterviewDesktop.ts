import type { LiveInterviewTurn } from "../types";

export type LiveInterviewCoachPhase = "idle" | "waiting" | "listening" | "answering" | "problem";

export type LiveInterviewDesktopEvent =
  | { type: "phase"; phase: LiveInterviewCoachPhase; message?: string }
  | { type: "session"; sessionId: string; transcript?: LiveInterviewTurn[]; startedAt?: string | null }
  | { type: "transcript"; transcript: LiveInterviewTurn[] }
  | { type: "answer"; text: string; done?: boolean }
  | { type: "ended"; message: string; ok: boolean }
  | { type: "coachUi"; panelOpen: boolean };

export type LiveInterviewStartOptions = {
  token: string;
  applicationId?: string | null;
  resume?: boolean;
};

export interface LiveInterviewDesktopApi {
  start: (options: LiveInterviewStartOptions) => Promise<{ sessionId: string }>;
  end: (sessionId: string) => Promise<{ ok: boolean; message: string }>;
  endActive?: () => Promise<{ ok: boolean; message: string }>;
  probeAudio: () => Promise<{ ok: boolean; message: string }>;
  status: () => Promise<{ active: boolean; sessionId: string | null }>;
  sync: () => Promise<{ active: boolean; sessionId: string | null }>;
  concealCoach?: () => Promise<void>;
  showCoach?: () => Promise<void>;
  reconnectAudio?: () => Promise<{ active: boolean; sessionId: string | null }>;
  moveCoachWindow?: (deltaX: number, deltaY: number) => Promise<void>;
  resizeCoachWindow?: (deltaWidth: number) => Promise<void>;
  onEvent: (listener: (event: LiveInterviewDesktopEvent) => void) => () => void;
}

export function liveInterviewDesktop(): LiveInterviewDesktopApi | null {
  return window.applyxaiDesktop?.liveInterview ?? null;
}
