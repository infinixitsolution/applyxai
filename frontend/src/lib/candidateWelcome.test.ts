import { afterEach, describe, expect, it } from "vitest";
import {
  candidateWelcomeStorageKey,
  hasSeenCandidateWelcome,
  markCandidateWelcomeSeen,
} from "./candidateWelcome";

describe("candidateWelcome storage", () => {
  afterEach(() => localStorage.clear());

  it("tracks seen state per user", () => {
    const key = candidateWelcomeStorageKey("user-1");
    expect(key).toContain("user-1");
    expect(hasSeenCandidateWelcome("user-1")).toBe(false);
    markCandidateWelcomeSeen("user-1");
    expect(hasSeenCandidateWelcome("user-1")).toBe(true);
    expect(hasSeenCandidateWelcome("user-2")).toBe(false);
  });
});
