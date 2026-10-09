const STORAGE_PREFIX = "applyxai_candidate_welcome_v1:";

export function candidateWelcomeStorageKey(userId: string): string {
  return `${STORAGE_PREFIX}${userId}`;
}

export function hasSeenCandidateWelcome(userId: string): boolean {
  try {
    return localStorage.getItem(candidateWelcomeStorageKey(userId)) === "1";
  } catch {
    return true;
  }
}

export function markCandidateWelcomeSeen(userId: string): void {
  try {
    localStorage.setItem(candidateWelcomeStorageKey(userId), "1");
  } catch {
    /* private mode / blocked storage */
  }
}
