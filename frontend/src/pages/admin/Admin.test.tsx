import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RequireAdmin } from "../../auth/session";
import { ToastProvider } from "../../components/Toast";
import type { AdminPlan, AdminRun, AdminUser, AdminUserDetail, User } from "../../types";
import { AdminRunsPage } from "./Lists";
import { AdminPlansPage } from "./Plans";
import { AdminUserPage, AdminUsersPage } from "./Users";

const me: User = {
  id: "admin-1", email: "boss@example.com", first_name: "", last_name: "", is_verified: true, is_admin: true,
  created_at: "2026-10-01T00:00:00+00:00", last_login_at: null,
};
const alice: AdminUser = {
  id: "u1", email: "alice@example.com", first_name: "Alice", last_name: "Doe", is_active: true, is_verified: true,
  is_admin: false, created_at: "2026-10-02T00:00:00+00:00", last_login_at: null, plan: "free", plan_name: "Free",
  applications_this_month: 4,
};
const usage = {
  plan: "free", plan_name: "Free", period: "2026-10", resets_at: "2026-11-01T00:00:00+00:00",
  applications: { used: 4, limit: 10, remaining: 6 }, resumes: { used: 1, limit: 1, remaining: 0 },
  jobs_discovered: 0, runtime_seconds: 0, limit_reached: false,
};
const noStatuses = { discovered: 0, queued: 0, running: 0, applied: 4, failed: 0, skipped: 0, external: 0, cancelled: 0 };
const detail = (over: Partial<AdminUserDetail> = {}): AdminUserDetail => ({
  user: alice, usage, subscription: null, subscriptions: [], payments: [], runs: [], devices: [],
  applications_by_status: noStatuses, resumes: 1, ...over,
});
const plans = [
  { code: "free", name: "Free", price_cents: 0, currency: "INR", interval: "month", limits: { applications_per_month: 10, resumes: 1 } },
  { code: "starter", name: "Starter", price_cents: 49900, currency: "INR", interval: "month", limits: { applications_per_month: 100, resumes: 3 } },
];

const ok = (data: unknown) => new Response(JSON.stringify({ success: true, data }), { status: 200 });

type Handler = unknown | ((init?: RequestInit, url?: string) => unknown);

function mockApi(routes: Record<string, Handler>) {
  const calls: { key: string; url: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
    calls.push({ key, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (!(key in routes)) throw new Error(`unexpected request: ${key}`);
    const value = routes[key];
    return ok(typeof value === "function" ? (value as (i?: RequestInit, u?: string) => unknown)(init, url) : value);
  }));
  return calls;
}

function renderAt(path: string, routes: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}><ToastProvider><Routes>{routes}</Routes></ToastProvider></MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("admin area", () => {
  it("keeps non-admins out", async () => {
    mockApi({ "GET /api/auth/me": { user: { ...me, is_admin: false } } });
    renderAt("/admin", <>
      <Route path="/admin" element={<RequireAdmin><p>secret admin page</p></RequireAdmin>} />
      <Route path="/app" element={<p>user dashboard</p>} />
    </>);
    expect(await screen.findByText("user dashboard")).toBeInTheDocument();
    expect(screen.queryByText("secret admin page")).not.toBeInTheDocument();
  });

  it("lists users and filters them by status", async () => {
    const calls = mockApi({
      "GET /api/admin/users": { items: [alice], total: 1, page: 1, page_size: 25 },
      "GET /api/plans": { plans },
    });
    renderAt("/admin/users", <Route path="/admin/users" element={<AdminUsersPage />} />);
    expect(await screen.findByRole("link", { name: "alice@example.com" })).toHaveAttribute("href", "/admin/users/u1");
    await userEvent.selectOptions(screen.getByLabelText("Status"), "disabled");
    await vi.waitFor(() => expect(calls.some((c) => c.url.includes("status=disabled"))).toBe(true));
  });

  it("disables an account only after confirming what it does", async () => {
    let current = detail();
    const calls = mockApi({
      "GET /api/auth/me": { user: me },
      "GET /api/plans": { plans },
      "GET /api/admin/users/u1": () => current,
      "PATCH /api/admin/users/u1": () => { current = detail({ user: { ...alice, is_active: false } }); return current; },
    });
    renderAt("/admin/users/u1", <Route path="/admin/users/:id" element={<AdminUserPage />} />);
    await userEvent.click(await screen.findByRole("switch", { name: "Can sign in" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("signed out everywhere");
    await userEvent.click(within(dialog).getByRole("button", { name: "Disable account" }));
    await vi.waitFor(() => expect(screen.getByRole("switch", { name: "Can sign in" })).toHaveAttribute("aria-checked", "false"));
    expect(calls.find((c) => c.key === "PATCH /api/admin/users/u1")?.body).toEqual({ is_active: false });
  });

  it("gives a complimentary plan", async () => {
    let current = detail();
    const calls = mockApi({
      "GET /api/auth/me": { user: me },
      "GET /api/plans": { plans },
      "GET /api/admin/users/u1": () => current,
      "POST /api/admin/users/u1/grant-plan": () => {
        current = detail({
          usage: { ...usage, plan: "starter", plan_name: "Starter" },
          subscription: { id: "s1", plan: { ...plans[1] }, status: "active", provider: "admin",
                          current_period_start: "2026-10-07T00:00:00+00:00", current_period_end: "2027-01-05T00:00:00+00:00",
                          cancel_at_period_end: true, created_at: "2026-10-07T00:00:00+00:00" },
        });
        return current;
      },
    });
    renderAt("/admin/users/u1", <Route path="/admin/users/:id" element={<AdminUserPage />} />);
    await userEvent.click(await screen.findByRole("button", { name: "Give a plan" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.selectOptions(within(dialog).getByLabelText("Plan"), "starter");
    await userEvent.selectOptions(within(dialog).getByLabelText("For"), "3");
    await userEvent.type(within(dialog).getByLabelText(/Note/), "Beta tester");
    await userEvent.click(within(dialog).getByRole("button", { name: "Give plan" }));
    expect(await screen.findByText("Complimentary")).toBeInTheDocument();
    expect(calls.find((c) => c.key.endsWith("/grant-plan"))?.body).toEqual({ plan: "starter", months: 3, note: "Beta tester" });
  });

  it("edits a plan's price in the currency's main unit and sends cents", async () => {
    const adminPlans: AdminPlan[] = plans.map((p, i) => ({ ...p, is_active: true, sort_order: i, provider_plan_id: "", subscribers: i }));
    const calls = mockApi({
      "GET /api/admin/plans": { plans: adminPlans },
      "PUT /api/admin/plans/starter": (init?: RequestInit) => ({ ...adminPlans[1], ...JSON.parse(String(init?.body)) }),
    });
    renderAt("/admin/plans", <Route path="/admin/plans" element={<AdminPlansPage />} />);
    const row = (await screen.findByText("Starter")).closest("tr")!;
    await userEvent.click(within(row).getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    const price = within(dialog).getByLabelText(/Price per month/);
    await userEvent.clear(price);
    await userEvent.type(price, "599");
    expect(dialog).toHaveTextContent("current subscriber keep their price");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /api/admin/plans/starter")).toBe(true));
    expect(calls.find((c) => c.key === "PUT /api/admin/plans/starter")?.body).toEqual({
      name: "Starter", price_cents: 59900, applications_per_month: 100, resumes: 3, is_active: true, sort_order: 1,
    });
  });

  it("stops a user's run after confirmation", async () => {
    const run: AdminRun = {
      id: "r1", status: "running", control: "run", dry_run: false, created_at: "2026-10-07T00:00:00+00:00",
      started_at: "2026-10-07T00:00:00+00:00", finished_at: null, current_job: "", total_jobs: 3, successful_count: 1,
      failed_count: 0, skipped_count: 0, error_message: "", stop_reason: "", claimed: true, user_id: "u1",
      user_email: "alice@example.com", device: "Laptop",
    } as AdminRun;
    let stopped = false;
    mockApi({
      "GET /api/admin/automation-jobs": () => ({ items: [stopped ? { ...run, control: "stop", stop_reason: "admin" } : run], total: 1, page: 1, page_size: 25 }),
      "POST /api/admin/automation-jobs/r1/stop": () => { stopped = true; return { ...run, control: "stop", stop_reason: "admin" }; },
    });
    renderAt("/admin/runs", <Route path="/admin/runs" element={<AdminRunsPage />} />);
    await userEvent.click(await screen.findByRole("button", { name: "Stop" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Stop run" }));
    expect(await screen.findByText("Stopped by an admin")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop" })).not.toBeInTheDocument();
  });
});
