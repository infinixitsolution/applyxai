import type {
  AdminAnalytics, AdminApplication, AdminAuditEntry, AdminCompany, AdminCompanyDetail, AdminEmailStatus, AdminPayment, AdminPlatformSettings, EmailTemplates, GstPlatformSettings, GstPreviewTotals, TaxInvoiceRecord, TestEmailResult, AdminLogLine, AdminPlan, AdminRun, AdminSubscription, AdminUser,
  AdminInstituteDetail, AdminPartnerDetail, AdminUserDetail, AdminWorkers, AgentDevice, Application, ApplicationDetail, ApplicationStatus,
  InterviewType, MockInterviewCompleteResult, MockInterviewFeedback, MockInterviewFeedbackJob, MockInterviewPresenterSettings, MockInterviewSessionDetail, MockInterviewSessionSummary, MockInterviewTurnResult,
  Institute, InstituteAssignment, InstituteDashboard, InstituteSeat, InstituteStudentDetail, Partner, PartnerCampaign, PartnerCommission,
  PartnerDashboard, PartnerPayout, SeatCounts,
  PlatformCms, PublicSite,
  AutomationOverview, AutomationRun, BillingOverview, CheckoutResult, DashboardStats, DesktopAgentInfo, JobWithApplication, LogLevel, PaymentRecord,
  LiveInterviewSession, Notification, Page, Plan, PlanUpdate, PreferenceOptions, Profile, ProfileInput, Resume, ResumeTemplate, RunLogLine, SearchConfig,
  SupportMessage, SupportThread,
  SearchConfigOut, Subscription, SubscriptionStatus, Usage, User,
  OutreachBulkActionResult, OutreachBulkImportResult, OutreachCampaignSettings, OutreachLead, OutreachLeadChatMessage, OutreachLeadDashboardStats, OutreachLeadMessage, OutreachProfileCompletion, OutreachScrapeJob, OutreachWhatsappChatThread, OutreachWhatsappRecentSend, OutreachWhatsappStatus,
} from "../types";
import { ApiError, buildUrl, request, requestFull } from "./api";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Firecrawl + profile completion can run several minutes per batch. */
const OUTREACH_TIMEOUT_MS = 300_000;

async function waitForMockInterviewFeedbackJob(
  jobId: string,
  sessionId: string,
): Promise<{ session: MockInterviewSessionDetail; feedback: MockInterviewFeedback }> {
  for (let attempt = 0; attempt < 90; attempt += 1) {
    const job = await request<MockInterviewFeedbackJob>(`/mock-interviews/feedback-jobs/${jobId}`);
    if (job.status === "failed") {
      throw new ApiError(
        job.error_code ?? "FEEDBACK_FAILED",
        job.error_message ?? "Report generation failed.",
        502,
      );
    }
    if (job.status === "succeeded") {
      const session = await request<MockInterviewSessionDetail>(`/mock-interviews/sessions/${sessionId}`);
      return { session, feedback: (session.feedback ?? {}) as MockInterviewFeedback };
    }
    await sleep(2000);
  }
  throw new ApiError("TIMEOUT", "Report generation is taking longer than expected. Refresh the page in a moment.", 504);
}

async function finishMockInterviewAction(
  path: string,
  sessionId: string,
  body: { presentation_frames?: string[] },
): Promise<{ session: MockInterviewSessionDetail; feedback: MockInterviewFeedback }> {
  const { status, data } = await requestFull<MockInterviewCompleteResult>(path, { method: "POST", body });
  if (status === 202 && data.job?.job_id) {
    return waitForMockInterviewFeedbackJob(data.job.job_id, sessionId);
  }
  if (data.session && data.feedback) {
    return { session: data.session, feedback: data.feedback };
  }
  if (data.session?.feedback) {
    return { session: data.session, feedback: data.session.feedback as MockInterviewFeedback };
  }
  throw new ApiError("FEEDBACK_PENDING", "Report is still processing.", 202);
}

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
  login: async (email: string, password: string) => {
    const data = await request<{ user?: User; requires_2fa?: boolean; challenge_token?: string }>(
      "/auth/login",
      { method: "POST", body: { email, password } },
    );
    if (data.requires_2fa && data.challenge_token) {
      return { kind: "2fa" as const, challengeToken: data.challenge_token };
    }
    return { kind: "session" as const, user: data.user! };
  },
  loginTwoFactor: (challengeToken: string, code: string) =>
    request<{ user: User }>("/auth/login/2fa", { method: "POST", body: { challenge_token: challengeToken, code } }).then(
      (d) => d.user,
    ),
  twoFactorSetup: () =>
    request<{ secret: string; otpauth_uri: string }>("/auth/2fa/setup", { method: "POST" }),
  twoFactorEnable: (code: string) =>
    request<{ totp_enabled: boolean }>("/auth/2fa/enable", { method: "POST", body: { code } }),
  twoFactorDisable: (password: string, code: string) =>
    request<{ totp_enabled: boolean }>("/auth/2fa/disable", { method: "POST", body: { password, code } }),
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
  patchSection: (section: string, data: unknown) =>
    request<Profile>(`/profile/sections/${section}`, { method: "PATCH", body: { data } }),
  enhance: () =>
    request<{
      source: "ai" | "heuristic";
      steps: { id: string; ok: boolean; source?: string; detail?: string }[];
      percent: number;
      missing: { section: string; label: string; hint?: string; ai?: boolean }[];
      profile: Profile;
    }>("/profile/ai-enhance", { method: "POST", timeoutMs: 180_000 }),
  completeProfessional: () =>
    request<{
      source: "ai" | "heuristic";
      headline: string;
      summary: string;
      filled: string[];
      profile: Profile;
    }>("/profile/sections/professional/ai-complete", { method: "POST" }),
  enhanceCareer: () =>
    request<{
      source: "ai" | "heuristic";
      preferred_roles: string[];
      preferred_locations: string[];
      desired_industries: string[];
      profile: Profile;
    }>("/profile/sections/career/ai-enhance", { method: "POST" }),
  fillCommonAnswers: () =>
    request<{
      source: "ai" | "heuristic";
      filled: string[];
      skipped_verified: string[];
      profile: Profile;
    }>("/profile/sections/common_answers/ai-fill", { method: "POST" }),
  fillScreening: () =>
    request<{
      source: "ai" | "heuristic";
      filled: string[];
      answers: Record<string, unknown>;
    }>("/profile/sections/screening/ai-fill", { method: "POST" }),
  fillEmployment: () =>
    request<{
      source: "ai" | "heuristic";
      kind: "fresher" | "experienced";
      status: string;
      note: string;
      jobs: { title: string; company: string; location: string; start: string; end: string; summary: string }[];
      experience_years: number | null;
      profile: Profile;
    }>("/profile/sections/employment/ai-fill", { method: "POST" }),
  fillProjects: () =>
    request<{
      source: "ai" | "heuristic";
      kind: "academic" | "professional";
      added: string[];
      projects: { id: string; title: string; description: string; role: string; technologies: string }[];
      profile: Profile;
    }>("/profile/sections/projects/ai-fill", { method: "POST" }),
  fillSkills: () =>
    request<{
      source: "ai" | "heuristic";
      skills: string[];
      rows: { id: string; name: string; category: string; years: string; proficiency: string; description: string }[];
      profile: Profile;
    }>("/profile/sections/skills/ai-fill", { method: "POST", timeoutMs: 120_000 }),
  taxonomies: () =>
    request<{
      industries: { id: string; label: string }[];
      departments: { id: string; label: string }[];
      job_roles: { id: string; label: string }[];
      education_levels: string[];
      employment_types: string[];
      skill_categories: string[];
    }>("/profile/taxonomies"),
  uploadPhoto: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Profile>("/profile/photo", { method: "POST", form });
  },
  deletePhoto: () => request<Profile>("/profile/photo", { method: "DELETE" }),
};

export const profileLinkedIn = {
  syncPlan: () =>
    request<{
      snapshot: Record<string, unknown>;
      plan: { section: string; action: string; preview?: string; policy?: string; reason?: string }[];
      settings: Record<string, unknown>;
    }>("/profile/linkedin/sync-plan"),
  aiComplete: () =>
    request<{ headline: string; about: string; skills: string[]; experience_bullets: unknown[]; unchanged?: boolean }>(
      "/profile/linkedin/ai-complete",
      { method: "POST" },
    ),
  applyAiDraft: (draft: Record<string, unknown>) =>
    request<Profile>("/profile/linkedin/apply-ai-draft", { method: "POST", body: { draft } }),
};

export const customQuestions = {
  list: () => request<import("../types").CustomQuestionsList>("/questions"),
  syncFromProfile: () =>
    request<{
      source: "ai" | "heuristic";
      updated: string[];
      dropped_standard: string[];
      deduped_from: number;
      items: import("../types").HumanQuestion[];
      total: number;
    }>("/questions/sync-from-profile", { method: "POST", timeoutMs: 180_000 }),
  replace: (items: import("../types").HumanQuestion[]) =>
    request<import("../types").CustomQuestionsList>("/questions", { method: "PUT", body: { items } }),
  patch: (id: string, body: Partial<import("../types").HumanQuestion>) =>
    request<import("../types").HumanQuestion>(`/questions/${id}`, { method: "PATCH", body }),
  remove: (id: string) => request<{ deleted: boolean }>(`/questions/${id}`, { method: "DELETE" }),
};

export const automationSettings = {
  get: () => request<import("../types").AutomationSettingsOut>("/settings/automation"),
  patch: (changes: Record<string, unknown>) =>
    request<import("../types").AutomationSettingsOut>("/settings/automation", { method: "PATCH", body: changes }),
  reset: () => request<import("../types").AutomationSettingsOut>("/settings/automation/reset", { method: "POST" }),
};

export const preferences = {
  options: () => request<PreferenceOptions>("/preferences/options"),
  search: () => request<SearchConfigOut>("/preferences/search"),
  saveSearch: (body: SearchConfig) => request<SearchConfigOut>("/preferences/search", { method: "PUT", body }),
  application: () => request<import("../types").ApplicationPreferencesOut>("/preferences/application"),
  patchApplication: (changes: Record<string, unknown>) =>
    request<import("../types").ApplicationPreferencesOut>("/preferences/application", { method: "PATCH", body: changes }),
  resolvePending: (body: { answers: { id: string; answer: string; label?: string; question_type?: string }[] }) =>
    request<import("../types").ApplicationPreferencesOut>("/preferences/application/resolve-pending", {
      method: "POST",
      body,
    }),
  suggestPendingAi: (body: { ids?: string[] }) => {
    type Out = { suggestions: { id: string; answer: string }[]; skipped: { id: string; reason: string }[] };
    const payload = { mode: "ai_suggest" as const, ids: body.ids };
    return request<Out>("/preferences/application/resolve-pending", { method: "POST", body: payload });
  },
};

export const resumes = {
  list: () =>
    request<{
      resumes: Resume[];
      limit: number;
      created_this_month?: number;
      library_count?: number;
      built_count?: number;
    }>("/resumes"),
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

export const mockInterviews = {
  availability: () =>
    request<{
      available: boolean;
      reason: string;
      message: string;
      voice: boolean;
      provider?: string;
      presenter?: MockInterviewPresenterSettings;
    }>("/mock-interviews/availability"),
  listSessions: (query: { page?: number; page_size?: number } = {}) =>
    request<Page<MockInterviewSessionSummary>>("/mock-interviews/sessions", { query }),
  createSession: (body: { application_id: string; interview_types: InterviewType[] }) =>
    request<MockInterviewSessionSummary>("/mock-interviews/sessions", { method: "POST", body }),
  getSession: (id: string) => request<MockInterviewSessionDetail>(`/mock-interviews/sessions/${id}`),
  opening: (id: string) =>
    request<{ interviewer_message: MockInterviewTurnResult["interviewer_message"]; should_end: boolean; audio_base64: string; audio_mime: string }>(
      `/mock-interviews/sessions/${id}/opening`,
      { method: "POST", query: { include_audio: false } },
    ),
  turn: (id: string, content: string, clientTurnId?: string) =>
    request<MockInterviewTurnResult>(`/mock-interviews/sessions/${id}/turns`, {
      method: "POST",
      body: { content, client_turn_id: clientTurnId },
      query: { include_audio: false },
    }),
  messageTts: (sessionId: string, messageId: string) =>
    request<{ audio_base64: string; audio_mime: string }>(
      `/mock-interviews/sessions/${sessionId}/messages/${messageId}/tts`,
      { method: "POST", body: {} },
    ),
  getFeedbackJob: (jobId: string) => request<MockInterviewFeedbackJob>(`/mock-interviews/feedback-jobs/${jobId}`),
  complete: (id: string, body: { presentation_frames?: string[] } = {}) =>
    finishMockInterviewAction(`/mock-interviews/sessions/${id}/complete`, id, body),
  regenerateFeedback: (id: string, body: { presentation_frames?: string[] } = {}) =>
    finishMockInterviewAction(`/mock-interviews/sessions/${id}/regenerate-feedback`, id, body),
  transcribe: (file: Blob, filename = "audio.webm") => {
    const form = new FormData();
    form.append("file", file, filename);
    return request<{ text: string }>("/mock-interviews/transcribe", { method: "POST", form });
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

export const support = {
  thread: () => request<{ thread: SupportThread; messages: SupportMessage[] }>("/support/thread"),
  send: (body: string) => request<{ message: SupportMessage }>("/support/messages", { method: "POST", body: { body } }),
  requestLiveInterview: () => request<{ thread: SupportThread; messages: SupportMessage[] }>("/support/live-interview-request", { method: "POST" }),
};

export const liveInterviews = {
  list: () => request<{ sessions: LiveInterviewSession[] }>("/live-interviews").then((d) => d.sessions),
  get: (id: string) => request<LiveInterviewSession>(`/live-interviews/${id}`),
  applications: () => request<{ applications: { id: string; title: string; company: string }[] }>("/live-interviews/applications").then((d) => d.applications),
  attach: (id: string, applicationId: string) => request<LiveInterviewSession>(`/live-interviews/${id}/application`, { method: "PUT", body: { application_id: applicationId } }),
  regenerate: (id: string) => request<LiveInterviewSession>(`/live-interviews/${id}/regenerate`, { method: "POST" }),
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
  getRun: (id: string) => request<AutomationRun>(`/automation/${id}`),
  start: (body: {
    dry_run: boolean;
    resume_mode: import("../types").ResumeRunMode;
    sources: Array<"linkedin" | "naukri">;
    switch_after?: number;
  }) => request<AutomationRun>("/automation/start", { method: "POST", body }),
  profileSyncReadiness: () => request<{ ready: boolean; problems: string[] }>("/automation/profile-sync/readiness"),
  profileSyncStart: (body: { dry_run?: boolean; include_photo?: boolean; sections?: string[]; overwrite_sections?: string[] }) =>
    request<AutomationRun>("/automation/profile-sync/start", { method: "POST", body }),
  pause: (id: string) => request<AutomationRun>(`/automation/${id}/pause`, { method: "POST" }),
  resume: (id: string) => request<AutomationRun>(`/automation/${id}/resume`, { method: "POST" }),
  stop: (id: string) => request<AutomationRun>(`/automation/${id}/stop`, { method: "POST" }),
  logs: (id: string, after: number) =>
    request<{ items: RunLogLine[]; next_after: number }>(`/automation/${id}/logs`, { query: { after } }),
  devices: () => request<{ devices: AgentDevice[] }>("/automation/devices").then((d) => d.devices),
  desktopAgentDownloadUrl: (format: "exe" | "zip" = "exe") => {
    const direct = import.meta.env.VITE_AGENT_DOWNLOAD_URL;
    if (direct && format === "exe") return direct;
    const base = buildUrl("/automation/desktop-agent/download");
    return format === "zip" ? `${base}?format=zip` : base;
  },
  desktopAgentInfo: () => request<DesktopAgentInfo>("/automation/desktop-agent/info"),
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
  payments: (query: Paged & { status?: string }) => request<Page<PaymentRecord>>("/billing/payments", { query }),
  checkout: (plan: string) => request<CheckoutResult>("/billing/checkout", { method: "POST", body: { plan } }),
  confirm: (body: { payment_id: string; subscription_id: string; signature: string }) =>
    request<{ subscription: Subscription }>("/billing/confirm", { method: "POST", body }),
  cancel: () => request<{ subscription: Subscription }>("/billing/cancel", { method: "POST" }),
  invoices: (query?: Paged) => request<Page<TaxInvoiceRecord>>("/billing/invoices", { query }),
  invoicePdfUrl: (id: string) => buildUrl(`/billing/invoices/${id}/pdf`),
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
  userLiveInterview: (id: string, sessionId: string) =>
    request<{ user: { id: string; email: string; name: string }; session: LiveInterviewSession }>(
      `/admin/users/${id}/live-interviews/${sessionId}`),
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
  payments: (query: Paged & { status?: string; q?: string }) =>
    request<Page<AdminPayment>>("/admin/payments", { query }),
  runs: (query: Paged & { status?: string }) => request<Page<AdminRun>>("/admin/automation-jobs", { query }),
  stopRun: (id: string) => request<AutomationRun>(`/admin/automation-jobs/${id}/stop`, { method: "POST" }),
  applications: (query: Paged & { status?: ApplicationStatus | ""; q?: string }) =>
    request<Page<AdminApplication>>("/admin/applications", { query }),
  companies: (query: Paged & { q?: string; sort?: string; filter?: "" | "applied" | "search" | "jobs" }) =>
    request<Page<AdminCompany>>("/admin/companies", { query }),
  company: (name: string) => request<AdminCompanyDetail>("/admin/companies/detail", { query: { name } }),
  enrichCompany: (name: string) =>
    request<AdminCompanyDetail>("/admin/companies/enrich", { method: "POST", query: { name } }),
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
    features: {
      applications: boolean;
      resume: boolean;
      mock_interview?: boolean;
      profile_sync?: boolean;
      outreach?: boolean;
    };
    mock_interview_presenter?: MockInterviewPresenterSettings;
    elevenlabs_api_key?: string;
    mock_interview_voice?: {
      provider: "elevenlabs" | "openai";
      elevenlabs_agent_id: string;
      elevenlabs_model_id: string;
    };
  }) => request<{ ai: AdminPlatformSettings["ai"] }>("/admin/settings/ai", { method: "PUT", body }),
  testAi: () => request<{ ok: boolean; reply: string }>("/admin/settings/ai/test", { method: "POST" }),
  testElevenLabs: (body?: { elevenlabs_api_key?: string }) =>
    request<{ ok: boolean; message: string; tier?: string }>("/admin/settings/ai/test-elevenlabs", {
      method: "POST",
      body: body ?? {},
    }),
  updatePayments: (body: {
    provider: "null" | "razorpay" | "stripe";
    key_id: string;
    key_secret?: string;
    webhook_secret?: string;
  }) => request<{ payments: AdminPlatformSettings["payments"] }>("/admin/settings/payments", { method: "PUT", body }),
  updateGst: (body: GstPlatformSettings) =>
    request<{ gst: GstPlatformSettings }>("/admin/settings/gst", { method: "PUT", body }),
  gstPreview: (query: { base_cents: number; buyer_state_code?: string }) =>
    request<GstPreviewTotals>("/admin/settings/gst/preview", { query }),
  taxInvoices: (query: Paged) => request<Page<TaxInvoiceRecord>>("/admin/billing/tax-invoices", { query }),
  testPayments: () =>
    request<{ ok: boolean; mode: string; test_checkout_hint?: string; message?: string }>(
      "/admin/settings/payments/test",
      { method: "POST" },
    ),
  syncRazorpayPlans: () =>
    request<{ created: { code: string; provider_plan_id: string }[] }>("/admin/settings/payments/sync-plans", { method: "POST" }),
  updateJobSources: (body: { linkedin: boolean; naukri: boolean }) =>
    request<{ job_sources: NonNullable<AdminPlatformSettings["job_sources"]> }>("/admin/settings/job-sources", { method: "PUT", body }),
  updateOutreach: (body: {
    firecrawl_api_key?: string;
    campaign?: Partial<OutreachCampaignSettings>;
    whatsapp_provider?: "bridge" | "cloud";
  }) =>
    request<{ outreach: NonNullable<AdminPlatformSettings["outreach"]> }>("/admin/settings/outreach", { method: "PUT", body }),
  testOutreach: (body?: { firecrawl_api_key?: string }) =>
    request<{ ok: boolean; message: string; remaining_credits?: number; plan_credits?: number }>(
      "/admin/settings/outreach/test",
      { method: "POST", body: body ?? {} },
    ),
  updateLiveInterview: (body: { enabled: boolean; display_name: string; price_cents: number }) =>
    request<{ live_interview: NonNullable<AdminPlatformSettings["live_interview"]> }>("/admin/settings/live-interview", { method: "PUT", body }),
  liveInterviews: () => request<{ sessions: LiveInterviewSession[] }>("/admin/live-interviews").then((d) => d.sessions),
  supportThreads: () => request<{ threads: SupportThread[] }>("/admin/support/threads").then((d) => d.threads),
  supportThread: (id: string) => request<{ thread: SupportThread; messages: SupportMessage[] }>(`/admin/support/threads/${id}`),
  supportReply: (id: string, body: string) =>
    request<{ message: SupportMessage }>(`/admin/support/threads/${id}/messages`, { method: "POST", body: { body } }),
  email: () => request<AdminEmailStatus>("/admin/email"),
  testEmail: (to: string) => request<TestEmailResult>("/admin/email/test", { method: "POST", body: { to: to || null } }),
  emailPreview: (body: { subject: string; body: string; html: string }) =>
    request<{ html: string; text: string }>("/admin/email/preview", { method: "POST", body }),
  verifyEmail: (id: string) => request<AdminUserDetail>(`/admin/users/${id}/verify-email`, { method: "POST" }),
  resendVerification: (id: string) =>
    request<AdminUserDetail>(`/admin/users/${id}/resend-verification`, { method: "POST" }),
  plans: () => request<{ plans: AdminPlan[] }>("/admin/plans").then((d) => d.plans),
  createPlan: (body: import("../types").PlanCreate) => request<AdminPlan>("/admin/plans", { method: "POST", body }),
  updatePlan: (code: string, body: PlanUpdate) => request<AdminPlan>(`/admin/plans/${code}`, { method: "PUT", body }),
  deletePlan: (code: string) => request<{ deleted: string }>(`/admin/plans/${code}`, { method: "DELETE" }),
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
  outreachStartScrape: (body: {
    query: string;
    location?: string;
    sources: string[];
    max_results: number;
    public_listing_attestation: boolean;
  }) =>
    request<OutreachScrapeJob>("/admin/outreach/scrape-jobs", {
      method: "POST",
      body,
      timeoutMs: OUTREACH_TIMEOUT_MS,
    }),
  outreachScrapeJobs: (query: Paged) =>
    request<Page<OutreachScrapeJob>>("/admin/outreach/scrape-jobs", { query }),
  outreachScrapeJob: (id: string) => request<OutreachScrapeJob>(`/admin/outreach/scrape-jobs/${id}`),
  payPayoutNow: (id: string, note?: string) =>
    request<PartnerPayout>(`/admin/payouts/${id}/pay`, { method: "POST", body: { note } }),
  outreachLeadStats: () => request<OutreachLeadDashboardStats>("/admin/outreach/leads/stats"),
  outreachLeads: (
    query: Paged & {
      job_id?: string;
      status?: string;
      source?: string;
      profile_complete?: boolean;
      q?: string;
    },
  ) => request<Page<OutreachLead>>("/admin/outreach/leads", { query }),
  outreachBulkImportLeads: (body: { contacts: string; enrich?: boolean }) =>
    request<OutreachBulkImportResult>("/admin/outreach/leads/bulk-import", {
      method: "POST",
      body,
    }),
  outreachBulkLeadAction: (body: { lead_ids: string[]; action: "complete" | "enhance" }) =>
    request<OutreachBulkActionResult>("/admin/outreach/leads/bulk-action", {
      method: "POST",
      body,
      timeoutMs: OUTREACH_TIMEOUT_MS,
    }),
  outreachLead: (id: string) => request<OutreachLead>(`/admin/outreach/leads/${id}`),
  outreachUpdateLead: (id: string, body: { payload: Record<string, unknown> }) =>
    request<OutreachLead>(`/admin/outreach/leads/${id}`, { method: "PATCH", body }),
  outreachCompleteProfile: (id: string) =>
    request<{ lead: OutreachLead; completion: OutreachProfileCompletion }>(
      `/admin/outreach/leads/${id}/complete-profile`,
      { method: "POST", timeoutMs: OUTREACH_TIMEOUT_MS },
    ),
  outreachGenerateProposal: (id: string) =>
    request<OutreachLead>(`/admin/outreach/leads/${id}/generate-proposal`, { method: "POST" }),
  outreachSend: (id: string, body: { channels: string[]; approve: boolean }) =>
    request<{ sent: Record<string, string>; lead: OutreachLead }>(`/admin/outreach/leads/${id}/send`, { method: "POST", body }),
  outreachConvert: (id: string) =>
    request<{ institute_id: string; email: string }>(`/admin/outreach/leads/${id}/convert`, { method: "POST" }),
  outreachWhatsappStatus: () => request<OutreachWhatsappStatus>("/admin/outreach/whatsapp/status"),
  outreachWhatsappReset: () =>
    request<OutreachWhatsappStatus & { reset: { ok?: boolean; error?: string } }>("/admin/outreach/whatsapp/reset", {
      method: "POST",
    }),
  outreachWhatsappRecentSends: (limit = 15) =>
    request<{ items: OutreachWhatsappRecentSend[] }>("/admin/outreach/whatsapp/recent-sends", { query: { limit } }),
  outreachWhatsappSyncChats: (query?: { limit?: number }) =>
    request<{
      synced: boolean;
      chats: number;
      messages_imported: number;
      leads_touched?: number;
      bridge_total?: number;
      reason?: string;
    }>("/admin/outreach/whatsapp/sync-chats", { method: "POST", query }),
  outreachWhatsappChatThreads: (query: Paged & { q?: string }) =>
    request<Page<OutreachWhatsappChatThread>>("/admin/outreach/whatsapp/chat-threads", { query }),
  outreachProposalImageInfo: () =>
    request<{ url: string; exists: boolean; updated_at: number | null }>("/admin/outreach/proposal-image"),
  outreachProposalImageUpload: (form: FormData) =>
    request<{ url: string }>("/admin/outreach/proposal-image", { method: "POST", form }),
  outreachWhatsappTestSend: (body: { phone: string; text: string }) =>
    request<{ sent: boolean; result: Record<string, unknown> }>("/admin/outreach/whatsapp/test-send", {
      method: "POST",
      body,
    }),
  outreachLeadChat: (id: string) =>
    request<{ items: OutreachLeadChatMessage[]; whatsapp_phone: string }>(`/admin/outreach/leads/${id}/chat`),
  outreachLeadChatSync: (id: string) =>
    request<{ imported: number; items: OutreachLeadChatMessage[]; whatsapp_phone: string }>(
      `/admin/outreach/leads/${id}/chat/sync`,
      { method: "POST" },
    ),
  outreachLeadChatSend: (id: string, body: { channel: string; text: string }) =>
    request<{ message: OutreachLeadChatMessage }>(`/admin/outreach/leads/${id}/chat`, {
      method: "POST",
      body,
    }),
  outreachLeadChatSendAttachment: (id: string, form: FormData) =>
    request<{ message: OutreachLeadChatMessage }>(`/admin/outreach/leads/${id}/chat/attachment`, {
      method: "POST",
      form,
    }),
};

export const institute = {
  me: () => request<{ institute: Institute; role: string }>("/institute/me"),
  dashboard: () => request<InstituteDashboard>("/institute/dashboard"),
  students: (query: Paged & { status?: string } = {}) => request<Page<InstituteAssignment>>("/institute/students", { query }),
  student: (id: string) => request<InstituteStudentDetail>(`/institute/students/${id}`),
  invite: (body: { name: string; phone: string; email: string; note?: string }) =>
    request<{ assignment: InstituteAssignment }>("/institute/students/invite", {
      method: "POST",
      body: { name: body.name, phone: body.phone, email: body.email, note: body.note || "" },
    }),
  release: (id: string) => request<{ assignment: InstituteAssignment }>(`/institute/students/${id}/release`, { method: "POST" }),
  suspend: (id: string) => request<{ assignment: InstituteAssignment }>(`/institute/students/${id}/suspend`, { method: "POST" }),
  invitations: () => request<{ items: InstituteAssignment[] }>("/institute/invitations"),
  seats: () => request<{ items: InstituteSeat[]; counts: SeatCounts }>("/institute/seats"),
  plans: () => request<{ plans: Plan[] }>("/institute/plans").then((d) => d.plans),
  subscription: () => request<{ subscription: Subscription | null; seats: SeatCounts }>("/institute/subscription"),
  checkout: (plan: string) => request<CheckoutResult>("/institute/subscription/checkout", { method: "POST", body: { plan } }),
  reports: () => request<{ seats: SeatCounts; assignments_by_status: Record<string, number> }>("/institute/reports"),
  profile: () => request<Institute>("/institute/profile"),
  saveProfile: (body: Partial<Institute>) => request<Institute>("/institute/profile", { method: "PUT", body }),
  saveSettings: (body: Record<string, unknown>) => request<Institute>("/institute/settings", { method: "PUT", body }),
  outreachStartScrape: (body: {
    query: string;
    location?: string;
    sources: string[];
    max_results: number;
    public_listing_attestation: boolean;
  }) => request<OutreachScrapeJob>("/institute/outreach/scrape-jobs", { method: "POST", body, timeoutMs: OUTREACH_TIMEOUT_MS }),
  outreachScrapeJobs: (query: Paged) => request<Page<OutreachScrapeJob>>("/institute/outreach/scrape-jobs", { query }),
  outreachScrapeJob: (id: string) => request<OutreachScrapeJob>(`/institute/outreach/scrape-jobs/${id}`),
  outreachLeads: (query: Paged & { job_id?: string; status?: string; q?: string } = {}) =>
    request<Page<OutreachLead>>("/institute/outreach/leads", { query }),
  outreachLead: (id: string) => request<OutreachLead>(`/institute/outreach/leads/${id}`),
  outreachLeadChat: (id: string) => request<{ items: OutreachLeadMessage[]; whatsapp_phone: string }>(`/institute/outreach/leads/${id}/chat`),
  outreachLeadChatSend: (id: string, text: string) =>
    request<unknown>(`/institute/outreach/leads/${id}/chat`, { method: "POST", body: { channel: "whatsapp", text } }),
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
  addKyc: (file: File, note = "") => {
    const form = new FormData();
    form.append("file", file);
    form.append("note", note);
    return request<Partner>("/partner/kyc", { method: "POST", form });
  },
  saveTax: (body: Partial<Partner>) => request<Partner>("/partner/tax", { method: "PUT", body }),
};

export const invites = {
  preview: (token: string) => request<{ institute_name: string; email: string; status: string; expires_at: string }>(`/invites/${token}`),
  accept: (token: string) => request<{ assignment: InstituteAssignment }>(`/invites/${token}/accept`, { method: "POST" }),
};

export const referrals = {
  capture: (code: string, campaign?: string) =>
    request<{ referral_code: string; organization: string; redirect: string; kind?: string }>(`/r/${code}`, { query: { c: campaign } }),
  me: () =>
    request<{ referral_code: string; referral_path: string; attributed: number; converted: number }>("/referrals/me"),
};
