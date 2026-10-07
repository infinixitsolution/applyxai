import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/Toast";
import type { AutomationOverview, AutomationRun } from "../../types";
import { AutomationPage } from "./Automation";

const usage = {
  plan: "free", plan_name: "Free", period: "2026-10", resets_at: "2026-11-01T00:00:00+00:00",
  applications: { used: 3, limit: 10, remaining: 7 }, resumes: { used: 1, limit: 1, remaining: 0 },
  jobs_discovered: 5, runtime_seconds: 0, limit_reached: false,
};
const device = { id: "d1", name: "Work laptop", platform: "Windows 10", agent_version: "0.1.0",
                 paired_at: "2026-10-07T00:00:00+00:00", last_seen_at: "2026-10-07T00:00:00+00:00", online: true };
const run: AutomationRun = {
  id: "r1", status: "running", control: "run", dry_run: false, created_at: "2026-10-07T04:00:00+00:00",
  started_at: "2026-10-07T04:00:05+00:00", finished_at: null, current_job: "Looking at Python Developer at Acme",
  total_jobs: 4, successful_count: 2, failed_count: 1, skipped_count: 1, error_message: "", stop_reason: "", claimed: true,
};

function overview(over: Partial<AutomationOverview> = {}): AutomationOverview {
  return { active: null, recent: [], devices: [device], agent_online: true,
           readiness: { ready: true, problems: [] }, usage, ...over };
}

const ok = (data: unknown, status = 200) => new Response(JSON.stringify({ success: true, data }), { status });

function mockApi(routes: Record<string, unknown | ((init?: RequestInit) => unknown)>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.split("?")[0];
    const key = `${init?.method ?? "GET"} ${path}`;
    if (!(key in routes)) throw new Error(`unexpected request: ${key}`);
    const value = routes[key];
    return ok(typeof value === "function" ? (value as (i?: RequestInit) => unknown)(init) : value);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter><ToastProvider><AutomationPage /></ToastProvider></MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("AutomationPage", () => {
  it("explains what's missing and won't start until setup is done", async () => {
    mockApi({ "GET /api/automation": overview({ devices: [], readiness: { ready: false, problems: ["Add your phone number."] } }) });
    renderPage();
    expect(await screen.findByText("Add your phone number.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start run" })).toBeDisabled();
    expect(screen.getByText(/Connect the ApplyXAI desktop agent/)).toBeInTheDocument();
  });

  it("starts a practice run", async () => {
    let body: unknown;
    const fetchMock = mockApi({
      "GET /api/automation": overview(),
      "POST /api/automation/start": (init?: RequestInit) => { body = JSON.parse(String(init?.body)); return { ...run, status: "queued" }; },
    });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("checkbox", { name: /Practice run/ }));
    await user.click(screen.getByRole("button", { name: "Start run" }));
    expect(body).toEqual({ dry_run: true });
    expect(fetchMock.mock.calls.some(([u, i]) => u === "/api/automation/start" && (i?.headers as Record<string, string>)["X-CSRF-Token"] !== undefined)).toBe(true);
  });

  it("shows a live run with its log and lets you pause and stop it", async () => {
    const calls: string[] = [];
    mockApi({
      "GET /api/automation": overview({ active: run, recent: [run] }),
      "GET /api/automation/r1/logs": { items: [
        { seq: 1, ts: "2026-10-07T04:00:05+00:00", level: "info", event: "run_started", message: "Run started. Searching for: Python Developer" },
        { seq: 2, ts: "2026-10-07T04:00:06+00:00", level: "warning", event: "login_required", message: "Sign in to LinkedIn in the browser window ApplyXAI opened." },
      ], next_after: 2 },
      "POST /api/automation/r1/pause": () => { calls.push("pause"); return { ...run, control: "pause" }; },
      "POST /api/automation/r1/stop": () => { calls.push("stop"); return { ...run, control: "stop", stop_reason: "user" }; },
    });
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText("Looking at Python Developer at Acme")).toBeInTheDocument();
    const log = await screen.findByRole("list", { name: "Run activity" });
    expect(within(log).getByText(/Sign in to LinkedIn/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Pause" }));
    expect(calls).toEqual(["pause"]);
    await user.click(screen.getByRole("button", { name: "Stop" }));
    await user.click(screen.getByRole("button", { name: "Stop run" }));
    expect(calls).toEqual(["pause", "stop"]);
  });

  it("gives a pairing code and the exact commands to connect a computer", async () => {
    mockApi({
      "GET /api/automation": overview({ devices: [] }),
      "POST /api/automation/devices/pairing-code": { code: "ABCD-EFGH", expires_at: new Date(Date.now() + 600_000).toISOString() },
      "GET /api/automation/devices": { devices: [] },
    });
    const user = userEvent.setup();
    renderPage();
    const [headerButton] = await screen.findAllByRole("button", { name: /Connect a computer/ });
    await user.click(headerButton);
    expect(await screen.findByTestId("pairing-code")).toHaveTextContent("ABCD-EFGH");
    expect(screen.getByText(`venv/bin/python -m agent pair --server ${window.location.origin} --code ABCD-EFGH`)).toBeInTheDocument();
    expect(screen.getByText("venv/bin/python -m agent run")).toBeInTheDocument();
  });
});
