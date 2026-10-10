import { describe, expect, it } from "vitest";
import { mergeMockInterviewPresenter } from "./mockInterviewPresenter";

describe("mergeMockInterviewPresenter", () => {
  it("fills legacy presenter without glb_url", () => {
    const merged = mergeMockInterviewPresenter({
      mode: "digital_human_3d",
      image_url: "/mock-interviewer-host.jpg",
    });
    expect(merged.glb_url).toBe("/portrait");
    expect(merged.image_url).toBe("/mock-interviewer-host.jpg");
  });

  it("uses defaults when presenter is missing", () => {
    const merged = mergeMockInterviewPresenter(null);
    expect(merged.glb_url).toBe("/portrait");
    expect(merged.image_url).toBe("/interviewer-portrait.png");
  });
});
