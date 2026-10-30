import { describe, expect, it } from "vitest";
import { findDuplicatePatterns, mergeDuplicateQuestions } from "./customQuestionsDedupe";
import type { HumanQuestion } from "../types";

function q(partial: Partial<HumanQuestion> & Pick<HumanQuestion, "pattern">): HumanQuestion {
  return {
    match: "contains",
    answer: "",
    field_types: ["text"],
    verified: false,
    usage_count: 0,
    input_type: "text",
    ...partial,
    id: partial.id ?? crypto.randomUUID(),
  };
}

describe("mergeDuplicateQuestions", () => {
  it("merges same pattern with different casing", () => {
    const merged = mergeDuplicateQuestions([
      q({ id: "a", pattern: "Visa sponsorship?", answer: "No", usage_count: 3 }),
      q({ id: "b", pattern: "visa sponsorship?", answer: "No sponsorship needed", verified: true }),
    ]);
    expect(merged).toHaveLength(1);
    expect(merged[0]!.verified).toBe(true);
    expect(merged[0]!.usage_count).toBe(3);
  });

  it("keeps empty-pattern rows separate", () => {
    const merged = mergeDuplicateQuestions([q({ pattern: "" }), q({ pattern: "  " }), q({ pattern: "Unique" })]);
    expect(merged.filter((r) => r.pattern.trim())).toHaveLength(1);
    expect(merged.filter((r) => !r.pattern.trim())).toHaveLength(2);
  });
});

describe("findDuplicatePatterns", () => {
  it("flags duplicates only when pattern matches", () => {
    const rows = [q({ pattern: "A" }), q({ pattern: "a" }), q({ pattern: "B" })];
    expect(findDuplicatePatterns(rows).length).toBeGreaterThan(0);
  });
});
