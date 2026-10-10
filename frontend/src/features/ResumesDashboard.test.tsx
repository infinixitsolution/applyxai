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

  it("shows resume rows when API returns files", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/resumes/templates")) return ok({ templates: [] });
      if (url.includes("/resumes") && !url.includes("templates")) {
        return ok({
          resumes: [{
            id: "r1",
            name: "Main CV",
            filename: "cv.pdf",
            is_default: true,
            file_type: "pdf",
            file_size: 1200,
            created_at: "2026-10-01T00:00:00Z",
          }],
          limit: 3,
        });
      }
      if (url.includes("/dashboard/stats")) {
        return ok({
          applications_by_status: { applied: 0, failed: 0, skipped: 0, queued: 0, running: 0, discovered: 0, external: 0, cancelled: 0 },
          total_applied: 0, applied_today: 0, success_rate: 0, daily: [], top_companies: [], recent_applications: [],
          automation: { active: null, last: null },
          usage: {
            plan: "free", plan_name: "Free", period: "2026-10", resets_at: "2026-11-01T00:00:00+00:00",
            applications: { used: 0, limit: 10, remaining: 10 },
            resumes: { used: 1, limit: 3, remaining: 2 },
            jobs_discovered: 0, runtime_seconds: 0, limit_reached: false,
          },
        });
      }
      if (url.includes("/automation/overview")) {
        return ok({
          devices: [],
          active: null,
          recent: [],
          agent_online: false,
          readiness: { ready: false, problems: [] },
          usage: {
            plan: "free", plan_name: "Free", period: "2026-10", resets_at: "2026-11-01T00:00:00+00:00",
            applications: { used: 0, limit: 10, remaining: 10 },
            resumes: { used: 1, limit: 3, remaining: 2 },
            jobs_discovered: 0, runtime_seconds: 0, limit_reached: false,
          },
          resume_tailor: { mode: "default", resume_ai_available: false, master_skills_ready: false, can_tailor: false },
        });
      }
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
    expect(await screen.findByText("Default for automation")).toBeTruthy();
    expect(screen.getAllByText("Main CV").length).toBeGreaterThan(0);
  });
});
