import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/Toast";
import type { Institute, InstituteAssignment, Plan, Subscription } from "../../types";
import { InstituteInvitationsPage, InstituteProfilePage, InstituteSettingsPage, InstituteStudentsPage, InstituteSubscriptionPage } from "./Pages";

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
  limits: { applications_per_month: 50, resumes: 999_999, mock_interviews_per_month: 10, seats: 10 },
};
const sub: Subscription = {
  id: "s1", plan: { code: "campus", name: "Campus", price_cents: 49900, currency: "INR", interval: "month" },
  status: "active", provider: "razorpay", current_period_start: "2026-10-01T00:00:00+00:00",
  current_period_end: "2026-11-01T00:00:00+00:00", cancel_at_period_end: false, created_at: "2026-10-01T00:00:00+00:00",
};

const dash = {
  institute: campus,
  subscription: null,
  students: 1,
  pending_invites: 0,
  seats,
  activity: { searched: 0, applied: 0, skipped: 0, failed: 0, success_rate: null, daily: [] },
  recent_assignments: [],
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
      "GET /api/institute/dashboard": dash,
      "GET /api/institute/students": { items: [student], total: 1, page: 1, page_size: 20 },
      "POST /api/institute/students/a1/suspend": { ...student, status: "suspended" },
    });
    renderPage(<InstituteStudentsPage />);
    expect(await screen.findByRole("link", { name: "View" })).toHaveAttribute("href", "/institute/students/a1");
    await userEvent.click(await screen.findByRole("button", { name: "Suspend" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Suspend" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /api/institute/students/a1/suspend")).toBe(true));
  });

  it("releases a candidate without cancelling institute seats", async () => {
    const student: InstituteAssignment = {
      id: "a1", candidate_email: "student@example.com", student_user_id: "u9", seat_id: "seat1",
      status: "active", note: "", accepted_at: "2026-10-09T00:00:00+00:00", released_at: null,
      created_at: "2026-10-08T00:00:00+00:00",
    };
    const calls = mockApi({
      "GET /api/institute/dashboard": dash,
      "GET /api/institute/students": { items: [student], total: 1, page: 1, page_size: 20 },
      "POST /api/institute/students/a1/release": { ...student, status: "released", seat_id: null },
    });
    renderPage(<InstituteStudentsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Release" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Release this candidate?" })).toBeInTheDocument();
    expect(dialog).toHaveTextContent(/will no longer be bound to this campus/i);
    expect(dialog).toHaveTextContent(/must buy a candidate plan to apply/i);
    expect(dialog).toHaveTextContent(/seats stay with the institute/i);
    await userEvent.click(within(dialog).getByRole("button", { name: "Release" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /api/institute/students/a1/release")).toBe(true));
    expect(await screen.findByText(/Candidate released\. They must buy a personal plan to apply/)).toBeInTheDocument();
  });

  it("invites a student from Add student", async () => {
    const invited: InstituteAssignment = {
      id: "a2", candidate_email: "new@example.com", candidate_name: "New Student",
      candidate_phone: "9876543210", student_user_id: "u2", seat_id: "seat2",
      status: "active", note: "", accepted_at: "2026-10-16T00:00:00+00:00", released_at: null,
      created_at: "2026-10-16T00:00:00+00:00",
    };
    const calls = mockApi({
      "GET /api/institute/dashboard": { ...dash, students: 0 },
      "GET /api/institute/students": { items: [], total: 0, page: 1, page_size: 20 },
      "POST /api/institute/students/invite": { assignment: invited },
    });
    renderPage(<InstituteStudentsPage />);
    const addButtons = await screen.findAllByRole("button", { name: "Add student" });
    await userEvent.click(addButtons[0]);
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Name"), "New Student");
    await userEvent.type(within(dialog).getByLabelText("Number"), "9876543210");
    await userEvent.type(within(dialog).getByLabelText("Email ID"), "new@example.com");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add student" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /api/institute/students/invite")).toBe(true));
    expect(calls.find((c) => c.key === "POST /api/institute/students/invite")?.body).toEqual({
      name: "New Student", phone: "9876543210", email: "new@example.com", note: "",
    });
  });

  it("cancels an invitation after confirm", async () => {
    const invited: InstituteAssignment = {
      id: "a3", candidate_email: "wait@example.com", candidate_name: "Wait Student",
      candidate_phone: "9876543212", student_user_id: "u3", seat_id: "seat3",
      status: "invited", note: "", accepted_at: null, released_at: null,
      created_at: "2026-10-16T00:00:00+00:00", expires_at: "2026-10-23T00:00:00+00:00",
    };
    const calls = mockApi({
      "GET /api/institute/dashboard": { ...dash, pending_invites: 1 },
      "GET /api/institute/invitations": { items: [invited] },
      "POST /api/institute/students/a3/release": { ...invited, status: "cancelled" },
    });
    renderPage(<InstituteInvitationsPage />);
    expect(await screen.findByRole("heading", { name: "1 open invitation" })).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel invite" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /api/institute/students/a3/release")).toBe(true));
  });
});
