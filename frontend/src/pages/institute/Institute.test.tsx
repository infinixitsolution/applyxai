import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/Toast";
import type { Institute, InstituteAssignment, Plan, Subscription } from "../../types";
import { InstituteProfilePage, InstituteSettingsPage, InstituteStudentsPage, InstituteSubscriptionPage } from "./Pages";

const seats = { total: 10, available: 8, assigned: 2, by_status: {} };
const campus: Institute = {
  id: "i1", name: "Riverside Training", email: "priya.riverside@example.com", contact_name: "Priya Dean",
  phone: "111", institute_type: "COLLEGE", gstin: "", pan_number: "", status: "active",
  partner_id: null, source: "admin",
  settings: { timezone: "Asia/Kolkata", notify_invites: true, notify_acceptances: true, notify_low_seats: true,
    low_seat_threshold: 3, invite_expiry_days: 7, invite_note: "" },
  seats, created_at: "2026-10-09T00:00:00+00:00",
};
const plan: Plan = {
  code: "campus", name: "Campus", price_cents: 49900, currency: "INR", interval: "month",
  limits: { applications_per_month: 50, resumes: 2, seats: 10 },
};
const sub: Subscription = {
  id: "s1", plan: { code: "campus", name: "Campus", price_cents: 49900, currency: "INR", interval: "month" },
  status: "active", provider: "razorpay", current_period_start: "2026-10-01T00:00:00+00:00",
  current_period_end: "2026-11-01T00:00:00+00:00", cancel_at_period_end: false, created_at: "2026-10-01T00:00:00+00:00",
};

const ok = (data: unknown) => new Response(JSON.stringify({ success: true, data }), { status: 200 });

function mockApi(routes: Record<string, unknown | ((init?: RequestInit) => unknown)>) {
  const calls: { key: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
    calls.push({ key, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (!(key in routes)) throw new Error(`unexpected request: ${key}`);
    const value = routes[key];
    return ok(typeof value === "function" ? (value as (i?: RequestInit) => unknown)(init) : value);
  }));
  return calls;
}

function renderPage(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter><ToastProvider>{ui}</ToastProvider></MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("institute portal wiring", () => {
  it("opens Razorpay and confirms campus checkout", async () => {
    let confirmed: unknown;
    mockApi({
      "GET /api/institute/subscription": { subscription: null, seats },
      "GET /api/institute/plans": { plans: [plan] },
      "POST /api/institute/subscription/checkout": {
        subscription: { ...sub, status: "pending" }, replaces: null,
        checkout: { key: "rzp_test_key", subscription_id: "sub_1", name: "ApplyXAI", description: "Campus",
                    prefill: { email: "dean@example.com", name: "" } },
      },
      "POST /api/billing/confirm": (init?: RequestInit) => {
        confirmed = JSON.parse(String(init?.body));
        return { subscription: sub };
      },
    });
    vi.stubGlobal("Razorpay", vi.fn(function (this: unknown, options: Record<string, unknown>) {
      return { open: () => (options.handler as (r: unknown) => void)({
        razorpay_payment_id: "pay_1", razorpay_subscription_id: "sub_1", razorpay_signature: "sig" }) };
    }));
    renderPage(<InstituteSubscriptionPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Choose" }));
    expect(confirmed).toEqual({ payment_id: "pay_1", subscription_id: "sub_1", signature: "sig" });
    expect(await screen.findByText(/Campus is active/)).toBeInTheDocument();
  });

  it("saves invitation settings from the form", async () => {
    const calls = mockApi({
      "GET /api/institute/profile": campus,
      "PUT /api/institute/settings": campus,
    });
    renderPage(<InstituteSettingsPage />);
    const note = await screen.findByLabelText("Default invite note");
    await userEvent.type(note, "Welcome to campus");
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /api/institute/settings")).toBe(true));
    expect(calls.find((c) => c.key === "PUT /api/institute/settings")?.body).toMatchObject({
      invite_note: "Welcome to campus", notify_invites: true, timezone: "Asia/Kolkata",
    });
  });

  it("saves the bound profile fields", async () => {
    const calls = mockApi({
      "GET /api/institute/profile": campus,
      "PUT /api/institute/profile": (init?: RequestInit) => ({ ...campus, ...JSON.parse(String(init?.body)) }),
    });
    renderPage(<InstituteProfilePage />);
    const name = await screen.findByLabelText("Name");
    await userEvent.clear(name);
    await userEvent.type(name, "Harbor Training");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /api/institute/profile")).toBe(true));
    expect(calls.find((c) => c.key === "PUT /api/institute/profile")?.body).toMatchObject({
      name: "Harbor Training", contact_name: "Priya Dean", phone: "111",
    });
  });

  it("suspends an active student after confirm", async () => {
    const student: InstituteAssignment = {
      id: "a1", candidate_email: "student@example.com", student_user_id: "u9", seat_id: "seat1",
      status: "active", note: "", accepted_at: "2026-10-09T00:00:00+00:00", released_at: null,
      created_at: "2026-10-08T00:00:00+00:00",
    };
    const calls = mockApi({
      "GET /api/institute/students": { items: [student], total: 1, page: 1, page_size: 20 },
      "POST /api/institute/students/a1/suspend": { ...student, status: "suspended" },
    });
    renderPage(<InstituteStudentsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Suspend" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Suspend" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /api/institute/students/a1/suspend")).toBe(true));
  });
});
