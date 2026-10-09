export type Workspace = "app" | "admin" | "institute" | "partner";

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_verified: boolean;
  is_admin: boolean;
  created_at: string;
  last_login_at: string | null;
  workspace?: Workspace;
  institute_id?: string | null;
  partner_id?: string | null;
  institute_status?: string | null;
  partner_status?: string | null;
}

export interface EducationEntry {
  school: string;
  degree: string;
  field: string;
  start_year: string;
  end_year: string;
}

export interface WorkEntry {
  title: string;
  company: string;
  location: string;
  start: string;
  end: string;
  summary: string;
}

export interface Profile {
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  headline: string | null;
  summary: string | null;
  current_title: string | null;
  current_company: string | null;
  experience_years: number | null;
  skills: string[];
  preferred_roles: string[];
  preferred_locations: string[];
  preferred_resume_template: string;
  education: EducationEntry[];
  work_history: WorkEntry[];
}

export interface ResumeTemplate {
  id: string;
  name: string;
  description: string;
  accent: string;
  body_font: string;
  heading_font: string;
  layout: string;
  layout_label: string;
}

export type ProfileInput = Omit<Profile, "email">;

export interface SearchConfig {
  keywords: string[];
  location: string;
  easy_apply_only: boolean;
  experience_level: string[];
  job_type: string[];
  on_site: string[];
  companies: string[];
  date_posted: string;
  sort_by: string;
  salary_min: number | null;
  salary_max: number | null;
  extra: Record<string, unknown>;
}

export interface SearchConfigOut extends SearchConfig {
  configured: boolean;
  updated_at: string | null;
}

export type FieldType = "text" | "textarea" | "password" | "number" | "bool" | "select" | "list";

export interface FieldMeta {
  key: string;
  label: string;
  type: FieldType;
  help: string;
  section: string;
  advanced: boolean;
  options?: string[];
}

export interface PreferenceOptions {
  search: {
    experience_level: string[];
    job_type: string[];
    on_site: string[];
    date_posted: string[];
    sort_by: string[];
    extra_fields: FieldMeta[];
  };
  application_fields: FieldMeta[];
}

export type Answers = Record<string, string | number | boolean | string[]>;

export interface Resume {
  id: string;
  name: string;
  filename: string;
  file_type: "pdf" | "docx";
  file_size: number;
  is_default: boolean;
  created_at: string;
  master_skills?: string[] | null;
  subskills_by_master?: Record<string, string[]> | null;
  ai_metadata?: Record<string, unknown> | null;
}

export interface ResumeAiPreview {
  gate_passed: boolean;
  match_score: number;
  missing_keywords: string[];
  fit_score: number | null;
  validation_warnings?: string[];
  patch?: Record<string, unknown> | null;
  disclaimer?: string;
}

export type ResumeTextExtraction = "pdf_text" | "ocr" | "pdf_text+ocr" | "docx";

export interface ResumeIntake {
  source: "ai" | "heuristic";
  text_extraction: ResumeTextExtraction;
  profile: Profile;
  cover_letter: string | null;
  master_skills_count: number;
  resume_id: string;
}

export type ApplicationStatus =
  | "discovered" | "queued" | "running" | "applied" | "failed" | "skipped" | "external" | "cancelled";

export const APPLICATION_STATUSES: ApplicationStatus[] = [
  "applied", "failed", "skipped", "external", "queued", "running", "discovered", "cancelled",
];

export interface JobSummary {
  id: string;
  platform: string;
  external_id: string;
  title: string;
  company: string;
  location: string;
  job_url: string;
  work_setting: string;
  employment_type: string;
  experience_level: string;
  salary_min: number | null;
  salary_max: number | null;
  discovered_at: string;
}

export interface JobDetail extends JobSummary {
  description: string;
}

export interface ResumeVersion {
  id: string;
  name: string;
  filename: string;
  file_type: string;
  created_at: string;
  is_default?: boolean;
  generated_by?: string | null;
}

export interface Application {
  id: string;
  status: ApplicationStatus;
  applied_at: string | null;
  failure_reason: string;
  resume_id: string | null;
  automation_job_id: string | null;
  created_at: string;
  updated_at: string;
  job: JobSummary;
  resume?: ResumeVersion | null;
  generated_resumes?: ResumeVersion[];
}

export interface ApplicationDetail extends Application {
  job: JobDetail;
}

export interface ApplicationBrief {
  id: string;
  status: ApplicationStatus;
  applied_at: string | null;
}

export interface JobWithApplication extends JobSummary {
  application: ApplicationBrief;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Usage {
  plan: string;
  plan_name: string;
  period: string;
  resets_at: string;
  applications: { used: number; limit: number; remaining: number };
  resumes: { used: number; limit: number; remaining: number };
  jobs_discovered: number;
  runtime_seconds: number;
  limit_reached: boolean;
}

export type RunStatus = "queued" | "running" | "paused" | "completed" | "failed" | "cancelled";

export interface AutomationRun {
  id: string;
  status: RunStatus;
  control: "run" | "pause" | "stop";
  dry_run: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  current_job: string;
  total_jobs: number;
  successful_count: number;
  failed_count: number;
  skipped_count: number;
  error_message: string;
  stop_reason: "" | "user" | "plan_limit" | "admin";
  claimed: boolean;
}

export interface AgentDevice {
  id: string;
  name: string;
  platform: string;
  agent_version: string;
  paired_at: string | null;
  last_seen_at: string | null;
  online: boolean;
}

export type ResumeRunMode = "default" | "tailor_if_gate";

export interface ResumeTailorOverview {
  mode: ResumeRunMode;
  resume_ai_available: boolean;
  master_skills_ready: boolean;
  can_tailor: boolean;
}

export interface AutomationOverview {
  active: AutomationRun | null;
  recent: AutomationRun[];
  devices: AgentDevice[];
  agent_online: boolean;
  readiness: { ready: boolean; problems: string[] };
  usage: Usage;
  resume_tailor?: ResumeTailorOverview;
}

export interface RunLogLine {
  seq: number;
  ts: string;
  level: "info" | "warning" | "error";
  event: string;
  message: string;
}

export interface DashboardStats {
  applications_by_status: Record<ApplicationStatus, number>;
  total_applied: number;
  applied_today: number;
  success_rate: number | null;
  daily: { date: string; applied: number; failed: number }[];
  top_companies: { company: string; applied: number }[];
  recent_applications: Application[];
  automation: { active: AutomationRun | null; last: AutomationRun | null };
  usage: Usage;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  link: string;
  read_at: string | null;
  created_at: string;
}

export type PlanKind = "personal" | "institute";

export interface Plan {
  code: string;
  name: string;
  price_cents: number;
  currency: string;
  interval: string;
  kind?: PlanKind;
  limits: { applications_per_month: number; resumes: number; seats?: number };
}

export type SubscriptionStatus = "pending" | "trialing" | "active" | "past_due" | "cancelled" | "expired";

export interface Subscription {
  id: string;
  plan: Omit<Plan, "limits">;
  status: SubscriptionStatus;
  provider: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  created_at: string;
}

export interface PaymentRecord {
  id: string;
  amount_cents: number;
  currency: string;
  status: string;
  method: string;
  description: string;
  paid_at: string | null;
}

export interface BillingOverview {
  provider: string;
  checkout_available?: boolean;
  razorpay_mode?: "test" | "live" | "unknown" | null;
  checkout_live?: boolean;
  subscription: Subscription | null;
  pending: Subscription | null;
  usage: Usage;
  payments: PaymentRecord[];
}

export interface CheckoutOptions {
  key: string;
  subscription_id: string;
  name: string;
  description: string;
  currency?: string;
  prefill: { email: string; name: string };
  theme?: { color: string };
  modal?: { confirm_close?: boolean; escape?: boolean };
  razorpay_mode?: "test" | "live";
  test_hint?: string;
}

export interface CheckoutResult {
  subscription: Subscription;
  checkout: CheckoutOptions | null;
  replaces: Subscription | null;
}

// ------------------------------------------------------------------------------------------ admin
export interface AdminAnalytics {
  users: { total: number; active: number; verified: number; admins: number; new_7d: number; new_30d: number; active_30d: number };
  subscriptions: { by_plan: { code: string; name: string; count: number }[]; mrr_cents: Record<string, number>; past_due: number };
  revenue_30d_cents: Record<string, number>;
  applications: { this_month_by_status: Record<ApplicationStatus, number>; daily: { date: string; applied: number; failed: number }[] };
  automation: { active_runs: number; last_24h_by_status: Record<RunStatus, number>; devices: number; devices_online: number };
}

export interface AdminUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_verified: boolean;
  is_admin: boolean;
  created_at: string;
  last_login_at: string | null;
  plan: string;
  plan_name: string;
  applications_this_month: number;
}

export interface AdminUserDetail {
  user: AdminUser;
  usage: Usage;
  subscription: Subscription | null;
  subscriptions: Subscription[];
  payments: PaymentRecord[];
  runs: AutomationRun[];
  devices: AgentDevice[];
  applications_by_status: Record<ApplicationStatus, number>;
  resumes: number;
}

export interface WithOwner {
  user_id: string;
  user_email: string;
}

export type AdminSubscription = Subscription & WithOwner;
export type AdminRun = AutomationRun & WithOwner & { device: string };

export interface AdminApplication extends WithOwner {
  id: string;
  status: ApplicationStatus;
  applied_at: string | null;
  updated_at: string | null;
  failure_reason: string;
  job: { title: string; company: string; location: string; job_url: string };
}

export type LogLevel = "info" | "warning" | "error";

export interface AdminLogLine extends WithOwner {
  ts: string;
  level: LogLevel;
  event: string;
  message: string;
  run_id: string;
}

export interface AdminAuditEntry {
  id: string;
  created_at: string;
  admin_email: string;
  action: string;
  target: string;
  target_user_id: string | null;
  details: Record<string, unknown>;
}

export interface AdminWorkers {
  celery: { broker: "ok" | "unreachable"; workers: string[] };
  devices: (AgentDevice & WithOwner & { running: boolean })[];
}

export interface AdminEmailStatus {
  mode: "smtp" | "console";
  host: string;
  port: number;
  security: "ssl" | "starttls";
  from: string;
  authenticated: boolean;
  require_verification: boolean;
  verification_hours: number;
  frontend_url: string;
  unverified_users: number;
}

export interface TestEmailResult {
  delivered: boolean;
  mode: "smtp" | "console";
  error: string;
}

export interface PlatformCms {
  branding: {
    app_name: string;
    contact_email: string;
    footer_line: string;
    social_links: { twitter: string; linkedin: string; github: string };
  };
  banner: { enabled: boolean; message: string; tone: "info" | "warning" | "success" };
  landing: {
    hero_badge: string;
    hero_title: string;
    hero_subtitle: string;
    hero_cta_primary: string;
    hero_cta_secondary: string;
    hero_footnote: string;
    features_heading: string;
    features: { icon: string; title: string; text: string }[];
    steps_heading: string;
    steps: { title: string; text: string }[];
    pricing_heading: string;
    pricing_subtitle: string;
    faq_heading: string;
    faq: { question: string; answer: string }[];
    faq_contact_line: string;
  };
  legal: { privacy_md: string; terms_md: string; refund_md: string };
}

export interface AdminPlatformSettings {
  cms: PlatformCms;
  smtp: {
    enabled: boolean;
    host: string;
    port: number;
    security: "ssl" | "starttls";
    username: string;
    from_address: string;
    password_configured: boolean;
    mode: "smtp" | "console";
    source: "database" | "environment";
  };
  auth_email: {
    require_verification: boolean;
    verification_hours: number;
    password_reset_minutes: number;
    frontend_url: string;
  };
  notifications: Record<string, { email: boolean; label: string; description: string }>;
  infrastructure: {
    app_env: string;
    app_version: string;
    database: string;
    redis_url_set: boolean;
    cors_origins: string[];
    payment_provider: string;
    payment_keys_configured: boolean;
  };
  ai: {
    enabled: boolean;
    provider: string;
    base_url: string;
    api_key_configured: boolean;
    models: { fast: string; strong: string; embedding: string };
    features: { applications: boolean; resume: boolean };
    ready: boolean;
  };
  payments: {
    provider: "null" | "razorpay";
    key_id: string;
    key_secret_configured: boolean;
    webhook_secret_configured: boolean;
    ready: boolean;
    source: "database" | "environment";
    razorpay_mode: "test" | "live" | "unknown";
    live_checkout: boolean;
    test_checkout: boolean;
  };
  unverified_users: number;
}

export type HumanQuestionMatch = "contains" | "exact";

export interface HumanQuestion {
  id: string;
  match: HumanQuestionMatch;
  pattern: string;
  answer: string;
  field_types: string[];
  locked?: boolean;
}

export interface PendingFormQuestion {
  id: string;
  label: string;
  question_type: string;
  options: string[];
  job_id?: string;
  job_title?: string;
  company?: string;
  needs_answer: boolean;
  has_saved_rule?: boolean;
  times_seen?: number;
  first_seen_at?: string;
  last_seen_at?: string;
}

export interface ApplicationPreferencesOut {
  answers: Record<string, unknown>;
  human_questions: HumanQuestion[];
  pending_form_questions: PendingFormQuestion[];
  ai_applications_enabled: boolean;
  user_information_all: string;
  ai_policy: { deny_label_contains: string[] };
  ai_available: boolean;
}

export type PublicSite = Pick<PlatformCms, "branding" | "banner" | "landing" | "legal">;

export interface AdminPlan extends Plan {
  is_active: boolean;
  sort_order: number;
  provider_plan_id: string;
  subscribers: number;
}

export interface PlanUpdate {
  name: string;
  price_cents: number;
  applications_per_month: number;
  resumes: number;
  seats?: number;
  is_active: boolean;
  sort_order: number;
}

export interface SeatCounts {
  total: number;
  available: number;
  assigned: number;
  by_status: Record<string, number>;
}

export interface InstituteSettings {
  timezone: string;
  notify_invites: boolean;
  notify_acceptances: boolean;
  notify_low_seats: boolean;
  low_seat_threshold: number;
  invite_expiry_days: number;
  invite_note: string;
}

export interface Institute {
  id: string;
  name: string;
  email: string;
  contact_name: string;
  phone: string;
  institute_type: string;
  gstin: string;
  pan_number: string;
  status: string;
  partner_id: string | null;
  source: string;
  settings: InstituteSettings | Record<string, unknown>;
  seats: SeatCounts;
  created_at: string;
}

export interface InstituteSeat {
  id: string;
  subscription_id: string;
  status: string;
  created_at: string;
}

export interface InstituteLogin {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_verified: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export interface InstituteMember {
  id: string;
  user_id: string;
  email: string;
  name: string;
  role: string;
  status: string;
}

export interface InstitutePartnerBrief {
  id: string;
  organization: string;
  referral_code: string;
  status: string;
  kyc_status: string;
}

export interface AdminInstituteDetail {
  institute: Institute;
  dashboard: InstituteDashboard;
  login: InstituteLogin | null;
  partner: InstitutePartnerBrief | null;
  subscription: Subscription | null;
  subscriptions: Subscription[];
  payments: PaymentRecord[];
  students: InstituteAssignment[];
  invitations: InstituteAssignment[];
  seats: { counts: SeatCounts; items: InstituteSeat[] };
  reports: { seats: SeatCounts; assignments_by_status: Record<string, number> };
  members: InstituteMember[];
  commissions: PartnerCommission[];
}

export interface InstituteAssignment {
  id: string;
  candidate_email: string;
  student_user_id: string | null;
  seat_id: string | null;
  status: string;
  note: string;
  accepted_at: string | null;
  released_at: string | null;
  created_at: string;
}

export interface Partner {
  id: string;
  user_id: string;
  organization: string;
  contact_name: string;
  phone: string;
  referral_code: string;
  status: string;
  kyc_status: string;
  commission_mode: string;
  commission_bps: number;
  commission_flat_cents: number;
  gstin: string;
  pan_number: string;
  payout_account: string;
  payout_ifsc: string;
  kyc_documents: { filename: string; note: string; uploaded_at: string }[];
  click_count: number;
  wallet: { accrued_cents: number; approved_cents: number; available_cents: number };
  created_at: string;
}

export interface PartnerCommission {
  id: string;
  institute_id: string | null;
  institute_name?: string | null;
  amount_cents: number;
  currency: string;
  commission_mode?: string;
  rate_bps: number;
  rate_flat_cents?: number;
  status: string;
  note: string;
  created_at: string;
}

export interface PartnerPayout {
  id: string;
  amount_cents: number;
  currency: string;
  status: string;
  note: string;
  processed_at: string | null;
  created_at: string;
}

export interface PartnerCampaign {
  id: string;
  name: string;
  code: string;
  click_count: number;
  note: string;
  path: string;
  created_at: string;
}

export interface InstituteDashboard {
  institute: Institute;
  subscription: Subscription | null;
  students: number;
  pending_invites: number;
  seats: SeatCounts;
  recent_assignments: InstituteAssignment[];
}

export interface PartnerDashboard {
  partner: Partner;
  institutes: number;
  recent_institutes: Institute[];
  recent_commissions: PartnerCommission[];
  referral_path: string;
}

export interface AdminPartnerDetail extends PartnerDashboard {
  login: InstituteLogin | null;
  institute_list: Institute[];
  commissions: PartnerCommission[];
  payouts: PartnerPayout[];
  campaigns: PartnerCampaign[];
  reports: {
    institutes_by_status: Record<string, number>;
    commissions_by_status: Record<string, number>;
    payouts_by_status: Record<string, number>;
  };
}
