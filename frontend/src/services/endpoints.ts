import type {
  AdminAnalytics, AdminApplication, AdminAuditEntry, AdminEmailStatus, AdminPlatformSettings, EmailTemplates, TestEmailResult, AdminLogLine, AdminPlan, AdminRun, AdminSubscription, AdminUser,
  AdminInstituteDetail, AdminPartnerDetail, AdminUserDetail, AdminWorkers, AgentDevice, Application, ApplicationDetail, ApplicationStatus,
  Institute, InstituteAssignment, InstituteDashboard, Partner, PartnerCampaign, PartnerCommission,
  PartnerDashboard, PartnerPayout, SeatCounts,
  PlatformCms, PublicSite,
  AutomationOverview, AutomationRun, BillingOverview, CheckoutResult, DashboardStats, JobWithApplication, LogLevel,
  Notification, Page, Plan, PlanUpdate, PreferenceOptions, Profile, ProfileInput, Resume, ResumeTemplate, RunLogLine, SearchConfig,
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
  register: (body: {
    email: string; password: string; first_name?: string; last_name?: string;
    account_type?: "candidate" | "institute" | "partner"; institute_name?: string; contact_name?: string;
    phone?: string; gstin?: string; pan_number?: string; organization?: string; referral_code?: string; agreed?: boolean;
  }) =>
    request<{ message: string; verification_required?: boolean }>("/auth/register", { method: "POST", body }),
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
  application: () => request<import("../types").ApplicationPreferencesOut>("/preferences/application"),
  patchApplication: (changes: Record<string, unknown>) =>
    request<import("../types").ApplicationPreferencesOut>("/preferences/application", { method: "PATCH", body: changes }),
  resolvePending: (body: { answers: { id: string; answer: string }[] }) =>
    request<import("../types").ApplicationPreferencesOut>("/preferences/application/resolve-pending", {
      method: "POST",
      body,
    }),
};

export const resumes = {
  list: () => request<{ resumes: Resume[]; limit: number }>("/resumes"),
  templates: () => request<{ templates: ResumeTemplate[] }>("/resumes/templates"),
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
  analyzeMaster: (id: string) => request<Resume>(`/resumes/${id}/analyze-master`, { method: "POST" }),
  intake: (id: string, apply = true) =>
    request<import("../types").ResumeIntake>(`/resumes/${id}/intake`, { method: "POST", body: { apply } }),
  updateMasterSkills: (id: string, master_skills: string[]) =>
    request<Resume>(`/resumes/${id}/master-skills`, { method: "PATCH", body: { master_skills } }),
  aiPreview: (body: { resume_id: string; job_description: string }) =>
    request<import("../types").ResumeAiPreview>("/resumes/ai/preview", { method: "POST", body }),
  aiTailor: (body: {
    resume_id: string;
    job_description: string;
    job_id?: string;
    application_id?: string;
    template_id?: string;
  }) => request<Resume>("/resumes/ai/tailor", { method: "POST", body }),
  applyStyle: (id: string, template_id: string, application_id?: string) =>
    request<Resume>(`/resumes/${id}/apply-style`, {
      method: "POST",
      body: { template_id, application_id: application_id || undefined },
    }),
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
  preferences: () => request<import("../types").NotificationPreferences>("/notifications/preferences"),
  updatePreferences: (body: { types: Record<string, { email: boolean }> }) =>
    request<import("../types").NotificationPreferences>("/notifications/preferences", { method: "PATCH", body }),
};

export const automation = {
  overview: () => request<AutomationOverview>("/automation"),
  start: (body: { dry_run: boolean; resume_mode: import("../types").ResumeRunMode }) =>
    request<AutomationRun>("/automation/start", { method: "POST", body }),
  pause: (id: string) => request<AutomationRun>(`/automation/${id}/pause`, { method: "POST" }),
  resume: (id: string) => request<AutomationRun>(`/automation/${id}/resume`, { method: "POST" }),
  stop: (id: string) => request<AutomationRun>(`/automation/${id}/stop`, { method: "POST" }),
  logs: (id: string, after: number) =>
    request<{ items: RunLogLine[]; next_after: number }>(`/automation/${id}/logs`, { query: { after } }),
  devices: () => request<{ devices: AgentDevice[] }>("/automation/devices").then((d) => d.devices),
  desktopAgentDownloadUrl: () =>
    import.meta.env.VITE_AGENT_DOWNLOAD_URL || buildUrl("/automation/desktop-agent/download"),
  pairingCode: () => request<{ code: string; expires_at: string }>("/automation/devices/pairing-code", { method: "POST" }),
  approveConnect: (sessionId: string) =>
    request<{ ok: boolean; device_name?: string }>("/automation/devices/connect/approve", {
      method: "POST",
      body: { session_id: sessionId },
    }),
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

export const site = {
  public: () => request<PublicSite>("/site/public"),
};

export const admin = {
  analytics: () => request<AdminAnalytics>("/admin/analytics"),
  users: (query: Paged & { q?: string; status?: string; plan?: string }) =>
    request<Page<AdminUser>>("/admin/users", { query }),
  createUser: (body: {
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
    is_admin?: boolean;
    is_verified?: boolean;
  }) => request<AdminUserDetail>("/admin/users", { method: "POST", body }),
  user: (id: string) => request<AdminUserDetail>(`/admin/users/${id}`),
  updateUser: (id: string, body: {
    email?: string;
    first_name?: string;
    last_name?: string;
    is_active?: boolean;
    is_admin?: boolean;
    is_verified?: boolean;
  }) => request<AdminUserDetail>(`/admin/users/${id}`, { method: "PATCH", body }),
  deleteUser: (id: string) => request<{ ok: true }>(`/admin/users/${id}`, { method: "DELETE" }),
  userPassword: (id: string, password: string) =>
    request<AdminUserDetail>(`/admin/users/${id}/password`, { method: "POST", body: { password } }),
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
  settings: () => request<AdminPlatformSettings>("/admin/settings"),
  updateCms: (body: PlatformCms) => request<{ cms: PlatformCms }>("/admin/settings/cms", { method: "PUT", body }),
  updateSmtp: (body: {
    enabled: boolean; host: string; port: number; username: string; password: string; from_address: string;
  }) => request<{ smtp: AdminPlatformSettings["smtp"] }>("/admin/settings/smtp", { method: "PUT", body }),
  updateAuthEmail: (body: AdminPlatformSettings["auth_email"]) =>
    request<{ auth_email: AdminPlatformSettings["auth_email"] }>("/admin/settings/auth-email", { method: "PUT", body }),
  updateNotifications: (body: { types: Record<string, { email: boolean }> }) =>
    request<{ notifications: AdminPlatformSettings["notifications"] }>("/admin/settings/notifications", { method: "PUT", body }),
  updateEmailTemplates: (body: EmailTemplates) =>
    request<{ email_templates: EmailTemplates }>("/admin/settings/email-templates", { method: "PUT", body }),
  testEmailTemplate: (body: { kind: string; to?: string }) =>
    request<TestEmailResult>("/admin/email/test-template", { method: "POST", body }),
  broadcastNotifications: (body: { title: string; body: string; link?: string; user_ids: string[] }) =>
    request<{ sent: number }>("/admin/notifications/broadcast", { method: "POST", body }),
  updateAi: (body: {
    enabled: boolean;
    provider: string;
    base_url: string;
    api_key?: string;
    models: { fast: string; strong: string; embedding: string };
    features: { applications: boolean; resume: boolean };
  }) => request<{ ai: AdminPlatformSettings["ai"] }>("/admin/settings/ai", { method: "PUT", body }),
  testAi: () => request<{ ok: boolean; reply: string }>("/admin/settings/ai/test", { method: "POST" }),
  updatePayments: (body: {
    provider: "null" | "razorpay";
    key_id: string;
    key_secret?: string;
    webhook_secret?: string;
  }) => request<{ payments: AdminPlatformSettings["payments"] }>("/admin/settings/payments", { method: "PUT", body }),
  testPayments: () =>
    request<{ ok: boolean; mode: string; test_checkout_hint?: string; message?: string }>(
      "/admin/settings/payments/test",
      { method: "POST" },
    ),
  syncRazorpayPlans: () =>
    request<{ created: { code: string; provider_plan_id: string }[] }>("/admin/settings/payments/sync-plans", { method: "POST" }),
  email: () => request<AdminEmailStatus>("/admin/email"),
  testEmail: (to: string) => request<TestEmailResult>("/admin/email/test", { method: "POST", body: { to: to || null } }),
  verifyEmail: (id: string) => request<AdminUserDetail>(`/admin/users/${id}/verify-email`, { method: "POST" }),
  resendVerification: (id: string) =>
    request<AdminUserDetail>(`/admin/users/${id}/resend-verification`, { method: "POST" }),
  plans: () => request<{ plans: AdminPlan[] }>("/admin/plans").then((d) => d.plans),
  updatePlan: (code: string, body: PlanUpdate) => request<AdminPlan>(`/admin/plans/${code}`, { method: "PUT", body }),
  institutes: (query: Paged & { q?: string; status?: string }) => request<Page<Institute>>("/admin/institutes", { query }),
  createInstitute: (body: {
    name: string; email: string; password: string; contact_name?: string; phone?: string; approve?: boolean;
  }) => request<Institute>("/admin/institutes", { method: "POST", body }),
  institute: (id: string) => request<AdminInstituteDetail>("/admin/institutes/" + id),
  updateInstitute: (id: string, body: { name: string; contact_name?: string; phone?: string }) =>
    request<Institute>(`/admin/institutes/${id}`, { method: "PUT", body }),
  setInstituteStatus: (id: string, status: string) =>
    request<Institute>(`/admin/institutes/${id}/status`, { method: "POST", body: { status } }),
  institutePassword: (id: string, password: string) =>
    request<{ ok: true }>(`/admin/institutes/${id}/password`, { method: "POST", body: { password } }),
  instituteLoginAs: (id: string) => request<{ user: User }>(`/admin/institutes/${id}/login-as`, { method: "POST" }),
  partners: (query: Paged & { q?: string; status?: string }) => request<Page<Partner>>("/admin/partners", { query }),
  createPartner: (body: {
    organization: string;
    email: string;
    password: string;
    contact_name?: string;
    phone?: string;
    approve?: boolean;
    commission_mode?: string;
    commission_bps?: number;
    commission_flat_cents?: number;
  }) => request<Partner>("/admin/partners", { method: "POST", body }),
  partner: (id: string) => request<AdminPartnerDetail>(`/admin/partners/${id}`),
  updatePartner: (id: string, body: {
    organization: string;
    contact_name?: string;
    phone?: string;
    commission_mode: string;
    commission_bps: number;
    commission_flat_cents: number;
    status: string;
    kyc_status: string;
    gstin?: string;
    pan_number?: string;
    payout_account?: string;
    payout_ifsc?: string;
    email?: string | null;
  }) => request<Partner>(`/admin/partners/${id}`, { method: "PUT", body }),
  setPartnerStatus: (id: string, status: string) =>
    request<Partner>(`/admin/partners/${id}/status`, { method: "POST", body: { status } }),
  setPartnerKyc: (id: string, status: string) =>
    request<Partner>(`/admin/partners/${id}/kyc`, { method: "POST", body: { status } }),
  partnerPassword: (id: string, password: string) =>
    request<{ ok: true }>(`/admin/partners/${id}/password`, { method: "POST", body: { password } }),
  partnerLoginAs: (id: string) => request<{ user: User }>(`/admin/partners/${id}/login-as`, { method: "POST" }),
  setCommissionStatus: (id: string, status: string) =>
    request<PartnerCommission>(`/admin/commissions/${id}/status`, { method: "POST", body: { status } }),
  setPayoutStatus: (id: string, status: string, note?: string) =>
    request<PartnerPayout>(`/admin/payouts/${id}/status`, { method: "POST", body: { status, note } }),
};

export const institute = {
  me: () => request<{ institute: Institute; role: string }>("/institute/me"),
  dashboard: () => request<InstituteDashboard>("/institute/dashboard"),
  students: (query: Paged & { status?: string } = {}) => request<Page<InstituteAssignment>>("/institute/students", { query }),
  invite: (email: string, note = "") =>
    request<{ assignment: InstituteAssignment }>("/institute/students/invite", { method: "POST", body: { email, note } }),
  release: (id: string) => request<{ assignment: InstituteAssignment }>(`/institute/students/${id}/release`, { method: "POST" }),
  suspend: (id: string) => request<{ assignment: InstituteAssignment }>(`/institute/students/${id}/suspend`, { method: "POST" }),
  invitations: () => request<{ items: InstituteAssignment[] }>("/institute/invitations"),
  seats: () => request<{ items: { id: string; status: string; created_at: string }[]; counts: SeatCounts }>("/institute/seats"),
  plans: () => request<{ plans: Plan[] }>("/institute/plans").then((d) => d.plans),
  subscription: () => request<{ subscription: Subscription | null; seats: SeatCounts }>("/institute/subscription"),
  checkout: (plan: string) => request<CheckoutResult>("/institute/subscription/checkout", { method: "POST", body: { plan } }),
  reports: () => request<{ seats: SeatCounts; assignments_by_status: Record<string, number> }>("/institute/reports"),
  profile: () => request<Institute>("/institute/profile"),
  saveProfile: (body: Partial<Institute>) => request<Institute>("/institute/profile", { method: "PUT", body }),
  saveSettings: (body: Record<string, unknown>) => request<Institute>("/institute/settings", { method: "PUT", body }),
};

export const partner = {
  me: () => request<Partner>("/partner/me"),
  dashboard: () => request<PartnerDashboard>("/partner/dashboard"),
  institutes: () => request<{ items: Institute[] }>("/partner/institutes"),
  enroll: (body: { name: string; email: string; password: string; contact_name?: string; phone?: string }) =>
    request<Institute>("/partner/institutes", { method: "POST", body }),
  referrals: () => request<{ referral_code: string; referral_path: string; click_count: number; institutes: Institute[] }>("/partner/referrals"),
  commissions: () => request<{ items: PartnerCommission[]; wallet: Partner["wallet"] }>("/partner/commissions"),
  payouts: () => request<{ items: PartnerPayout[]; wallet: Partner["wallet"] }>("/partner/payouts"),
  requestPayout: (amount_cents?: number) =>
    request<PartnerPayout>("/partner/payouts", { method: "POST", body: { amount_cents } }),
  campaigns: () => request<{ items: PartnerCampaign[] }>("/partner/campaigns"),
  createCampaign: (name: string, note = "") =>
    request<PartnerCampaign>("/partner/campaigns", { method: "POST", body: { name, note } }),
  marketing: () => request<{ referral_path: string; assets: { title: string; text: string }[] }>("/partner/marketing"),
  links: () => request<{ referral_path: string; campaigns: PartnerCampaign[] }>("/partner/links"),
  saveProfile: (body: Partial<Partner>) => request<Partner>("/partner/profile", { method: "PUT", body }),
  addKyc: (filename: string, note = "") => request<Partner>("/partner/kyc", { method: "POST", body: { filename, note } }),
  saveTax: (body: Partial<Partner>) => request<Partner>("/partner/tax", { method: "PUT", body }),
};

export const invites = {
  preview: (token: string) => request<{ institute_name: string; email: string; status: string; expires_at: string }>(`/invites/${token}`),
  accept: (token: string) => request<{ assignment: InstituteAssignment }>(`/invites/${token}/accept`, { method: "POST" }),
};

export const referrals = {
  capture: (code: string, campaign?: string) =>
    request<{ referral_code: string; organization: string; redirect: string }>(`/r/${code}`, { query: { c: campaign } }),
};
