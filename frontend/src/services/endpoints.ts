import type {
  AdminAnalytics, AdminApplication, AdminAuditEntry, AdminEmailStatus, TestEmailResult, AdminLogLine, AdminPlan, AdminRun, AdminSubscription, AdminUser,
  AdminUserDetail, AdminWorkers, AgentDevice, Answers, Application, ApplicationDetail, ApplicationStatus,
  AutomationOverview, AutomationRun, BillingOverview, CheckoutResult, DashboardStats, JobWithApplication, LogLevel,
  Notification, Page, Plan, PlanUpdate, PreferenceOptions, Profile, ProfileInput, Resume, RunLogLine, SearchConfig,
  SearchConfigOut, Subscription, SubscriptionStatus, Usage, User,
} from "../types";
import { buildUrl, request } from "./api";

export interface ApplicationFilters {
  status?: ApplicationStatus[];
  q?: string;
  company?: string;
  applied_from?: string;
  applied_to?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

export const auth = {
  me: () => request<{ user: User }>("/auth/me").then((d) => d.user),
  login: (email: string, password: string) =>
    request<{ user: User }>("/auth/login", { method: "POST", body: { email, password } }).then((d) => d.user),
  register: (body: { email: string; password: string; first_name?: string; last_name?: string }) =>
    request<{ message: string }>("/auth/register", { method: "POST", body }),
  logout: () => request("/auth/logout", { method: "POST" }),
  logoutAll: () => request("/auth/logout-all", { method: "POST" }),
  verifyEmail: (token: string) =>
    request<{ user: User }>("/auth/verify-email", { method: "POST", body: { token } }),
  resendVerification: (email: string) =>
    request<{ message: string }>("/auth/resend-verification", { method: "POST", body: { email } }),
  forgotPassword: (email: string) =>
    request<{ message: string }>("/auth/forgot-password", { method: "POST", body: { email } }),
  resetPassword: (token: string, new_password: string) =>
    request("/auth/reset-password", { method: "POST", body: { token, new_password } }),
};

export const profile = {
  get: () => request<Profile>("/profile"),
  update: (body: ProfileInput) => request<Profile>("/profile", { method: "PUT", body }),
};

export const preferences = {
  options: () => request<PreferenceOptions>("/preferences/options"),
  search: () => request<SearchConfigOut>("/preferences/search"),
  saveSearch: (body: SearchConfig) => request<SearchConfigOut>("/preferences/search", { method: "PUT", body }),
  application: () => request<Answers>("/preferences/application"),
  patchApplication: (changes: Record<string, unknown>) =>
    request<Answers>("/preferences/application", { method: "PATCH", body: changes }),
};

export const resumes = {
  list: () => request<{ resumes: Resume[]; limit: number }>("/resumes"),
  upload: (file: File, name?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (name) form.append("name", name);
    return request<Resume>("/resumes", { method: "POST", form });
  },
  rename: (id: string, name: string) => request<Resume>(`/resumes/${id}`, { method: "PATCH", body: { name } }),
  makeDefault: (id: string) => request<Resume>(`/resumes/${id}/default`, { method: "POST" }),
  remove: (id: string) => request(`/resumes/${id}`, { method: "DELETE" }),
  downloadUrl: (id: string) => buildUrl(`/resumes/${id}/download`),
};

export const applications = {
  list: (filters: ApplicationFilters) =>
    request<Page<Application>>("/applications", { query: { ...filters } }),
  get: (id: string) => request<ApplicationDetail>(`/applications/${id}`),
  exportUrl: (filters: ApplicationFilters) => {
    const { page: _page, page_size: _size, ...rest } = filters;
    return buildUrl("/applications/export", { ...rest });
  },
};

export const jobs = {
  list: (query: { q?: string; work_setting?: string; page?: number; page_size?: number }) =>
    request<Page<JobWithApplication>>("/jobs", { query }),
};

export const dashboard = {
  stats: () => request<DashboardStats>("/dashboard/stats"),
  usage: () => request<Usage>("/usage"),
};

export const notifications = {
  list: (query: { unread_only?: boolean; page?: number; page_size?: number } = {}) =>
    request<Page<Notification> & { unread_count: number }>("/notifications", { query }),
  read: (id: string) => request<Notification>(`/notifications/${id}/read`, { method: "POST" }),
  readAll: () => request<{ marked: number }>("/notifications/read-all", { method: "POST" }),
};

export const automation = {
  overview: () => request<AutomationOverview>("/automation"),
  start: (dryRun: boolean) => request<AutomationRun>("/automation/start", { method: "POST", body: { dry_run: dryRun } }),
  pause: (id: string) => request<AutomationRun>(`/automation/${id}/pause`, { method: "POST" }),
  resume: (id: string) => request<AutomationRun>(`/automation/${id}/resume`, { method: "POST" }),
  stop: (id: string) => request<AutomationRun>(`/automation/${id}/stop`, { method: "POST" }),
  logs: (id: string, after: number) =>
    request<{ items: RunLogLine[]; next_after: number }>(`/automation/${id}/logs`, { query: { after } }),
  devices: () => request<{ devices: AgentDevice[] }>("/automation/devices").then((d) => d.devices),
  pairingCode: () => request<{ code: string; expires_at: string }>("/automation/devices/pairing-code", { method: "POST" }),
  removeDevice: (id: string) => request(`/automation/devices/${id}`, { method: "DELETE" }),
};

export const plans = {
  list: () => request<{ plans: Plan[] }>("/plans").then((d) => d.plans),
};

export const billing = {
  overview: () => request<BillingOverview>("/billing"),
  checkout: (plan: string) => request<CheckoutResult>("/billing/checkout", { method: "POST", body: { plan } }),
  confirm: (body: { payment_id: string; subscription_id: string; signature: string }) =>
    request<{ subscription: Subscription }>("/billing/confirm", { method: "POST", body }),
  cancel: () => request<{ subscription: Subscription }>("/billing/cancel", { method: "POST" }),
};

type Paged = { page?: number; page_size?: number };

export const admin = {
  analytics: () => request<AdminAnalytics>("/admin/analytics"),
  users: (query: Paged & { q?: string; status?: string; plan?: string }) =>
    request<Page<AdminUser>>("/admin/users", { query }),
  user: (id: string) => request<AdminUserDetail>(`/admin/users/${id}`),
  updateUser: (id: string, body: { is_active?: boolean; is_admin?: boolean }) =>
    request<AdminUserDetail>(`/admin/users/${id}`, { method: "PATCH", body }),
  grantPlan: (id: string, body: { plan: string; months: number; note: string }) =>
    request<AdminUserDetail>(`/admin/users/${id}/grant-plan`, { method: "POST", body }),
  revokePlan: (id: string) => request<AdminUserDetail>(`/admin/users/${id}/revoke-plan`, { method: "POST" }),
  subscriptions: (query: Paged & { status?: SubscriptionStatus | ""; plan?: string }) =>
    request<Page<AdminSubscription>>("/admin/subscriptions", { query }),
  runs: (query: Paged & { status?: string }) => request<Page<AdminRun>>("/admin/automation-jobs", { query }),
  stopRun: (id: string) => request<AutomationRun>(`/admin/automation-jobs/${id}/stop`, { method: "POST" }),
  applications: (query: Paged & { status?: ApplicationStatus | ""; q?: string }) =>
    request<Page<AdminApplication>>("/admin/applications", { query }),
  logs: (query: Paged & { level: LogLevel[]; q?: string }) => request<Page<AdminLogLine>>("/admin/logs", { query }),
  audit: (query: Paged) => request<Page<AdminAuditEntry>>("/admin/audit-log", { query }),
  workers: () => request<AdminWorkers>("/admin/workers"),
  email: () => request<AdminEmailStatus>("/admin/email"),
  testEmail: (to: string) => request<TestEmailResult>("/admin/email/test", { method: "POST", body: { to: to || null } }),
  verifyEmail: (id: string) => request<AdminUserDetail>(`/admin/users/${id}/verify-email`, { method: "POST" }),
  resendVerification: (id: string) =>
    request<AdminUserDetail>(`/admin/users/${id}/resend-verification`, { method: "POST" }),
  plans: () => request<{ plans: AdminPlan[] }>("/admin/plans").then((d) => d.plans),
  updatePlan: (code: string, body: PlanUpdate) => request<AdminPlan>(`/admin/plans/${code}`, { method: "PUT", body }),
};
