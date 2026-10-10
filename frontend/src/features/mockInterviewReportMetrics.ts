import type { MockInterviewFeedback, MockInterviewSessionDetail } from "../types";

export type MockInterviewReportStats = {
  turns: number;
  candidateAnswers: number;
  questions: number;
  rubricScored: number;
  types: string;
  behaviorOverall: number | null;
  behaviorConcerns: number;
  presentationScore: number | null;
  conductIssueCount: number;
  framesAnalyzed: number | null;
  generatedAt: string | null;
};

export function buildMockInterviewReportStats(
  session: MockInterviewSessionDetail,
  feedback: MockInterviewFeedback,
): MockInterviewReportStats {
  const candidateMsgs = session.messages.filter((m) => m.role === "candidate");
  const interviewerMsgs = session.messages.filter((m) => m.role === "interviewer");
  const rubricScored = (feedback.rubric_scores ?? []).filter((r) => r.score != null).length;
  const behavioral = feedback.presentation?.behavioral_parameters ?? [];
  const behaviorConcerns = behavioral.filter((r) => r.detected || r.status === "concern").length;
  const snap = session.context_snapshot as Record<string, unknown>;
  const meta = feedback.analysis_meta;

  return {
    turns: session.turn_count,
    candidateAnswers: candidateMsgs.length,
    questions: interviewerMsgs.length,
    rubricScored,
    types: session.interview_types?.join(", ") || "mixed",
    behaviorOverall: feedback.presentation?.behavior_overall ?? null,
    behaviorConcerns,
    presentationScore:
      feedback.presentation?.available && feedback.presentation.overall_score != null
        ? feedback.presentation.overall_score
        : null,
    conductIssueCount: feedback.presentation?.professional_conduct?.issues?.length ?? 0,
    framesAnalyzed:
      meta?.presentation_frames_analyzed ??
      (typeof snap.presentation_frames_analyzed === "number" ? snap.presentation_frames_analyzed : null),
    generatedAt: meta?.generated_at ?? session.updated_at,
  };
}

export const ANALYSIS_PIPELINE_STEPS = [
  "Saving your transcript",
  "Scoring answers (100-parameter rubric)",
  "Analyzing on-camera behavior (55 parameters)",
  "Checking answer authenticity",
  "Generating coaching and report",
] as const;
