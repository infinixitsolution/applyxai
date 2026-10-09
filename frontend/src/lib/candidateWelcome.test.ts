import { afterEach, describe, expect, it } from "vitest";
import {
  candidateWelcomeDismissKey,
  dismissCandidateWelcomeForSession,
  isCandidateWelcomeDismissed,
  resetCandidateWelcomeForLogin,
} from "./candidateWelcome";

describe("candidateWelcome session", () => {
  afterEach(() => sessionStorage.clear());

  it("shows again after each login reset", () => {
    dismissCandidateWelcomeForSession("user-1");
    expect(isCandidateWelcomeDismissed("user-1")).toBe(true);
    resetCandidateWelcomeForLogin("user-1");
    expect(isCandidateWelcomeDismissed("user-1")).toBe(false);
    expect(candidateWelcomeDismissKey("user-1")).toContain("user-1");
  });
});
