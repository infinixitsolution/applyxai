import { describe, expect, it } from "vitest";
import { notificationLink } from "./notificationLink";

describe("notificationLink", () => {
  it("maps legacy candidate paths under /app", () => {
    expect(notificationLink("/automation")).toBe("/app/automation");
    expect(notificationLink("/automation?pending=1")).toBe("/app/automation?pending=1");
    expect(notificationLink("/billing")).toBe("/app/billing");
  });

  it("leaves /app paths unchanged", () => {
    expect(notificationLink("/app/billing")).toBe("/app/billing");
    expect(notificationLink("/app/applications")).toBe("/app/applications");
  });

  it("leaves public invite routes unchanged", () => {
    expect(notificationLink("/invite/abc-token")).toBe("/invite/abc-token");
  });

  it("rejects unsafe links", () => {
    expect(notificationLink("")).toBe("/app/notifications");
    expect(notificationLink("//evil.example")).toBe("/app/notifications");
    expect(notificationLink("https://evil.example")).toBe("/app/notifications");
  });
});
