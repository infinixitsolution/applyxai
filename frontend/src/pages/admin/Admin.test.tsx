import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RequireAdmin } from "../../auth/session";
import { ToastProvider } from "../../components/Toast";
import type { AdminCandidate, AdminInstituteDetail, AdminPartnerDetail, AdminPlan, AdminPlatformSettings, AdminRun, AdminUser, AdminUserDetail, User } from "../../types";
import { AdminCompanyPage } from "./Company";
import { AdminCompaniesPage, AdminRunsPage } from "./Lists";
import { AdminInstitutePage, AdminInstitutesPage, AdminPartnerPage, AdminPartnersPage } from "./Orgs";
import { AdminPlansPage } from "./Plans";
import { AdminSystemPage } from "./System";
import { AdminUserLiveInterviewPage } from "./UserCandidate";
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
  {
    code: "free", name: "Free", price_cents: 0, currency: "INR", interval: "month",
    limits: { applications_per_month: 10, resumes: 999_999, mock_interviews_per_month: 3 },
  },
  {
    code: "starter", name: "Starter", price_cents: 49900, currency: "INR", interval: "month",
    limits: { applications_per_month: 100, resumes: 999_999, mock_interviews_per_month: 10 },
  },
];

const adminSettings: AdminPlatformSettings = {
  cms: {
    branding: { app_name: "ApplyXAI", contact_email: "hello@example.com", footer_line: "", social_links: { twitter: "", linkedin: "", github: "" } },
    banner: { enabled: false, message: "", tone: "info" },
    landing: {
      hero_badge: "", hero_title: "", hero_subtitle: "", hero_cta_primary: "", hero_cta_secondary: "", hero_footnote: "",
      features_heading: "", features: [], steps_heading: "", steps: [], pricing_heading: "", pricing_subtitle: "",
      faq_heading: "", faq: [], faq_contact_line: "",
    },
    legal: { privacy_md: "", terms_md: "", refund_md: "" },
    seo: {
      site_url: "https://applyxai.com",
      default_title: "ApplyXAI",
      title_suffix: "",
      default_description: "LinkedIn Easy Apply automation.",
      default_keywords: "LinkedIn, jobs",
      og_image_url: "https://applyxai.com/mascot.png",
      twitter_card: "summary_large_image",
      robots_index: true,
      robots_disallow: ["/app/", "/admin/"],
      google_site_verification: "",
      bing_site_verification: "",
      pages: {
        home: { title: "", description: "", noindex: false },
        login: { title: "Sign in", description: "", noindex: true },
        register: { title: "Register", description: "", noindex: false },
        privacy: { title: "Privacy", description: "", noindex: false },
        terms: { title: "Terms", description: "", noindex: false },
        refund: { title: "Refund", description: "", noindex: false },
      },
    },
  },
  smtp: {
    enabled: true, host: "smtp.example.com", port: 587, security: "starttls", username: "mailer", from_address: "ApplyXAI <no-reply@example.com>",
    password_configured: true, mode: "smtp", source: "environment",
  },
  auth_email: { require_verification: true, verification_hours: 24, password_reset_minutes: 60, frontend_url: "http://localhost:5173" },
  notifications: { run_finished: { email: false, label: "Run finished", description: "When a run completes" } },
  email_templates: {
    auth: {
      verify_email: { subject: "Verify", body: "Link {link}", html: "" },
      password_reset: { subject: "Reset", body: "Link {link}", html: "" },
      account_exists: { subject: "Exists", body: "Link {link}", html: "" },
      institute_invite: { subject: "Invite", body: "Link {link}", html: "" },
    },
    events: {
      run_finished: {
        in_app_title: "{title}", in_app_body: "{message}", email_subject: "{title}",
        email_body: "{message}", email_html: "",
      },
    },
  },
  ai: {
    enabled: false, provider: "openai", base_url: "https://api.openai.com/v1", api_key_configured: false,
    models: { fast: "gpt-4o-mini", strong: "gpt-4o", embedding: "text-embedding-3-small" },
    features: { applications: true, resume: true, mock_interview: true }, ready: false,
  },
  payments: {
    provider: "null", key_id: "", key_secret_configured: false, webhook_secret_configured: false,
    ready: false, source: "environment", razorpay_mode: "unknown", live_checkout: false, test_checkout: false,
  },
  infrastructure: {
    app_env: "development", app_version: "test", database: "sqlite", redis_url_set: false, cors_origins: ["http://localhost:5173"],
    payment_provider: "null", payment_keys_configured: false,
  },
  unverified_users: 2,
};

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
      "GET /api/auth/me": { user: me },
      "GET /api/admin/users": { items: [alice], total: 1, page: 1, page_size: 25 },
      "GET /api/plans": { plans },
    });
    renderAt("/admin/users", <Route path="/admin/users" element={<AdminUsersPage />} />);
    expect(await screen.findByRole("link", { name: "alice@example.com" })).toHaveAttribute("href", "/admin/users/u1");
    expect(screen.getByRole("button", { name: "Add user" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Disabled" }));
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
    const adminPlans: AdminPlan[] = plans.map((p, i) => ({
      ...p, kind: "personal", is_active: true, sort_order: i, provider_plan_id: "", subscribers: i,
    }));
    const calls = mockApi({
      "GET /api/admin/plans": { plans: adminPlans },
      "PUT /api/admin/plans/starter": (init?: RequestInit) => ({ ...adminPlans[1], ...JSON.parse(String(init?.body)) }),
    });
    renderAt("/admin/plans", <Route path="/admin/plans" element={<AdminPlansPage />} />);
    expect(await screen.findByRole("heading", { name: "Candidate plans" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Training institute plans" })).toBeInTheDocument();
    const row = (await screen.findByText("Starter")).closest("tr")!;
    await userEvent.click(within(row).getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("individual candidates");
    const price = within(dialog).getByLabelText(/Price per month/);
    await userEvent.clear(price);
    await userEvent.type(price, "599");
    expect(dialog).toHaveTextContent("current subscriber keep their price");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /api/admin/plans/starter")).toBe(true));
    expect(calls.find((c) => c.key === "PUT /api/admin/plans/starter")?.body).toEqual({
      name: "Starter", price_cents: 59900, applications_per_month: 100, mock_interviews_per_month: 10,
      resumes_per_month: 999_999, is_active: true, sort_order: 1,
    });
  });

  it("lists campus plans under training institutes and can edit seats", async () => {
    const adminPlans: AdminPlan[] = [
      { code: "free", name: "Free", kind: "personal", price_cents: 0, currency: "INR", interval: "month",
        limits: { applications_per_month: 10, resumes: 999_999, mock_interviews_per_month: 3 },
        is_active: true, sort_order: 0, provider_plan_id: "", subscribers: 0 },
      { code: "campus", name: "Campus", kind: "institute", price_cents: 49900, currency: "INR", interval: "month",
        limits: { applications_per_month: 100, resumes: 999_999, mock_interviews_per_month: 3, seats: 10 },
        is_active: true, sort_order: 4, provider_plan_id: "", subscribers: 0 },
    ];
    const calls = mockApi({
      "GET /api/admin/plans": { plans: adminPlans },
      "PUT /api/admin/plans/campus": (init?: RequestInit) => ({ ...adminPlans[1], ...JSON.parse(String(init?.body)) }),
    });
    renderAt("/admin/plans", <Route path="/admin/plans" element={<AdminPlansPage />} />);
    const row = (await screen.findByText("Campus")).closest("tr")!;
    expect(row).toHaveTextContent("10");
    expect(row).toHaveTextContent("4,990");
    expect(row).toHaveTextContent("1,000 apps");
    expect(row).toHaveTextContent("30 mock interviews");
    await userEvent.click(within(row).getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("per student");
    expect(dialog).toHaveTextContent("Amount =");
    expect(dialog).toHaveTextContent("Package: 1,000 applications / month and 30 mock interviews / month");
    const seats = within(dialog).getByLabelText("Minimum students");
    await userEvent.clear(seats);
    await userEvent.type(seats, "25");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /api/admin/plans/campus")).toBe(true));
    expect(calls.find((c) => c.key === "PUT /api/admin/plans/campus")?.body).toMatchObject({ seats: 25 });
  });

  it("sends a test email and shows the mail server's refusal", async () => {
    const calls = mockApi({
      "GET /api/auth/me": { user: me },
      "GET /api/admin/settings": adminSettings,
      "POST /api/admin/email/test": { delivered: false, mode: "smtp", error: "SMTPAuthenticationError: bad login" },
    });
    renderAt("/admin/system", <Route path="/admin/system" element={<AdminSystemPage />} />);
    await userEvent.click(await screen.findByRole("button", { name: "Email & SMTP" }));
    expect(await screen.findByDisplayValue("smtp.example.com")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "2" })).toHaveAttribute("href", "/admin/users?status=unverified");
    await userEvent.type(screen.getByLabelText("To"), "ops@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Send test" }));
    expect(await screen.findByText(/SMTPAuthenticationError: bad login/)).toBeInTheDocument();
    expect(calls.find((c) => c.key === "POST /api/admin/email/test")?.body).toEqual({ to: "ops@example.com" });
  });

  it("shows the candidate dashboard, profile, and live interview report", async () => {
    const candidate: AdminCandidate = {
      profile: {
        phone: "+91 98765 43210", headline: "Backend engineer", summary: "Builds APIs.", current_title: "Engineer",
        current_company: "Acme", experience_years: 4, skills: ["Python", "FastAPI"], preferred_roles: ["Backend"],
        preferred_locations: ["Bangalore"], education: [{ school: "IIT Madras", degree: "B.Tech" }],
        work_history: [{ title: "Engineer", company: "Acme", start: "2022" }],
      },
      search: { keywords: ["Python developer"], location: "Bangalore", easy_apply_only: true, experience_level: [],
                job_type: [], on_site: ["Remote"], date_posted: "", salary_min: null, salary_max: null },
      resume_list: [{ id: "r1", name: "Main CV", file_type: "pdf", file_size: 2048, is_default: true, tailored: false,
                      created_at: "2026-10-02T00:00:00+00:00" }],
      stats: { applications_total: 4, applied_total: 4, success_rate: 100, mock_interviews_total: 0, mock_average_score: null,
               live_interviews_total: 1, live_average_score: 72 },
      applications_daily: [{ date: "2026-10-11", applied: 4, failed: 0 }],
      recent_applications: [{ id: "a1", status: "applied", title: "Backend Engineer", company: "Globex", location: "Remote",
                              job_url: "", failure_reason: "", applied_at: "2026-10-11T00:00:00+00:00", created_at: null }],
      mock_interviews: [],
      live_interviews: [{ id: "L1", status: "completed", job_title: "Backend Engineer", company: "Globex", token: "12345678",
                          token_status: "used", overall_score: 72, lines: 6, started_at: "2026-10-11T00:00:00+00:00",
                          ended_at: "2026-10-11T00:30:00+00:00" }],
      live_tokens: { unused: 1, reserved: 0, used: 1, paid: [{ currency: "INR", amount_cents: 99800 }] },
      journey: {
        steps: [
          { key: "registered", label: "Registered", done: true, at: "2026-10-02T00:00:00+00:00", optional: false },
          { key: "resume", label: "Uploaded a resume", done: true, at: "2026-10-02T01:00:00+00:00", optional: false },
          { key: "desktop_agent", label: "Connected the desktop agent", done: false, at: null, optional: false },
        ],
        stopped_at: "desktop_agent", stopped_label: "Connect the desktop agent", stopped_step: 3, completed: 2, total: 3,
        last_activity_at: "2026-10-11T00:00:00+00:00",
      },
    };
    mockApi({
      "GET /api/auth/me": { user: me },
      "GET /api/plans": { plans },
      "GET /api/admin/users/u1": detail({ candidate }),
      "GET /api/admin/users/u1/live-interviews/L1": {
        user: { id: "u1", email: "alice@example.com", name: "Alice Doe" },
        session: { id: "L1", status: "completed", job_title: "Backend Engineer", company: "Globex", application_id: null,
                   token: "12345678", started_at: "2026-10-11T00:00:00+00:00", ended_at: "2026-10-11T00:30:00+00:00",
                   transcript: [{ role: "interviewer", text: "Tell me about yourself", at: "1" }],
                   feedback: { overall_score: 72, summary: "Clear answers." } },
      },
    });
    renderAt("/admin/users/u1", <>
      <Route path="/admin/users/:id" element={<AdminUserPage />} />
      <Route path="/admin/users/:id/live-interviews/:sessionId" element={<AdminUserLiveInterviewPage />} />
    </>);
    expect(await screen.findByText("+91 98765 43210")).toBeInTheDocument();
    expect(screen.getByText("Applied (all time)")).toBeInTheDocument();
    const journey = screen.getByRole("region", { name: "Progress after registration" });
    expect(journey).toHaveTextContent("Stopped at step 3: Connect the desktop agent");
    expect(journey).toHaveTextContent("2 of 3 steps done");
    expect(within(journey).getByText("Stopped here")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Profile" }));
    expect(await screen.findByText("IIT Madras")).toBeInTheDocument();
    expect(screen.getByText("FastAPI")).toBeInTheDocument();
    expect(screen.getByText("Main CV")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Interviews (1)" }));
    expect(await screen.findByText(/Token 12345678/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "View report" }));
    expect(await screen.findByText("Tell me about yourself")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Regenerate/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to candidate" })).toHaveAttribute("href", "/admin/users/u1?tab=interviews");
  });

  it("resends verification for an unverified user", async () => {
    const unverified = detail({ user: { ...alice, is_verified: false } });
    const calls = mockApi({
      "GET /api/auth/me": { user: me },
      "GET /api/plans": { plans },
      "GET /api/admin/users/u1": unverified,
      "POST /api/admin/users/u1/resend-verification": unverified,
    });
    renderAt("/admin/users/u1", <Route path="/admin/users/:id" element={<AdminUserPage />} />);
    await userEvent.click(await screen.findByRole("button", { name: "Resend verification email" }));
    expect(await screen.findByText(/Verification email sent/)).toBeInTheDocument();
    expect(calls.some((c) => c.key === "POST /api/admin/users/u1/resend-verification")).toBe(true);
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
    expect(await screen.findByText("Stopped by ApplyXAI support")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop" })).not.toBeInTheDocument();
  });

  it("lists companies users searched and companies searches returned", async () => {
    mockApi({
      "GET /api/admin/companies": {
        items: [{
          company: "Acme", users: 2, user_emails: ["alice@example.com", "bob@example.com"],
          jobs: 4, applied: 1, search_filters: 1, last_seen: "2026-10-10T08:00:00+00:00",
        }],
        total: 1, page: 1, page_size: 25,
      },
    });
    renderAt("/admin/companies", <Route path="/admin/companies" element={<AdminCompaniesPage />} />);
    expect(await screen.findByRole("heading", { name: "Companies" })).toBeInTheDocument();
    expect(await screen.findByText("Acme")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View" })).toHaveAttribute("href", "/admin/companies/Acme");
    expect(screen.getByText("alice@example.com, bob@example.com")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("opens a company dashboard with jobs and a contact directory", async () => {
    mockApi({
      "GET /api/admin/companies/detail": {
        company: "Acme", users: 1, jobs: 2, applied: 3, search_filters: 1, locations: ["India"],
        last_seen: "2026-10-10T08:00:00+00:00",
        job_list: [{ id: "j1", title: "Backend Engineer", location: "India", job_url: "https://www.linkedin.com/jobs/view/1", applied: 3, other: 1, users: 1, last_seen: "2026-10-10T08:00:00+00:00" }],
        contacts: [{ name: "Priya Shah", email: "hiring@acme.com", phone: "+91 98450 11223", role: "Recruiter", link: "", jobs: [{ title: "Backend Engineer", job_url: "" }] }],
      },
    });
    renderAt("/admin/companies/Acme", <Route path="/admin/companies/:company" element={<AdminCompanyPage />} />);
    expect(await screen.findByRole("heading", { name: "Acme" })).toBeInTheDocument();
    expect(screen.getByText("Company overview")).toBeInTheDocument();
    expect(screen.getAllByText("Backend Engineer").length).toBeGreaterThan(0);
    expect(screen.getByText("Priya Shah")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "hiring@acme.com" })).toHaveAttribute("href", "mailto:hiring@acme.com");
    expect(screen.getByText("+91 98450 11223")).toBeInTheDocument();
    expect(screen.getAllByText("Contact directory").length).toBeGreaterThan(0);
  });

  it("creates an institute from the list page", async () => {
    const created = {
      id: "i1", name: "Acme College", email: "dean@acme.edu", contact_name: "", phone: "",
      institute_type: "OTHER", gstin: "", pan_number: "", status: "active", partner_id: null, source: "admin",
      settings: {}, seats: { total: 0, available: 0, assigned: 0, by_status: {} }, created_at: "2026-10-09T00:00:00+00:00",
    };
    const calls = mockApi({
      "GET /api/admin/institutes": { items: [], total: 0, page: 1, page_size: 20 },
      "POST /api/admin/institutes": (init?: RequestInit) => ({ ...created, ...JSON.parse(String(init?.body)) }),
    });
    renderAt("/admin/institutes", <>
      <Route path="/admin/institutes" element={<AdminInstitutesPage />} />
      <Route path="/admin/institutes/:id" element={<p>institute detail</p>} />
    </>);
    await userEvent.click(await screen.findByRole("button", { name: "Add institute" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Institute name"), "Acme College");
    await userEvent.type(within(dialog).getByLabelText("Email"), "dean@acme.edu");
    await userEvent.type(within(dialog).getByLabelText("Password"), "correct horse battery");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add institute" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /api/admin/institutes")).toBe(true));
    expect(calls.find((c) => c.key === "POST /api/admin/institutes")?.body).toMatchObject({
      name: "Acme College", email: "dean@acme.edu", approve: true,
    });
    expect(await screen.findByText("institute detail")).toBeInTheDocument();
  });

  it("lists institutes with view, edit, and disable actions", async () => {
    mockApi({
      "GET /api/admin/institutes": {
        items: [{
          id: "i1", name: "Riverside Training", email: "priya.riverside@example.com", contact_name: "Priya Dean",
          phone: "", institute_type: "TRAINING_CENTRE", gstin: "", pan_number: "", status: "active",
          partner_id: null, source: "admin", settings: {},
          seats: { total: 20, available: 20, assigned: 0, by_status: {} }, created_at: "2026-10-09T00:00:00+00:00",
        }],
        total: 1, page: 1, page_size: 20,
      },
    });
    renderAt("/admin/institutes", <Route path="/admin/institutes" element={<AdminInstitutesPage />} />);
    expect(await screen.findByText("Riverside Training")).toBeInTheDocument();
    expect(screen.getByText("20 / 20")).toBeInTheDocument();
    expect(screen.getByText(/Training centre/)).toBeInTheDocument();
    expect(screen.getByText(/Created by admin/)).toBeInTheDocument();
    expect(screen.getByText("Contact Priya Dean")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View" })).toHaveAttribute("href", "/admin/institutes/i1");
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disable" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enable" })).not.toBeInTheDocument();
  });

  it("edits an institute from the list", async () => {
    const institute = {
      id: "i1", name: "Riverside Training", email: "priya.riverside@example.com", contact_name: "Priya Dean",
      phone: "111", institute_type: "TRAINING_CENTRE", gstin: "", pan_number: "", status: "active",
      partner_id: null, source: "admin", settings: {},
      seats: { total: 20, available: 20, assigned: 0, by_status: {} }, created_at: "2026-10-09T00:00:00+00:00",
    };
    const calls = mockApi({
      "GET /api/admin/institutes": { items: [institute], total: 1, page: 1, page_size: 20 },
      "PUT /api/admin/institutes/i1": (init?: RequestInit) => ({ ...institute, ...JSON.parse(String(init?.body)) }),
    });
    renderAt("/admin/institutes", <Route path="/admin/institutes" element={<AdminInstitutesPage />} />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.clear(within(dialog).getByLabelText("Institute name"));
    await userEvent.type(within(dialog).getByLabelText("Institute name"), "Harbor Training");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /api/admin/institutes/i1")).toBe(true));
    expect(calls.find((c) => c.key === "PUT /api/admin/institutes/i1")?.body).toMatchObject({
      name: "Harbor Training", contact_name: "Priya Dean", phone: "111",
    });
  });

  it("disables an active campus from the list", async () => {
    const institute = {
      id: "i1", name: "Riverside Training", email: "priya.riverside@example.com", contact_name: "Priya Dean",
      phone: "", institute_type: "TRAINING_CENTRE", gstin: "", pan_number: "", status: "active",
      partner_id: null, source: "admin", settings: {},
      seats: { total: 20, available: 20, assigned: 0, by_status: {} }, created_at: "2026-10-09T00:00:00+00:00",
    };
    let status = "active";
    mockApi({
      "GET /api/admin/institutes": () => ({
        items: [{ ...institute, status }], total: 1, page: 1, page_size: 20,
      }),
      "POST /api/admin/institutes/i1/status": (init?: RequestInit) => {
        status = JSON.parse(String(init?.body)).status;
        return { ...institute, status };
      },
    });
    renderAt("/admin/institutes", <Route path="/admin/institutes" element={<AdminInstitutesPage />} />);
    await userEvent.click(await screen.findByRole("button", { name: "Disable" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Disable" }));
    expect(await screen.findByRole("button", { name: "Enable" })).toBeInTheDocument();
  });

  it("enables a suspended campus from the list", async () => {
    const institute = {
      id: "i1", name: "Riverside Training", email: "priya.riverside@example.com", contact_name: "Priya Dean",
      phone: "", institute_type: "TRAINING_CENTRE", gstin: "", pan_number: "", status: "suspended",
      partner_id: null, source: "admin", settings: {},
      seats: { total: 20, available: 20, assigned: 0, by_status: {} }, created_at: "2026-10-09T00:00:00+00:00",
    };
    let status = "suspended";
    mockApi({
      "GET /api/admin/institutes": () => ({
        items: [{ ...institute, status }], total: 1, page: 1, page_size: 20,
      }),
      "POST /api/admin/institutes/i1/status": (init?: RequestInit) => {
        status = JSON.parse(String(init?.body)).status;
        return { ...institute, status };
      },
    });
    renderAt("/admin/institutes", <Route path="/admin/institutes" element={<AdminInstitutesPage />} />);
    await userEvent.click(await screen.findByRole("button", { name: "Enable" }));
    expect(await screen.findByRole("button", { name: "Disable" })).toBeInTheDocument();
  });

  it("shows a complete institute dashboard", async () => {
    const seats = { total: 10, available: 8, assigned: 2, by_status: { purchased: 8, assigned: 2, suspended: 0, released: 0, expired: 0 } };
    const institute = {
      id: "i1", name: "Riverside Training", email: "priya.riverside@example.com", contact_name: "Priya Rao",
      phone: "999", institute_type: "TRAINING_CENTRE", gstin: "", pan_number: "", status: "active",
      partner_id: null, source: "admin", settings: { timezone: "Asia/Kolkata", notify_invites: true,
        notify_acceptances: true, notify_low_seats: true, low_seat_threshold: 3, invite_expiry_days: 7, invite_note: "" },
      seats, created_at: "2026-10-09T00:00:00+00:00",
    };
    const sub = {
      id: "s1", plan: { code: "campus", name: "Campus", price_cents: 49900, currency: "INR", interval: "month" },
      status: "active" as const, provider: "razorpay", current_period_start: "2026-10-01T00:00:00+00:00",
      current_period_end: "2026-11-01T00:00:00+00:00", cancel_at_period_end: false, created_at: "2026-10-01T00:00:00+00:00",
    };
    const student = {
      id: "a1", candidate_email: "student@example.com", student_user_id: "u9", seat_id: "seat1",
      status: "active", note: "", accepted_at: "2026-10-09T00:00:00+00:00", released_at: null,
      created_at: "2026-10-08T00:00:00+00:00",
    };
    const detail: AdminInstituteDetail = {
      institute,
      dashboard: { institute, subscription: sub, students: 1, pending_invites: 0, seats, recent_assignments: [student] },
      login: {
        id: "u2", email: "priya.riverside@example.com", first_name: "Priya", last_name: "Rao",
        is_active: true, is_verified: true, last_login_at: null, created_at: "2026-10-09T00:00:00+00:00",
      },
      partner: null,
      subscription: sub,
      subscriptions: [sub],
      payments: [{ id: "pay1", amount_cents: 499000, currency: "INR", status: "captured", method: "card", description: "Campus", paid_at: "2026-10-01T00:00:00+00:00" }],
      students: [student],
      invitations: [],
      seats: { counts: seats, items: [{ id: "seat1", subscription_id: "s1", status: "assigned", created_at: "2026-10-01T00:00:00+00:00" }] },
      reports: { seats, assignments_by_status: { invited: 0, pending_candidate_acceptance: 0, active: 1, rejected: 0, suspended: 0, released: 0, expired: 0, cancelled: 0 } },
      members: [{ id: "m1", user_id: "u2", email: "priya.riverside@example.com", name: "Priya Rao", role: "admin", status: "active" }],
      commissions: [],
    };
    mockApi({ "GET /api/admin/institutes/i1": detail });
    renderAt("/admin/institutes/i1", <Route path="/admin/institutes/:id" element={<AdminInstitutePage />} />);
    expect(await screen.findByRole("heading", { name: "Riverside Training" })).toBeInTheDocument();
    expect(screen.getByText("Active students")).toBeInTheDocument();
    expect(screen.getByText("student@example.com")).toBeInTheDocument();
    expect(screen.getAllByText("Priya Rao").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Suspend" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in as" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset password" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Grant campus seats" })).not.toBeInTheDocument();
  });

  it("creates a partner from the list page", async () => {
    const created = {
      id: "p1", user_id: "u2", organization: "Ally Partners", contact_name: "", phone: "",
      referral_code: "ABCD1234", status: "approved", kyc_status: "not_required",
      commission_mode: "percent_payment", commission_bps: 0, commission_flat_cents: 0,
      gstin: "", pan_number: "", payout_account: "", payout_ifsc: "",
    };
    const calls = mockApi({
      "GET /api/admin/partners": { items: [], total: 0, page: 1, page_size: 20 },
      "POST /api/admin/partners": (init?: RequestInit) => ({ ...created, ...JSON.parse(String(init?.body)) }),
    });
    renderAt("/admin/partners", <>
      <Route path="/admin/partners" element={<AdminPartnersPage />} />
      <Route path="/admin/partners/:id" element={<p>partner detail</p>} />
    </>);
    await userEvent.click(await screen.findByRole("button", { name: "Add partner" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Organisation"), "Ally Partners");
    await userEvent.type(within(dialog).getByLabelText("Email"), "ally@example.com");
    await userEvent.type(within(dialog).getByLabelText("Password"), "correct horse battery");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add partner" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /api/admin/partners")).toBe(true));
    expect(calls.find((c) => c.key === "POST /api/admin/partners")?.body).toMatchObject({
      organization: "Ally Partners", email: "ally@example.com", approve: true,
    });
    expect(await screen.findByText("partner detail")).toBeInTheDocument();
  });

  it("lists partners with view, edit, and disable actions", async () => {
    mockApi({
      "GET /api/admin/partners": {
        items: [{
          id: "p1", user_id: "u3", organization: "West Coast Referral", contact_name: "Alex West",
          phone: "555", referral_code: "WCR1", status: "approved", kyc_status: "not_required",
          commission_mode: "percent_payment", commission_bps: 1000, commission_flat_cents: 0,
          gstin: "", pan_number: "", payout_account: "", payout_ifsc: "",
          kyc_documents: [], click_count: 0, wallet: { accrued_cents: 0, approved_cents: 0, available_cents: 0 },
          created_at: "2026-10-09T00:00:00+00:00",
        }],
        total: 1, page: 1, page_size: 20,
      },
    });
    renderAt("/admin/partners", <>
      <Route path="/admin/partners" element={<AdminPartnersPage />} />
      <Route path="/admin/partners/:id" element={<p>partner detail</p>} />
    </>);
    expect(await screen.findByText("West Coast Referral")).toBeInTheDocument();
    expect(screen.getByText("Alex West")).toBeInTheDocument();
    expect(screen.getByText("Code WCR1")).toBeInTheDocument();
    expect(screen.getByText("10%")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View" })).toHaveAttribute("href", "/admin/partners/p1");
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disable" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enable" })).not.toBeInTheDocument();
  });

  it("edits a partner from the list", async () => {
    const partner = {
      id: "p1", user_id: "u3", organization: "West Coast Referral", contact_name: "Alex West",
      phone: "555", referral_code: "WCR1", status: "approved", kyc_status: "not_required",
      commission_mode: "percent_payment", commission_bps: 1000, commission_flat_cents: 0,
      gstin: "", pan_number: "", payout_account: "", payout_ifsc: "",
      kyc_documents: [], click_count: 0, wallet: { accrued_cents: 0, approved_cents: 0, available_cents: 0 },
      created_at: "2026-10-09T00:00:00+00:00",
    };
    const calls = mockApi({
      "GET /api/admin/partners": { items: [partner], total: 1, page: 1, page_size: 20 },
      "PUT /api/admin/partners/p1": (init?: RequestInit) => ({ ...partner, ...JSON.parse(String(init?.body)) }),
    });
    renderAt("/admin/partners", <Route path="/admin/partners" element={<AdminPartnersPage />} />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.clear(within(dialog).getByLabelText("Organisation"));
    await userEvent.type(within(dialog).getByLabelText("Organisation"), "Pacific Referral");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /api/admin/partners/p1")).toBe(true));
    expect(calls.find((c) => c.key === "PUT /api/admin/partners/p1")?.body).toMatchObject({
      organization: "Pacific Referral",
      contact_name: "Alex West",
      phone: "555",
      commission_mode: "percent_payment",
      commission_bps: 1000,
      commission_flat_cents: 0,
      status: "approved",
      kyc_status: "not_required",
    });
  });

  it("disables an approved partner from the list", async () => {
    const partner = {
      id: "p1", user_id: "u3", organization: "West Coast Referral", contact_name: "Alex West",
      phone: "", referral_code: "WCR1", status: "approved", kyc_status: "not_required",
      commission_mode: "percent_payment", commission_bps: 0, commission_flat_cents: 0,
      gstin: "", pan_number: "", payout_account: "", payout_ifsc: "",
      kyc_documents: [], click_count: 0, wallet: { accrued_cents: 0, approved_cents: 0, available_cents: 0 },
      created_at: "2026-10-09T00:00:00+00:00",
    };
    let status = "approved";
    mockApi({
      "GET /api/admin/partners": () => ({
        items: [{ ...partner, status }], total: 1, page: 1, page_size: 20,
      }),
      "POST /api/admin/partners/p1/status": (init?: RequestInit) => {
        status = JSON.parse(String(init?.body)).status;
        return { ...partner, status };
      },
    });
    renderAt("/admin/partners", <Route path="/admin/partners" element={<AdminPartnersPage />} />);
    await userEvent.click(await screen.findByRole("button", { name: "Disable" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Disable" }));
    expect(await screen.findByRole("button", { name: "Enable" })).toBeInTheDocument();
  });

  it("enables a suspended partner from the list", async () => {
    const partner = {
      id: "p1", user_id: "u3", organization: "West Coast Referral", contact_name: "Alex West",
      phone: "", referral_code: "WCR1", status: "suspended", kyc_status: "not_required",
      commission_mode: "percent_payment", commission_bps: 0, commission_flat_cents: 0,
      gstin: "", pan_number: "", payout_account: "", payout_ifsc: "",
      kyc_documents: [], click_count: 0, wallet: { accrued_cents: 0, approved_cents: 0, available_cents: 0 },
      created_at: "2026-10-09T00:00:00+00:00",
    };
    let status = "suspended";
    mockApi({
      "GET /api/admin/partners": () => ({
        items: [{ ...partner, status }], total: 1, page: 1, page_size: 20,
      }),
      "POST /api/admin/partners/p1/status": (init?: RequestInit) => {
        status = JSON.parse(String(init?.body)).status;
        return { ...partner, status };
      },
    });
    renderAt("/admin/partners", <Route path="/admin/partners" element={<AdminPartnersPage />} />);
    await userEvent.click(await screen.findByRole("button", { name: "Enable" }));
    expect(await screen.findByRole("button", { name: "Disable" })).toBeInTheDocument();
  });

  it("shows a complete partner dashboard", async () => {
    const partner = {
      id: "p1", user_id: "u3", organization: "West Coast Referral", contact_name: "Alex West",
      phone: "888", referral_code: "WEST01", status: "approved", kyc_status: "not_required",
      commission_mode: "percent_payment", commission_bps: 2000, commission_flat_cents: 0,
      gstin: "", pan_number: "", payout_account: "", payout_ifsc: "",
      kyc_documents: [] as { filename: string; note: string; uploaded_at: string }[],
      click_count: 4, wallet: { accrued_cents: 0, approved_cents: 0, available_cents: 0 },
      created_at: "2026-10-09T00:00:00+00:00",
    };
    const campus = {
      id: "i2", name: "Harbor College", email: "dean@harbor.edu", contact_name: "", phone: "",
      institute_type: "COLLEGE", gstin: "", pan_number: "", status: "active", partner_id: "p1",
      source: "partner", settings: {}, seats: { total: 10, available: 10, assigned: 0, by_status: {} },
      created_at: "2026-10-09T00:00:00+00:00",
    };
    const detail: AdminPartnerDetail = {
      partner, institutes: 1, recent_institutes: [campus], recent_commissions: [], referral_path: "/r/WEST01",
      login: {
        id: "u3", email: "alex.west@example.com", first_name: "Alex", last_name: "West",
        is_active: true, is_verified: true, last_login_at: null, created_at: "2026-10-09T00:00:00+00:00",
      },
      institute_list: [campus],
      commissions: [],
      payouts: [],
      campaigns: [],
      reports: {
        institutes_by_status: { pending: 0, active: 1, suspended: 0, closed: 0 },
        commissions_by_status: { accrued: 0, approved: 0, void: 0 },
        payouts_by_status: { requested: 0, approved: 0, paid: 0, rejected: 0 },
      },
    };
    mockApi({ "GET /api/admin/partners/p1": detail });
    renderAt("/admin/partners/p1", <Route path="/admin/partners/:id" element={<AdminPartnerPage />} />);
    expect(await screen.findByRole("heading", { name: "West Coast Referral" })).toBeInTheDocument();
    expect(screen.getAllByText("Campuses").length).toBeGreaterThan(0);
    expect(screen.getByText("Harbor College")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark active" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in as" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset password" })).toBeInTheDocument();
  });
});
