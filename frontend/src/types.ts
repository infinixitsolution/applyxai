export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_verified: boolean;
  is_admin: boolean;
  created_at: string;
  last_login_at: string | null;
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

export interface AutomationOverview {
  active: AutomationRun | null;
  recent: AutomationRun[];
  devices: AgentDevice[];
  agent_online: boolean;
  readiness: { ready: boolean; problems: string[] };
  usage: Usage;
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

export interface Plan {
  code: string;
  name: string;
  price_cents: number;
  currency: string;
  interval: string;
  limits: { applications_per_month: number; resumes: number };
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
  prefill: { email: string; name: string };
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
  is_active: boolean;
  sort_order: number;
}
