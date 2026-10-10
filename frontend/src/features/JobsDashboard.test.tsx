import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/Toast";
import { JobsDashboard } from "./JobsDashboard";

const ok = (data: unknown) => new Response(JSON.stringify({ success: true, data }), { status: 200 });

const dashboardStats = {
  applications_by_status: { applied: 0, failed: 0, skipped: 0, queued: 0, running: 0, discovered: 0, external: 0, cancelled: 0 },
  total_applied: 0, applied_today: 0, success_rate: 0, daily: [], top_companies: [], recent_applications: [],
  automation: { active: null, last: null },
  usage: {
    plan: "free", plan_name: "Free", period: "2026-10", resets_at: "2026-11-01T00:00:00+00:00",
    applications: { used: 0, limit: 10, remaining: 10 },
    resumes: { used: 0, limit: 1, remaining: 1 },
    jobs_discovered: 0, runtime_seconds: 0, limit_reached: false,
  },
};

describe("JobsDashboard", () => {
  it("shows empty state when no jobs", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input).split("?")[0]!;
      if (url.includes("/dashboard/stats")) return ok(dashboardStats);
      if (url.includes("/preferences/options")) {
        return ok({
          search: { experience_level: [], job_type: [], on_site: [], date_posted: [], sort_by: [], extra_fields: [] },
          application_fields: [],
        });
      }
      if (url.includes("/jobs")) return ok({ items: [], total: 0, page: 1, page_size: 20 });
      throw new Error(`unexpected fetch: ${url}`);
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ToastProvider>
            <JobsDashboard />
          </ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/No jobs found/i)).toBeTruthy();
  });
});
