import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/Toast";
import type { BillingOverview, Plan, Subscription } from "../../types";
import { BillingPage } from "./Billing";

const usage = {
  plan: "free", plan_name: "Free", period: "2026-10", resets_at: "2026-11-01T00:00:00+00:00",
  applications: { used: 3, limit: 10, remaining: 7 }, resumes: { used: 1, limit: 1, remaining: 0 },
  jobs_discovered: 5, runtime_seconds: 0, limit_reached: false,
};
const plans: Plan[] = [
  { code: "free", name: "Free", price_cents: 0, currency: "INR", interval: "month", limits: { applications_per_month: 10, resumes: 1 } },
  { code: "starter", name: "Starter", price_cents: 49900, currency: "INR", interval: "month", limits: { applications_per_month: 100, resumes: 3 } },
  { code: "pro", name: "Pro", price_cents: 99900, currency: "INR", interval: "month", limits: { applications_per_month: 500, resumes: 10 } },
];
const starterSub: Subscription = {
  id: "s1", plan: { code: "starter", name: "Starter", price_cents: 49900, currency: "INR", interval: "month" },
  status: "active", provider: "razorpay", current_period_start: "2026-10-07T00:00:00+00:00",
  current_period_end: "2026-11-07T00:00:00+00:00", cancel_at_period_end: false, created_at: "2026-10-07T00:00:00+00:00",
};

function overview(over: Partial<BillingOverview> = {}): BillingOverview {
  return { provider: "razorpay", subscription: null, pending: null, usage, payments: [], ...over };
}

const ok = (data: unknown) => new Response(JSON.stringify({ success: true, data }), { status: 200 });

function mockApi(routes: Record<string, unknown | ((init?: RequestInit) => unknown)>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
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
      <MemoryRouter><ToastProvider><BillingPage /></ToastProvider></MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("BillingPage", () => {
  it("pays through Razorpay Checkout and has the server verify the result", async () => {
    let current = overview();
    let confirmed: unknown;
    let razorpayOptions: Record<string, unknown> = {};
    mockApi({
      "GET /api/billing": () => current,
      "GET /api/plans": { plans },
      "POST /api/billing/checkout": {
        subscription: { ...starterSub, status: "pending" }, replaces: null,
        checkout: { key: "rzp_test_key", subscription_id: "sub_1", name: "ApplyXAI", description: "Starter plan",
                    prefill: { email: "a@example.com", name: "" } },
      },
      "POST /api/billing/confirm": (init?: RequestInit) => {
        confirmed = JSON.parse(String(init?.body));
        current = overview({ subscription: starterSub, usage: { ...usage, plan: "starter", plan_name: "Starter" } });
        return { subscription: starterSub };
      },
    });
    vi.stubGlobal("Razorpay", vi.fn(function (this: unknown, options: Record<string, unknown>) {
      razorpayOptions = options;
      return { open: () => (options.handler as (r: unknown) => void)({
        razorpay_payment_id: "pay_1", razorpay_subscription_id: "sub_1", razorpay_signature: "sig" }) };
    }));
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Upgrade to Starter" }));

    expect(razorpayOptions.subscription_id).toBe("sub_1");
    expect(razorpayOptions.key).toBe("rzp_test_key");
    expect(confirmed).toEqual({ payment_id: "pay_1", subscription_id: "sub_1", signature: "sig" });
    expect(await screen.findByText("You're on the Starter plan now.")).toBeInTheDocument();
    expect(await screen.findByText(/Renews on/)).toBeInTheDocument();
  });

  it("closing the payment window changes nothing", async () => {
    const fetchMock = mockApi({
      "GET /api/billing": overview(),
      "GET /api/plans": { plans },
      "POST /api/billing/checkout": {
        subscription: { ...starterSub, status: "pending" }, replaces: null,
        checkout: { key: "k", subscription_id: "sub_1", name: "ApplyXAI", description: "", prefill: { email: "", name: "" } },
      },
    });
    vi.stubGlobal("Razorpay", vi.fn(function (this: unknown, options: { modal: { ondismiss: () => void } }) {
      return { open: () => options.modal.ondismiss() };
    }));
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Upgrade to Pro" }));
    expect(fetchMock.mock.calls.some(([u]) => u === "/api/billing/confirm")).toBe(false);
  });

  it("warns before switching that the old plan ends with no refund", async () => {
    mockApi({
      "GET /api/billing": overview({ subscription: starterSub, usage: { ...usage, plan: "starter", plan_name: "Starter" } }),
      "GET /api/plans": { plans },
    });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Switch to Pro" }));
    expect(await screen.findByText(/unused days\s+aren't refunded/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Pay/ })).toBeInTheDocument();
    expect(screen.getByText("Cancel your plan to move to Free.")).toBeInTheDocument();
  });

  it("cancels at the end of the period", async () => {
    let cancelled = false;
    mockApi({
      "GET /api/billing": () => overview({
        subscription: { ...starterSub, cancel_at_period_end: cancelled },
        usage: { ...usage, plan: "starter", plan_name: "Starter" },
      }),
      "GET /api/plans": { plans },
      "POST /api/billing/cancel": () => { cancelled = true; return { subscription: { ...starterSub, cancel_at_period_end: true } }; },
    });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Cancel plan" }));
    expect(screen.getByText(/10 applications a month/)).toBeInTheDocument();
    const buttons = screen.getAllByRole("button", { name: "Cancel plan" });
    await user.click(buttons[buttons.length - 1]);
    expect(await screen.findByText(/You won't be charged again\./)).toBeInTheDocument();
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
  });

  it("explains test mode with the development provider", async () => {
    mockApi({ "GET /api/billing": overview({ provider: "null" }), "GET /api/plans": { plans } });
    renderPage();
    expect(await screen.findByText(/Test mode/)).toBeInTheDocument();
    expect(screen.getByText("No payments yet")).toBeInTheDocument();
  });
});
