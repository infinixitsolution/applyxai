import { describe, expect, it } from "vitest";
import { consumeNext, homeFor, rememberNext, safeNext, storedNext, withNext } from "../auth/session";
import { fromDraft, toDraft } from "../components/DynamicField";
import { appLink } from "../components/NotificationBell";
import { resumeFileProblem } from "../features/ResumeManager";
import type { FieldMeta } from "../types";
import { formatBytes, formatMoney, safeExternalUrl } from "./format";

const field = (type: FieldMeta["type"], options?: string[]): FieldMeta =>
  ({ key: "k", label: "Thing", type, help: "", section: "Profile", advanced: false, options });

describe("safeExternalUrl", () => {
  it.each([
    ["https://www.linkedin.com/jobs/view/1", "https://www.linkedin.com/jobs/view/1"],
    ["http://example.com", "http://example.com/"],
    ["javascript:alert(1)", null],
    ["JaVaScRiPt:alert(1)", null],
    ["data:text/html,<script>", null],
    ["/relative", null],
    ["", null],
  ])("%s", (input, expected) => expect(safeExternalUrl(input)).toBe(expected));
});

describe("safeNext (post-login redirect)", () => {
  it.each([
    ["/app/resumes", "/app/resumes"],
    ["//evil.example", "/app"],
    ["https://evil.example", "/app"],
    ["/\\evil.example", "/app"],
    [null, "/app"],
  ])("%s", (input, expected) => expect(safeNext(input)).toBe(expected));
});

describe("homeFor", () => {
  it("sends each workspace to its portal", () => {
    const base = { id: "u1", email: "a@b.c", first_name: "A", last_name: "B", is_verified: true, is_admin: false, created_at: "", last_login_at: null };
    expect(homeFor({ ...base, is_admin: true })).toBe("/admin");
    expect(homeFor({ ...base, workspace: "institute" })).toBe("/institute");
    expect(homeFor({ ...base, workspace: "partner" })).toBe("/partner");
    expect(homeFor({ ...base, workspace: "app" })).toBe("/app");
  });
});

describe("invite next persistence", () => {
  it("stores only same-site paths and appends them to auth URLs", () => {
    rememberNext("/invite/abc");
    expect(storedNext()).toBe("/invite/abc");
    rememberNext("//evil.example");
    expect(storedNext()).toBe("/invite/abc");
    expect(withNext("/login?verified=1", "/invite/abc")).toBe("/login?verified=1&next=%2Finvite%2Fabc");
    expect(withNext("/register", "/invite/abc")).toBe("/register?next=%2Finvite%2Fabc");
    expect(withNext("/login", "//evil")).toBe("/login");
    expect(consumeNext()).toBe("/invite/abc");
    expect(storedNext()).toBeNull();
  });
});

describe("appLink", () => {
  it("maps backend paths into the app", () => {
    expect(appLink("/automation")).toBe("/app/automation");
    expect(appLink("/app/billing")).toBe("/app/billing");
    expect(appLink("")).toBe("/app/notifications");
    expect(appLink("//evil.example")).toBe("/app/notifications");
    expect(appLink("https://evil.example")).toBe("/app/notifications");
  });
});

describe("engine field drafts", () => {
  it("round-trips numbers and rejects non-integers", () => {
    expect(toDraft(field("number"), 30)).toBe("30");
    expect(fromDraft(field("number"), " 45 ")).toBe(45);
    expect(fromDraft(field("number"), "")).toBeNull();
    expect(() => fromDraft(field("number"), "1.5")).toThrow("whole number");
    expect(() => fromDraft(field("number"), "lots")).toThrow();
  });

  it("uses tri-state booleans so 'not set' keeps the engine default", () => {
    expect(toDraft(field("bool"), undefined)).toBe("");
    expect(toDraft(field("bool"), false)).toBe("false");
    expect(fromDraft(field("bool"), "")).toBeNull();
    expect(fromDraft(field("bool"), "true")).toBe(true);
    expect(fromDraft(field("bool"), "false")).toBe(false);
  });

  it("keeps '' only when it's a real option", () => {
    expect(fromDraft(field("select", ["Male", "Female", ""]), "")).toBe("");
    expect(fromDraft(field("select", ["Yes", "No"]), "")).toBeNull();
    expect(fromDraft(field("select", ["Yes", "No"]), "No")).toBe("No");
  });

  it("treats empty text and lists as unset", () => {
    expect(fromDraft(field("text"), "  ")).toBeNull();
    expect(fromDraft(field("list"), [])).toBeNull();
    expect(fromDraft(field("list"), ["a"])).toEqual(["a"]);
  });
});

describe("resumeFileProblem", () => {
  const file = (name: string, size: number) => new File([new Uint8Array(size)], name);
  it("accepts PDF and DOCX within the limit", () => {
    expect(resumeFileProblem(file("CV.PDF", 10))).toBeNull();
    expect(resumeFileProblem(file("cv.docx", 10))).toBeNull();
  });
  it("rejects other types, empty files and large files", () => {
    expect(resumeFileProblem(file("cv.doc", 10))).toMatch(/PDF or DOCX/);
    expect(resumeFileProblem(file("cv.pdf", 0))).toMatch(/empty/);
    expect(resumeFileProblem(file("cv.pdf", 5 * 1024 * 1024 + 1))).toMatch(/5 MB/);
  });
});

describe("formatting", () => {
  it("formats sizes and money", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(1.5 * 1024 * 1024)).toBe("1.5 MB");
    expect(formatMoney(49900, "INR")).toBe("₹499");
  });
});
