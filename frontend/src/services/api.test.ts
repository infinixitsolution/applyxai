import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, buildUrl, fieldErrors, onSessionExpired, request } from "./api";

function json(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
}
const ok = (data: unknown) => json(200, { success: true, data });
const fail = (status: number, code: string, message = "nope", details?: unknown) =>
  json(status, { success: false, error: { code, message, details } });

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  document.cookie = "applyxai_csrf=csrf-123; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
  onSessionExpired(null);
});

const headersOf = (call: number) => fetchMock.mock.calls[call][1].headers as Record<string, string>;

describe("request", () => {
  it("unwraps the success envelope", async () => {
    fetchMock.mockResolvedValueOnce(ok({ hello: "world" }));
    await expect(request("/thing")).resolves.toEqual({ hello: "world" });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/thing");
    expect(fetchMock.mock.calls[0][1].credentials).toBe("same-origin");
  });

  it("sends the CSRF header on mutations only", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(ok({})));
    await request("/x");
    await request("/x", { method: "POST", body: { a: 1 } });
    await request("/x", { method: "DELETE" });
    expect(headersOf(0)["X-CSRF-Token"]).toBeUndefined();
    expect(headersOf(1)["X-CSRF-Token"]).toBe("csrf-123");
    expect(headersOf(1)["Content-Type"]).toBe("application/json");
    expect(fetchMock.mock.calls[1][1].body).toBe('{"a":1}');
    expect(headersOf(2)["X-CSRF-Token"]).toBe("csrf-123");
  });

  it("lets the browser set multipart headers for uploads", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(ok({})));
    const form = new FormData();
    form.append("file", new Blob(["x"]), "cv.pdf");
    await request("/resumes", { method: "POST", form });
    expect(headersOf(0)["Content-Type"]).toBeUndefined();
    expect(fetchMock.mock.calls[0][1].body).toBe(form);
  });

  it("turns error envelopes into ApiError with field details", async () => {
    fetchMock.mockResolvedValueOnce(fail(422, "VALIDATION_ERROR", "Invalid", [{ field: "body.job_type", message: "Invalid job type" }]));
    const error = (await request("/x", { method: "PUT", body: {} }).catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("VALIDATION_ERROR");
    expect(error.status).toBe(422);
    expect(fieldErrors(error)).toEqual({ job_type: "Invalid job type" });
  });

  it("reports non-JSON responses (e.g. proxy errors) without crashing", async () => {
    fetchMock.mockResolvedValueOnce(new Response("<html>Bad Gateway</html>", { status: 502 }));
    await expect(request("/x")).rejects.toMatchObject({ code: "SERVER_UNAVAILABLE", status: 502 });
  });

  it("reports network failures", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(request("/x")).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });
});

describe("session refresh", () => {
  it("refreshes once on 401 and retries the request", async () => {
    fetchMock
      .mockResolvedValueOnce(fail(401, "UNAUTHORIZED"))
      .mockResolvedValueOnce(ok({ user: {} }))           // /auth/refresh
      .mockResolvedValueOnce(ok({ n: 1 }));
    await expect(request("/dashboard/stats")).resolves.toEqual({ n: 1 });
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual(["/api/dashboard/stats", "/api/auth/refresh", "/api/dashboard/stats"]);
    expect(headersOf(1)["X-CSRF-Token"]).toBe("csrf-123");
  });

  it("shares one refresh between concurrent requests", async () => {
    let releaseRefresh: (r: Response) => void = () => {};
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/auth/refresh") return new Promise<Response>((resolve) => { releaseRefresh = resolve; });
      const retried = fetchMock.mock.calls.filter((c) => c[0] === url).length > 1;
      return Promise.resolve(retried ? ok({ url }) : fail(401, "UNAUTHORIZED"));
    });
    const both = Promise.all([request("/a"), request("/b")]);
    await vi.waitFor(() => expect(fetchMock.mock.calls.filter((c) => c[0] === "/api/auth/refresh")).toHaveLength(1));
    releaseRefresh(ok({ user: {} }));
    await expect(both).resolves.toEqual([{ url: "/api/a" }, { url: "/api/b" }]);
    expect(fetchMock.mock.calls.filter((c) => c[0] === "/api/auth/refresh")).toHaveLength(1);
  });

  it("signals session expiry when the refresh fails", async () => {
    const expired = vi.fn();
    onSessionExpired(expired);
    fetchMock.mockResolvedValueOnce(fail(401, "UNAUTHORIZED")).mockResolvedValueOnce(fail(401, "SESSION_EXPIRED"));
    await expect(request("/profile")).rejects.toMatchObject({ status: 401 });
    expect(expired).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("never refreshes for a failed login", async () => {
    fetchMock.mockResolvedValueOnce(fail(401, "INVALID_CREDENTIALS", "Incorrect email or password"));
    await expect(request("/auth/login", { method: "POST", body: {} })).rejects.toMatchObject({ code: "INVALID_CREDENTIALS" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("buildUrl", () => {
  it("skips empty values and repeats arrays", () => {
    expect(buildUrl("/applications", { q: "", status: ["applied", "failed"], page: 2, x: undefined, y: null }))
      .toBe("/api/applications?status=applied&status=failed&page=2");
  });

  it("encodes values", () => {
    expect(buildUrl("/jobs", { q: "C++ & Go" })).toBe("/api/jobs?q=C%2B%2B+%26+Go");
  });
});
