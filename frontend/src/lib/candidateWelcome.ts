const DISMISS_PREFIX = "applyxai_candidate_welcome_dismissed_v1:";

export function candidateWelcomeDismissKey(userId: string): string {
  return `${DISMISS_PREFIX}${userId}`;
}

/** Call when the user signs in so the instructions popup can show again this session. */
export function resetCandidateWelcomeForLogin(userId: string): void {
  try {
    sessionStorage.removeItem(candidateWelcomeDismissKey(userId));
  } catch {
    /* blocked storage */
  }
}

export function isCandidateWelcomeDismissed(userId: string): boolean {
  try {
    return sessionStorage.getItem(candidateWelcomeDismissKey(userId)) === "1";
  } catch {
    return false;
  }
}

export function dismissCandidateWelcomeForSession(userId: string): void {
  try {
    sessionStorage.setItem(candidateWelcomeDismissKey(userId), "1");
  } catch {
    /* blocked storage */
  }
}
