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
  totp_enabled?: boolean;
  /** True when an active campus seat supplies the plan; personal billing is locked. */
  institute_managed?: boolean;
  institute_name?: string | null;
  referral_code?: string | null;
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

export interface ProfileCompletion {
  percent: number;
  missing: { section: string; label: string; hint?: string; ai?: boolean }[];
  weights: Record<string, number>;
}

export interface MasterProfileSections {
  personal: Record<string, unknown>;
  professional: Record<string, unknown>;
  education_extended: Record<string, unknown>;
  employment_extended: Record<string, unknown>;
  skills: Record<string, unknown>[];
  projects: Record<string, unknown>[];
  accomplishments: Record<string, unknown>;
  career: Record<string, unknown>;
  diversity: Record<string, unknown>;
  common_answers: CommonApplicationAnswer[];
}

export interface CommonApplicationAnswer {
  id: string;
  key: string;
  question: string;
  answer: string;
  answer_type: string;
  category?: string;
  verified?: boolean;
  profile_field?: string;
  created_at?: string;
  updated_at?: string | null;
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
  master?: MasterProfileSections;
  photo_url?: string | null;
  updated_at?: string | null;
  completion?: ProfileCompletion;
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
  profile_answer_fields?: FieldMeta[];
  run_settings_fields?: FieldMeta[];
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

/** Contact details the employer published on the job posting (not your personal data). */
export interface PublishedContact {
  name?: string;
  email?: string;
  phone?: string;
  role?: string;
  link?: string;
}

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
  published_contacts?: PublishedContact[];
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
  job_title?: string | null;
  company?: string | null;
  match_score?: number | null;
  fit_score?: number | null;
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
  resumes: { used: number; limit: number; remaining: number; unlimited?: boolean };
  mock_interviews?: { used: number; limit: number; remaining: number; unlimited?: boolean };
  jobs_discovered: number;
  runtime_seconds: number;
  limit_reached: boolean;
}

export type RunStatus = "queued" | "running" | "paused" | "completed" | "failed" | "cancelled";

export type AutomationRunKind = "job_apply" | "linkedin_profile_sync";

export interface AutomationRun {
  id: string;
  status: RunStatus;
  control: "run" | "pause" | "stop";
  dry_run: boolean;
  run_kind?: AutomationRunKind;
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
  sources: Array<"linkedin" | "naukri">;
  switch_after: number | null;
  active_source: "linkedin" | "naukri";
  source_submitted: number;
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

export interface DesktopAgentInfo {
  available: boolean;
  filename: string | null;
  size_bytes: number | null;
  zip?: { filename: string; size_bytes: number } | null;
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
  enabled_sources?: Array<"linkedin" | "naukri">;
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
  mock_interviews?: MockInterviewDashboardStats;
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
  limits: {
    applications_per_month: number;
    mock_interviews_per_month: number;
    resumes: number;
    resumes_unlimited?: boolean;
    seats?: number;
  };
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
  managed_by_institute?: boolean;
  institute_name?: string | null;
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
  provider?: string;
  url?: string;
  session_id?: string;
  publishable_key?: string;
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
  signups_daily?: { date: string; applied: number; failed: number }[];
  revenue_daily?: { date: string; applied: number; failed: number }[];
  automation: { active_runs: number; last_24h_by_status: Record<RunStatus, number>; devices: number; devices_online: number };
  mock_interviews: {
    total_sessions: number;
    this_month: number;
    by_status: Record<MockInterviewSessionStatus, number>;
    failed_feedback_jobs_24h: number;
    average_score?: number | null;
    scored_sessions?: number;
    daily?: { date: string; applied: number; failed: number }[];
  };
  live_interviews?: {
    total_sessions: number;
    this_month: number;
    by_status: Record<string, number>;
  };
}

export interface MockInterviewPresenterSettings {
  mode: "digital_human_3d" | "static_photo" | "live_stream";
  image_url: string;
  glb_url?: string;
  live_stream_url?: string;
  supports_barge_in?: boolean;
  supports_replay?: boolean;
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
  candidate?: AdminCandidate;
}

export interface AdminCandidate {
  profile: {
    phone: string;
    headline: string;
    summary: string;
    current_title: string;
    current_company: string;
    experience_years: number | null;
    skills: string[];
    preferred_roles: string[];
    preferred_locations: string[];
    education: Record<string, unknown>[];
    work_history: Record<string, unknown>[];
  };
  search: {
    keywords: string[];
    location: string;
    easy_apply_only: boolean;
    experience_level: string[];
    job_type: string[];
    on_site: string[];
    date_posted: string;
    salary_min: number | null;
    salary_max: number | null;
  } | null;
  resume_list: { id: string; name: string; file_type: string; file_size: number; is_default: boolean; tailored: boolean; created_at: string | null }[];
  stats: {
    applications_total: number;
    applied_total: number;
    success_rate: number | null;
    mock_interviews_total: number;
    mock_average_score: number | null;
    live_interviews_total: number;
    live_average_score: number | null;
  };
  applications_daily: { date: string; applied: number; failed: number }[];
  recent_applications: {
    id: string; status: ApplicationStatus; title: string; company: string; location: string; job_url: string;
    failure_reason: string; applied_at: string | null; created_at: string | null;
  }[];
  mock_interviews: {
    id: string; status: MockInterviewSessionStatus; job_title: string; company: string; interview_types: string[];
    turn_count: number; overall_score: number | null; created_at: string | null;
  }[];
  live_interviews: {
    id: string; status: string; job_title: string; company: string; token: string; token_status: string;
    overall_score: number | null; lines: number; started_at: string | null; ended_at: string | null;
  }[];
  live_tokens: { unused: number; reserved: number; used: number; paid: { currency: string; amount_cents: number }[] };
  journey?: {
    steps: { key: string; label: string; done: boolean; at: string | null; optional: boolean }[];
    stopped_at: string | null;
    stopped_label: string | null;
    stopped_step: number | null;
    completed: number;
    total: number;
    last_activity_at: string | null;
  };
}

export interface WithOwner {
  user_id: string;
  user_email: string;
}

export type AdminPayment = PaymentRecord & WithOwner & { provider: string };
export type AdminSubscription = Subscription & WithOwner;
export type AdminRun = AutomationRun & WithOwner & { device: string };

export interface AdminCompany {
  company: string;
  users: number;
  user_emails: string[];
  jobs: number;
  applied: number;
  search_filters: number;
  last_seen: string | null;
}

export interface AdminCompanyJob {
  id: string;
  title: string;
  location: string;
  job_url: string;
  platform?: string;
  discovered_at?: string | null;
  applied: number;
  other: number;
  users: number;
  last_seen: string | null;
}

export interface AdminCompanyContact {
  name: string;
  email: string;
  phone: string;
  role: string;
  link: string;
  jobs: { title: string; job_url: string }[];
  origin?: "posting" | "web" | "both";
  sources?: { url: string; title?: string }[];
}

export interface AdminCompanyProfiling {
  status: "idle" | "running" | "ready" | "failed";
  last_enriched_at: string | null;
  error: string;
  sources_scraped: number;
}

export interface AdminCompanyExternalJobLink {
  url: string;
  title?: string;
  source_url?: string;
  known_in_app?: boolean;
}

export interface AdminCompanySourcePage {
  url: string;
  title?: string;
}

export interface AdminCompanyApplication {
  id: string;
  status: ApplicationStatus;
  applied_at: string | null;
  updated_at: string | null;
  failure_reason: string;
  user_id: string;
  user_email: string;
  job: {
    id: string;
    title: string;
    location: string;
    job_url: string;
    platform?: string;
  };
}

export interface AdminCompanyCandidate {
  user_id: string;
  user_email: string;
  applications: number;
  applied: number;
  in_search_filter: boolean;
  last_seen: string | null;
}

export interface AdminCompanyDetail {
  company: string;
  users: number;
  jobs: number;
  applied: number;
  search_filters: number;
  locations: string[];
  last_seen: string | null;
  applicant_emails?: string[];
  search_filter_emails?: string[];
  status_breakdown?: Record<string, number>;
  applications?: AdminCompanyApplication[];
  applications_total?: number;
  candidates?: AdminCompanyCandidate[];
  contact_stats?: { total: number; from_postings: number; from_web: number };
  job_list: AdminCompanyJob[];
  contacts: AdminCompanyContact[];
  profiling?: AdminCompanyProfiling;
  source_pages?: AdminCompanySourcePage[];
  external_job_links?: AdminCompanyExternalJobLink[];
}

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

export type SeoPageKey = "home" | "login" | "register" | "privacy" | "terms" | "refund";

export interface SeoPageMeta {
  title: string;
  description: string;
  noindex: boolean;
}

export interface SiteSeoSettings {
  site_url: string;
  default_title: string;
  title_suffix: string;
  default_description: string;
  default_keywords: string;
  og_image_url: string;
  twitter_card: "summary" | "summary_large_image";
  robots_index: boolean;
  robots_disallow: string[];
  google_site_verification: string;
  bing_site_verification: string;
  pages: Record<SeoPageKey, SeoPageMeta>;
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
  seo: SiteSeoSettings;
}

export interface AuthEmailTemplate {
  subject: string;
  body: string;
  html: string;
  /** Institute outreach WhatsApp copy (institute_proposal only). */
  whatsapp?: string;
}

export interface EventNotificationTemplate {
  in_app_title: string;
  in_app_body: string;
  email_subject: string;
  email_body: string;
  email_html: string;
}

export interface EmailTemplates {
  auth: Record<string, AuthEmailTemplate>;
  events: Record<string, EventNotificationTemplate>;
}

export interface NotificationPreferences {
  types: Record<string, { email: boolean; label: string; description: string }>;
}

export interface OutreachCampaignSettings {
  keywords: string[];
  cities: string[];
  sources: string[];
  max_results: number;
  rotation_index: number;
  public_listing_attestation: boolean;
  last_outreach_send_at: string | null;
  next_outreach_send_at: string | null;
  send_interval_min_sec: number;
  send_interval_max_sec: number;
}

export interface OutreachPlatformSettings {
  firecrawl_api_key_configured: boolean;
  source: "database" | "environment" | "none" | string;
  campaign?: OutreachCampaignSettings;
  automation_enabled?: boolean;
  whatsapp_provider?: "bridge" | "cloud";
  whatsapp_cloud_configured?: boolean;
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
  email_templates: EmailTemplates;
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
    features: {
      applications: boolean;
      resume: boolean;
      mock_interview?: boolean;
      profile_sync?: boolean;
      outreach?: boolean;
    };
    ready: boolean;
    resume_ready?: boolean;
    mock_interview_ready?: boolean;
    outreach_ready?: boolean;
    mock_interview_presenter?: MockInterviewPresenterSettings;
    elevenlabs_api_key_configured?: boolean;
    elevenlabs_api_key_source?: "database" | "environment" | "none";
    mock_interview_voice?: {
      provider: "elevenlabs" | "openai";
      elevenlabs_agent_id: string;
      elevenlabs_model_id: string;
    };
  };
  payments: {
    provider: "null" | "razorpay" | "stripe";
    key_id: string;
    key_secret_configured: boolean;
    webhook_secret_configured: boolean;
    ready: boolean;
    source: "database" | "environment";
    razorpay_mode: "test" | "live" | "unknown";
    live_checkout: boolean;
    test_checkout: boolean;
  };
  gst: GstPlatformSettings;
  live_interview?: {
    enabled: boolean;
    display_name: string;
    price_cents: number;
    currency: string;
  };
  job_sources?: {
    linkedin: boolean;
    naukri: boolean;
  };
  outreach?: OutreachPlatformSettings;
  unverified_users: number;
}

export interface GstPlatformSettings {
  enabled: boolean;
  legal_name: string;
  trade_name: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  state_code: string;
  pin: string;
  country: string;
  gstin: string;
  pan: string;
  sac_code: string;
  rate_percent: number;
  pricing_tax_exclusive: boolean;
  invoice_prefix: string;
  invoice_next_number: number;
  invoice_footer_note: string;
  configured?: boolean;
}

export interface GstPreviewTotals {
  base_cents: number;
  rate_percent: number;
  supplier_state_code: string;
  buyer_state_code: string;
  taxable_cents: number;
  cgst_cents: number;
  sgst_cents: number;
  igst_cents: number;
  total_cents: number;
}

export interface TaxInvoiceRecord {
  id: string;
  payment_id: string | null;
  user_id: string;
  invoice_number: string;
  status: string;
  issued_at: string | null;
  taxable_cents: number;
  cgst_cents: number;
  sgst_cents: number;
  igst_cents: number;
  total_cents: number;
  currency: string;
  created_at: string | null;
}

export interface SupportMessage {
  id: string;
  sender: "user" | "admin" | "system";
  kind: "text" | "payment_link" | "token";
  body: string;
  meta: { url?: string; token?: string; amount_cents?: number; token_status?: "unused" | "reserved" | "used" };
  created_at: string | null;
}

export interface SupportThread {
  id: string;
  user_id: string;
  email: string;
  name: string;
  last_message_at: string | null;
}

export interface LiveInterviewTurn {
  role: "interviewer" | "candidate" | "suggestion";
  text: string;
  at?: string;
}

export interface LiveInterviewReport {
  overall_score?: number | null;
  summary?: string;
  knowledge_summary?: string;
  rubric_version?: number;
  rubric_overall?: number;
  rubric_scores?: MockInterviewRubricScore[];
  rubric_categories?: MockInterviewRubricCategory[];
  dimensions?: { key?: string; label?: string; score?: number; notes?: string }[];
  strengths?: string[];
  suggestions?: string[];
  question_breakdown?: { question?: string; answer_quality?: string; notes?: string }[];
  sample_answers?: { question?: string; suggestion?: string }[];
}

export interface LiveInterviewSession {
  id: string;
  status: "active" | "completed";
  job_title: string;
  company: string;
  application_id: string | null;
  token?: string;
  transcript: LiveInterviewTurn[];
  feedback: LiveInterviewReport | null;
  started_at: string | null;
  ended_at: string | null;
  email?: string;
  token_status?: string;
}

export type HumanQuestionMatch = "contains" | "exact";

export interface HumanQuestion {
  id: string;
  match: HumanQuestionMatch;
  pattern: string;
  answer: string;
  field_types: string[];
  locked?: boolean;
  normalized_pattern?: string;
  input_type?: string;
  verified?: boolean;
  company?: string;
  job_title?: string;
  usage_count?: number;
  created_at?: string;
  updated_at?: string | null;
  last_used_at?: string | null;
}

export interface CustomQuestionsList {
  items: HumanQuestion[];
  total: number;
}

export interface AutomationSettingsOut {
  values: Record<string, unknown>;
  fields: FieldMeta[];
  defaults: Record<string, unknown>;
  warnings: string[];
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

export type PublicSite = Pick<PlatformCms, "branding" | "banner" | "landing" | "legal" | "seo">;

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
  mock_interviews_per_month: number;
  resumes_per_month: number;
  seats?: number;
  is_active: boolean;
  sort_order: number;
}

export interface PlanCreate extends PlanUpdate {
  code: string;
  kind: PlanKind;
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
  assignment?: InstituteAssignment | null;
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
  candidate_name?: string | null;
  candidate_phone?: string | null;
  student_user_id: string | null;
  seat_id: string | null;
  status: string;
  note: string;
  accepted_at: string | null;
  released_at: string | null;
  created_at: string;
  expires_at?: string | null;
  activity?: Pick<InstituteStudentActivity, "searched" | "applied" | "skipped" | "failed">;
}

export interface InstituteStudentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_verified: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export interface InstituteStudentDetail {
  assignment: InstituteAssignment;
  user: InstituteStudentUser | null;
  activity: {
    searched: number;
    applied: number;
    skipped: number;
    failed: number;
    success_rate: number | null;
  };
  applications_by_status: Record<string, number>;
  candidate: AdminCandidate | null;
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
  kyc_documents: { id?: string; filename: string; note: string; uploaded_at: string }[];
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

export interface InstituteStudentActivity {
  searched: number;
  applied: number;
  skipped: number;
  failed: number;
  success_rate: number | null;
  daily: { date: string; applied: number; failed: number }[];
}

export interface InstituteDashboard {
  institute: Institute;
  subscription: Subscription | null;
  students: number;
  pending_invites: number;
  seats: SeatCounts;
  activity: InstituteStudentActivity;
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

export type InterviewType = "behavioral" | "technical" | "hr" | "mixed";
export type MockInterviewSessionStatus = "active" | "completed" | "abandoned";
export type MockInterviewMessageRole = "interviewer" | "candidate";

export interface MockInterviewDashboardStats {
  total: number;
  by_status: Record<MockInterviewSessionStatus, number>;
  average_score: number | null;
  best_score: number | null;
  completed_with_score: number;
  recent: {
    id: string;
    status: MockInterviewSessionStatus;
    turn_count: number;
    overall_score: number | null;
    job_title: string;
    company: string;
    created_at: string;
  }[];
}

export interface MockInterviewMessage {
  id: string;
  role: MockInterviewMessageRole;
  content: string;
  meta?: Record<string, unknown> | null;
  created_at: string;
}

export interface MockInterviewSessionSummary {
  id: string;
  application_id: string;
  interview_types: InterviewType[];
  status: MockInterviewSessionStatus;
  turn_count: number;
  context_snapshot: Record<string, string>;
  feedback?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  overall_score?: number | null;
  max_duration_seconds: number;
  max_questions?: number;
  ends_at: string;
  seconds_remaining?: number | null;
}

export interface MockInterviewSessionDetail extends MockInterviewSessionSummary {
  messages: MockInterviewMessage[];
}

export interface MockInterviewTurnResult {
  candidate_message: MockInterviewMessage;
  interviewer_message: MockInterviewMessage;
  should_end: boolean;
  turn_count: number;
  audio_base64: string;
  audio_mime: string;
}

export interface MockInterviewFeedbackJob {
  job_id: string;
  session_id: string;
  operation: string;
  status: "queued" | "running" | "succeeded" | "failed";
  attempt_count: number;
  error_code?: string | null;
  error_message?: string | null;
  presentation_frame_count: number;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface MockInterviewCompleteResult {
  session?: MockInterviewSessionDetail;
  feedback?: MockInterviewFeedback;
  job?: MockInterviewFeedbackJob;
}

export interface MockInterviewRubricScore {
  id: number;
  key: string;
  label: string;
  category_id: string;
  category_label: string;
  score: number | null;
  notes?: string | null;
}

export interface MockInterviewRubricCategory {
  category_id: string;
  category_label: string;
  average_score: number | null;
  parameters_scored: number;
  parameters_total: number;
}

export type MockInterviewBehaviorStatus = "ok" | "concern" | "not_observable" | "na" | string;

export interface MockInterviewBehaviorParameter {
  id: number;
  category_id: string;
  category_label: string;
  key: string;
  label: string;
  score?: number | null;
  status?: MockInterviewBehaviorStatus;
  detected?: boolean;
  notes?: string;
}

export interface MockInterviewBehaviorCategory {
  category_id: string;
  category_label: string;
  average_score?: number | null;
  parameters_scored?: number;
  parameters_total?: number;
  concerns_detected?: number;
}

export interface MockInterviewAnalysisMeta {
  generated_at?: string;
  message_count?: number;
  candidate_turns?: number;
  presentation_frames_analyzed?: number;
  behavior_parameters_total?: number;
  behavior_concerns?: number;
  rubric_version?: number;
  behavior_analysis_version?: number;
  includes?: string[];
}

export interface MockInterviewFeedback {
  overall_score?: number;
  analysis_meta?: MockInterviewAnalysisMeta;
  rubric_version?: number;
  rubric_overall?: number;
  rubric_scores?: MockInterviewRubricScore[];
  rubric_categories?: MockInterviewRubricCategory[];
  knowledge_summary?: string;
  dimensions?: { key: string; label: string; score: number; notes: string }[];
  question_breakdown?: {
    question: string;
    answer_quality: "strong" | "adequate" | "weak" | "missing" | string;
    notes: string;
  }[];
  presentation?: {
    available?: boolean;
    reason?: string;
    overall_score?: number;
    facial_expression?: { score: number; notes: string };
    eye_contact?: { score: number; notes: string };
    grooming?: { score: number; notes: string };
    professional_conduct?: {
      score?: number | null;
      issues?: string[];
      notes?: string;
    };
    behavior_analysis_version?: number;
    behavior_overall?: number | null;
    behavioral_parameters?: MockInterviewBehaviorParameter[];
    behavior_categories?: MockInterviewBehaviorCategory[];
    presentability_summary?: string;
  };
  answer_authenticity?: {
    overall: "human" | "mixed" | "bookish" | "ai_like" | "missing" | "unknown" | string;
    confidence?: number;
    signals?: string[];
    notes?: string;
  };
  strengths?: string[];
  improvements?: string[];
  sample_answers?: { question: string; suggestion: string }[];
  error?: string;
}

export interface OutreachScrapeJobStats {
  search_queries_run?: number;
  search_results?: number;
  unique_candidate_urls?: number;
  pages_attempted?: number;
  pages_scraped?: number;
  pages_failed?: number;
  candidates_seen?: number;
  leads_created?: number;
  leads_updated?: number;
  duplicates_skipped?: number;
  contacts_extracted?: number;
  contacts_syntax_valid?: number;
  profiles_enriched?: number;
  profiles_needs_review?: number;
  firecrawl_errors?: string[];
  partial?: boolean;
}

export interface OutreachScrapeJob {
  id: string;
  query: string;
  location: string;
  sources: string[];
  max_results: number;
  status: string;
  leads_found: number;
  leads_updated?: number;
  leads_enriched: number;
  stats?: OutreachScrapeJobStats;
  error_message: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
}

export interface OutreachLeadMessage {
  id: string;
  channel: string;
  subject: string;
  body: string;
  status: string;
  sent_at: string | null;
}

export interface OutreachWhatsappStatus {
  status: string;
  qr?: string | null;
  error?: string;
  ready?: boolean;
  session_id?: string;
  connected_at?: string | null;
  bridge_url?: string;
  inbound_enabled?: boolean;
  api_inbound_configured?: boolean;
  bridge_inbound_configured?: boolean;
}

export interface OutreachWhatsappRecentSend {
  lead_id: string;
  name: string;
  sent_at: string | null;
  preview: string;
}

export interface OutreachWhatsappChatThread {
  lead_id: string;
  display_name: string;
  status: string;
  whatsapp_phone: string;
  message_count: number;
  last_message: OutreachLeadChatMessage;
}

export interface OutreachProfileCompletion {
  score_before: number;
  score_after: number;
  searches_run: number;
  search_hits: number;
  urls_scraped: number;
  urls_skipped: number;
  snippets_used: number;
  hints: string[];
}

export interface OutreachBulkImportRow {
  line: string;
  status: "created" | "existing" | "invalid";
  lead_id?: string;
  display_name?: string;
  completeness_score?: number;
  enrich_queued?: boolean;
  enriched?: boolean;
  enrich_error?: string;
  completion?: OutreachProfileCompletion;
  error?: string;
}

export interface OutreachLeadDashboardStats {
  total: number;
  profile_completing: number;
  profile_completion_pending: number;
  completeness_full: number;
  enriched: number;
  discovered: number;
  sent: number;
  skipped_incomplete: number;
  by_status: Record<string, number>;
}

export interface OutreachBulkImportResult {
  created: number;
  existing: number;
  invalid: number;
  enrich_queued: number;
  items: OutreachBulkImportRow[];
}

export interface OutreachBulkActionRow {
  lead_id: string;
  ok: boolean;
  display_name?: string;
  completeness_score?: number;
  error?: string;
  score_before?: number;
  score_after?: number;
  completion?: OutreachProfileCompletion;
}

export interface OutreachBulkActionResult {
  action: "complete" | "enhance";
  succeeded: number;
  failed: number;
  items: OutreachBulkActionRow[];
}

export interface OutreachLeadChatMessage {
  id: string;
  channel: string;
  direction: "inbound" | "outbound" | string;
  body: string;
  created_at: string | null;
}

export interface OutreachLead {
  profile_completing?: boolean;
  id: string;
  job_id: string | null;
  source_platform: string;
  source_url: string;
  display_name: string;
  status: string;
  completeness_score: number;
  institute_id: string | null;
  profile: Record<string, unknown>;
  confidence: number;
  messages: OutreachLeadMessage[];
  whatsapp_phone?: string;
  created_at: string | null;
}
