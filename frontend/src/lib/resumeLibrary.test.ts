import { describe, expect, it } from "vitest";
import type { Resume } from "../types";
import { isBuiltResume, splitResumeLibrary } from "./resumeLibrary";

const base = (over: Partial<Resume>): Resume =>
  ({
    id: "1",
    name: "x",
    filename: "x.pdf",
    file_type: "pdf",
    file_size: 1,
    is_default: false,
    created_at: "2026-10-01T00:00:00Z",
    ...over,
  }) as Resume;

describe("resumeLibrary", () => {
  it("splits uploads from built copies", () => {
    const upload = base({ id: "u", ai_metadata: {} });
    const tailored = base({ id: "t", ai_metadata: { generated_by: "ai" } });
    const auto = base({ id: "a", ai_metadata: { generated_by: "automation" } });
    const { built, uploads } = splitResumeLibrary([upload, tailored, auto]);
    expect(uploads.map((r) => r.id)).toEqual(["u"]);
    expect(built.map((r) => r.id)).toEqual(["t", "a"]);
    expect(isBuiltResume(tailored)).toBe(true);
    expect(isBuiltResume(upload)).toBe(false);
  });
});
