import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/Toast";
import { ResumesDashboard } from "./ResumesDashboard";

const ok = (data: unknown) => new Response(JSON.stringify({ success: true, data }), { status: 200 });

describe("ResumesDashboard", () => {
  it("lists resume section", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/resumes/templates")) return ok({ templates: [] });
      if (url.includes("/resumes")) return ok({ resumes: [], limit: 3 });
      if (url.includes("/dashboard/stats")) {
        return ok({
          applications_by_status: { applied: 0, failed: 0, skipped: 0, queued: 0, running: 0, discovered: 0, external: 0, cancelled: 0 },
          total_applied: 0, applied_today: 0, success_rate: 0, daily: [], top_companies: [], recent_applications: [],
          automation: { active: null, last: null },
          usage: {
            plan: "free", plan_name: "Free", period: "2026-10", resets_at: "2026-11-01T00:00:00+00:00",
            applications: { used: 0, limit: 10, remaining: 10 },
            resumes: { used: 0, limit: 1, remaining: 1 },
            jobs_discovered: 0, runtime_seconds: 0, limit_reached: false,
          },
        });
      }
      if (url.includes("/automation/overview")) return ok({ devices: [], active_run: null, recent_runs: [], runs: [] });
      throw new Error(url);
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ToastProvider>
            <ResumesDashboard />
          </ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Resumes" })).toBeTruthy();
  });
});
