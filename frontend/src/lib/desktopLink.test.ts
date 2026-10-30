import { describe, expect, it, vi } from "vitest";
import { postLoginPath } from "./desktopLink";
import type { User } from "../types";

const candidate: User = {
  id: "u1",
  email: "a@b.com",
  first_name: "A",
  last_name: "B",
  is_admin: false,
  is_verified: true,
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
};

describe("postLoginPath", () => {
  it("sends desktop candidates to Automation by default", () => {
    vi.stubGlobal("window", { applyxaiDesktop: { isDesktop: true } });
    expect(postLoginPath(candidate, null)).toBe("/app/automation");
    vi.unstubAllGlobals();
  });

  it("honors explicit next on desktop", () => {
    vi.stubGlobal("window", { applyxaiDesktop: { isDesktop: true } });
    expect(postLoginPath(candidate, "/app/billing")).toBe("/app/billing");
    vi.unstubAllGlobals();
  });

  it("uses normal home on web", () => {
    vi.stubGlobal("window", { applyxaiDesktop: undefined });
    expect(postLoginPath(candidate, null)).toBe("/app");
    vi.unstubAllGlobals();
  });
});
