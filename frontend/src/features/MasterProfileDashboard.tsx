import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Plus, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ME_KEY } from "../auth/session";
import { DynamicField, fromDraft, toDraft, type DraftValue } from "../components/DynamicField";
import { TagInput, TextArea, TextInput } from "../components/form";
import { Modal } from "../components/Modal";
import { useToast } from "../components/Toast";
import { Alert, Button, Card, cx, ProgressBar, Spinner, UserAvatar } from "../components/ui";
import { formatDateTime } from "../lib/format";
import { errorMessage, fieldErrors } from "../services/api";
import { preferences, profile as profileApi, resumes as resumesApi } from "../services/endpoints";
import { LinkedInProfileSyncPanel } from "./LinkedInProfileSyncPanel";
import type {
  CommonApplicationAnswer,
  EducationEntry,
  FieldMeta,
  MasterProfileSections,
  Profile,
  ProfileInput,
  WorkEntry,
} from "../types";

const SECTION_NAV = [
  { id: "personal", label: "Personal details" },
  { id: "professional", label: "Professional overview" },
  { id: "education", label: "Education" },
  { id: "employment", label: "Employment history" },
  { id: "skills", label: "Skills" },
  { id: "projects", label: "Projects" },
  { id: "accomplishments", label: "Accomplishments (optional)" },
  { id: "career", label: "Career preferences" },
  { id: "diversity", label: "Optional personal info" },
  { id: "screening", label: "Screening answers" },
  { id: "common", label: "Common application answers" },
] as const;

type SectionId = (typeof SECTION_NAV)[number]["id"];

type AccRow = { id: string; title: string; org: string; year: string; url: string };
type AccLink = { id: string; label: string; url: string };

function newAccId() {
  return crypto.randomUUID();
}

function accRows(raw: unknown, orgKey: "issuer" | "publisher"): AccRow[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object")
    .map((row) => ({
      id: String(row.id || newAccId()),
      title: String(row.title ?? ""),
      org: String(row[orgKey] ?? row.org ?? ""),
      year: String(row.year ?? ""),
      url: String(row.url ?? ""),
    }));
}

function parseAccLinks(raw: unknown): AccLink[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object")
    .map((row) => ({
      id: String(row.id || newAccId()),
      label: String(row.label ?? row.title ?? ""),
      url: String(row.url ?? ""),
    }));
}

function emptyAccRow(): AccRow {
  return { id: newAccId(), title: "", org: "", year: "", url: "" };
}

function emptyAccLink(): AccLink {
  return { id: newAccId(), label: "", url: "" };
}

const PENDING_DISMISS_KEY = "applyxai.profile-pending-dismissed";

function PendingProfileModal({
  open,
  percent,
  missing,
  enhancing,
  hasResume,
  onClose,
  onEnhance,
  onJump,
}: {
  open: boolean;
  percent: number;
  missing: { section: string; label: string; hint?: string; ai?: boolean }[];
  enhancing: boolean;
  hasResume: boolean;
  onClose: () => void;
  onEnhance: () => void;
  onJump: (section: SectionId) => void;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={percent >= 100 ? "Profile complete" : `Profile is ${percent}% complete`}
      footer={
        <>
          <Button type="button" variant="secondary" onClick={onClose}>
            {percent >= 100 ? "Close" : "I'll add these"}
          </Button>
          <Button type="button" onClick={onEnhance} loading={enhancing} disabled={!hasResume && percent >= 100}>
            <Sparkles className="h-4 w-4" aria-hidden /> Enhance with AI
          </Button>
        </>
      }
    >
      {percent >= 100 ? (
        <p>Required sections are filled. Enhance with AI can still polish headline, summary, and answers from your resume.</p>
      ) : (
        <div className="space-y-3">
          <p>
            Add these to reach 100%. Enhance with AI fills what it can from your resume and will not invent employers,
            salary, or a photo.
          </p>
          {!hasResume && (
            <p>
              <Link to="/app/resumes" className="font-medium text-brand-600 hover:underline" onClick={onClose}>
                Upload a default resume
              </Link>{" "}
              so AI can complete education, skills, and summary.
            </p>
          )}
          <ul className="space-y-2">
            {missing.map((item) => (
              <li key={`${item.section}-${item.label}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <button
                  type="button"
                  className="text-left font-medium text-brand-700 hover:underline"
                  onClick={() => {
                    onJump(item.section as SectionId);
                    onClose();
                  }}
                >
                  {item.label}
                </button>
                <p className="mt-0.5 text-xs text-slate-600">{item.hint}</p>
                {item.ai ? (
                  <p className="mt-1 text-[11px] font-medium uppercase tracking-wide text-brand-600">AI can fill this</p>
                ) : (
                  <p className="mt-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">Needs you</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Modal>
  );
}

function SectionShell({
  id,
  title,
  open,
  onToggle,
  children,
  onSave,
  saving,
  dirty,
}: {
  id: string;
  title: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
  onSave?: () => void;
  saving?: boolean;
  dirty?: boolean;
}) {
  return (
    <div id={id} className="scroll-mt-24">
    <Card className="overflow-hidden">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 text-left"
        onClick={onToggle}
        aria-expanded={open}
      >
        <span className="text-base font-semibold text-slate-900">{title}</span>
        {open ? <ChevronDown className="h-5 w-5 text-slate-400" /> : <ChevronRight className="h-5 w-5 text-slate-400" />}
      </button>
      {open && (
        <div className="mt-4 space-y-4 border-t border-slate-100 pt-4">
          {children}
          {onSave && (
            <div className="flex justify-end gap-2">
              {dirty && <span className="self-center text-xs text-amber-700">Unsaved changes</span>}
              <Button type="button" onClick={onSave} loading={saving}>
                Save section
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
    </div>
  );
}

const emptyEducation = (): EducationEntry => ({
  school: "",
  degree: "",
  field: "",
  start_year: "",
  end_year: "",
});

const emptyWork = (): WorkEntry => ({
  title: "",
  company: "",
  location: "",
  start: "",
  end: "",
  summary: "",
});

export function MasterProfileDashboard() {
  const client = useQueryClient();
  const toast = useToast();
  const { data, isLoading, error } = useQuery({ queryKey: ["profile"], queryFn: profileApi.get });
  const taxonomies = useQuery({ queryKey: ["profile", "taxonomies"], queryFn: profileApi.taxonomies, staleTime: Infinity });
  const fieldMeta = useQuery({ queryKey: ["preferences", "options"], queryFn: preferences.options, staleTime: Infinity });
  const resumes = useQuery({ queryKey: ["resumes"], queryFn: resumesApi.list });
  const defaultResume = resumes.data?.resumes.find((r) => r.is_default) ?? resumes.data?.resumes[0];
  const [openSections, setOpenSections] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(SECTION_NAV.map((s) => [s.id, s.id === "personal" || s.id === "professional"])),
  );
  const toggle = (id: string) => setOpenSections((m) => ({ ...m, [id]: !m[id] }));

  const [pendingOpen, setPendingOpen] = useState(false);

  const jumpTo = useCallback((section: SectionId) => {
    setOpenSections((m) => ({ ...m, [section]: true }));
    requestAnimationFrame(() => document.getElementById(section)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, []);

  const enhanceProfile = useMutation({
    mutationFn: () => profileApi.enhance(),
    onSuccess: (result) => {
      client.setQueryData(["profile"], result.profile);
      void client.invalidateQueries({ queryKey: ["profile"] });
      void client.invalidateQueries({ queryKey: ["preferences", "application"] });
      void client.invalidateQueries({ queryKey: ME_KEY });
      void client.invalidateQueries({ queryKey: ["resumes"] });
      setOpenSections((m) => ({
        ...m,
        professional: true,
        education: true,
        employment: true,
        skills: true,
        projects: true,
        career: true,
        screening: true,
        common: true,
      }));
      const via = result.source === "ai" ? "AI and your resume" : "your resume";
      const leftover = result.missing.map((m) => m.label);
      toast.success(
        leftover.length
          ? `Enhanced from ${via}. Profile is ${result.percent}%. Still needed: ${leftover.join(", ")}.`
          : `Enhanced from ${via}. Profile is 100%. Review, then save any edits.`,
      );
      if (result.percent < 100) setPendingOpen(true);
      else setPendingOpen(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  useEffect(() => {
    const percent = data?.completion?.percent ?? 0;
    if (!data || percent >= 100) return;
    if (sessionStorage.getItem(PENDING_DISMISS_KEY) === String(percent)) return;
    setPendingOpen(true);
  }, [data?.updated_at, data?.completion?.percent]);

  if (isLoading || !data) return isLoading ? <Spinner /> : <Alert kind="error">{errorMessage(error)}</Alert>;

  return (
    <MasterProfileInner
      key={`${data.updated_at}-${data.completion?.percent}`}
      initial={data}
      taxonomies={taxonomies.data}
      screeningFields={
        fieldMeta.data?.profile_answer_fields?.length
          ? fieldMeta.data.profile_answer_fields
          : fieldMeta.data?.application_fields.filter((f) => f.section === "Profile") ?? []
      }
      onRefresh={(saved) => {
        client.setQueryData(["profile"], saved);
        client.invalidateQueries({ queryKey: ME_KEY });
      }}
      toast={toast}
      openSections={openSections}
      toggle={toggle}
      jumpTo={jumpTo}
      defaultResumeId={defaultResume?.id}
      pendingOpen={pendingOpen}
      onPendingOpen={() => setPendingOpen(true)}
      onPendingClose={() => {
        const percent = data.completion?.percent ?? 0;
        sessionStorage.setItem(PENDING_DISMISS_KEY, String(percent));
        setPendingOpen(false);
      }}
      enhancing={enhanceProfile.isPending}
      onEnhance={() => {
        setPendingOpen(true);
        enhanceProfile.mutate();
      }}
    />
  );
}

function MasterProfileInner({
  initial,
  taxonomies,
  screeningFields,
  onRefresh,
  toast,
  openSections,
  toggle,
  jumpTo,
  defaultResumeId,
  pendingOpen,
  onPendingOpen,
  onPendingClose,
  enhancing,
  onEnhance,
}: {
  initial: Profile;
  taxonomies: Awaited<ReturnType<typeof profileApi.taxonomies>> | undefined;
  screeningFields: FieldMeta[];
  onRefresh: (p: Profile) => void;
  toast: ReturnType<typeof useToast>;
  openSections: Record<string, boolean>;
  toggle: (id: string) => void;
  jumpTo: (section: SectionId) => void;
  defaultResumeId?: string;
  pendingOpen: boolean;
  onPendingOpen: () => void;
  onPendingClose: () => void;
  enhancing: boolean;
  onEnhance: () => void;
}) {
  const master = initial.master ?? ({} as MasterProfileSections);
  const personal = { ...(master.personal ?? {}) };
  const professional = { ...(master.professional ?? {}) };
  const career = { ...(master.career ?? {}) };
  const rawAcc = (master.accomplishments ?? {}) as Record<string, unknown>;
  const [accNotes, setAccNotes] = useState(String(rawAcc.notes ?? ""));
  const [accAwards, setAccAwards] = useState<AccRow[]>(() => accRows(rawAcc.awards, "issuer"));
  const [accPubs, setAccPubs] = useState<AccRow[]>(() => accRows(rawAcc.publications, "publisher"));
  const [accLinks, setAccLinks] = useState<AccLink[]>(() => parseAccLinks(rawAcc.links));
  const [diversityForm, setDiversityForm] = useState({ ...(master.diversity ?? {}) });

  const [core, setCore] = useState({
    first_name: initial.first_name,
    last_name: initial.last_name,
    phone: initial.phone ?? "",
    headline: initial.headline ?? "",
    summary: initial.summary ?? "",
    current_title: initial.current_title ?? "",
    current_company: initial.current_company ?? "",
    experience_years: initial.experience_years?.toString() ?? "",
    skills: initial.skills,
    preferred_roles: initial.preferred_roles,
    preferred_locations: initial.preferred_locations,
    education: [...(initial.education ?? [])],
    work_history: [...(initial.work_history ?? [])],
  });

  const [personalForm, setPersonalForm] = useState({
    middle_name: String(personal.middle_name ?? ""),
    dob: String(personal.dob ?? ""),
    gender: String(personal.gender ?? ""),
    marital_status: String(personal.marital_status ?? ""),
    street: String(personal.street ?? ""),
    city: String(personal.city ?? ""),
    state: String(personal.state ?? ""),
    postal_code: String(personal.postal_code ?? ""),
    country: String(personal.country ?? ""),
    languages: (personal.languages as { language: string; proficiency: string }[]) ?? [],
  });

  const [profForm, setProfForm] = useState({
    employment_status: String(professional.employment_status ?? ""),
    additional_months: String(professional.additional_months ?? ""),
    current_ctc: professional.current_ctc != null ? String(professional.current_ctc) : "",
    expected_ctc: professional.expected_ctc != null ? String(professional.expected_ctc) : "",
    salary_currency: String(professional.salary_currency ?? "INR"),
    notice_period_days: professional.notice_period_days != null ? String(professional.notice_period_days) : "",
    notice_description: String(professional.notice_description ?? ""),
    availability_type: String(professional.availability_type ?? "Immediately"),
    availability_description: String(professional.availability_description ?? ""),
    joining_date: String(professional.joining_date ?? ""),
    last_working_day: String(professional.last_working_day ?? ""),
    confidence_level: String(professional.confidence_level ?? ""),
  });

  const [skillRows, setSkillRows] = useState<
    { id: string; name: string; category: string; proficiency: string; years: string; description: string }[]
  >(
    () =>
      (master.skills as { id?: string; name?: string; category?: string; proficiency?: string; years?: string; description?: string }[])?.map(
        (s) => ({
          id: s.id ?? crypto.randomUUID(),
          name: s.name ?? "",
          category: s.category ?? "",
          proficiency: s.proficiency ?? "",
          years: s.years ?? "",
          description: s.description ?? "",
        }),
      ) ?? [],
  );

  const [projects, setProjects] = useState(
    () =>
      (master.projects as { id?: string; title?: string; description?: string; role?: string; technologies?: string }[])?.map(
        (p) => ({
          id: p.id ?? crypto.randomUUID(),
          title: p.title ?? "",
          description: p.description ?? "",
          role: p.role ?? "",
          technologies: p.technologies ?? "",
        }),
      ) ?? [],
  );

  const [commonAnswers, setCommonAnswers] = useState<CommonApplicationAnswer[]>(() => [
    ...(master.common_answers ?? []),
  ]);

  const screeningInitial = useQuery({
    queryKey: ["preferences", "application"],
    queryFn: preferences.application,
  }).data?.answers as Record<string, unknown> | undefined;

  const [screenDraft, setScreenDraft] = useState<Record<string, DraftValue>>(() =>
    Object.fromEntries(screeningFields.map((f) => [f.key, toDraft(f, screeningInitial?.[f.key])])),
  );

  const [errors, setErrors] = useState<Record<string, string>>({});

  const saveCore = useMutation({
    mutationFn: (body: ProfileInput) => profileApi.update(body),
    onSuccess: (saved) => {
      onRefresh(saved);
      toast.success("Profile saved");
    },
    onError: (e) => setErrors(fieldErrors(e)),
  });

  const saveSection = useMutation({
    mutationFn: ({ section, data }: { section: string; data: unknown }) => profileApi.patchSection(section, data),
    onSuccess: (saved) => {
      onRefresh(saved);
      toast.success("Section saved");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const saveScreening = useMutation({
    mutationFn: (changes: Record<string, unknown>) => preferences.patchApplication(changes),
    onSuccess: () => toast.success("Screening answers saved"),
    onError: (e) => toast.error(errorMessage(e)),
  });

  const photoUpload = useMutation({
    mutationFn: (file: File) => profileApi.uploadPhoto(file),
    onSuccess: onRefresh,
    onError: (e) => toast.error(errorMessage(e)),
  });

  const photoRemove = useMutation({
    mutationFn: () => profileApi.deletePhoto(),
    onSuccess: onRefresh,
  });

  const submitCore = (e?: FormEvent) => {
    e?.preventDefault();
    const years = core.experience_years.trim();
    saveCore.mutate({
      ...core,
      phone: core.phone.trim() || null,
      headline: core.headline.trim() || null,
      summary: core.summary.trim() || null,
      current_title: core.current_title.trim() || null,
      current_company: core.current_company.trim() || null,
      experience_years: years ? Number.parseInt(years, 10) : null,
      preferred_resume_template: initial.preferred_resume_template,
      education: core.education.filter((ed) => ed.school.trim() || ed.degree.trim()),
      work_history: core.work_history.filter((w) => w.title.trim() || w.company.trim()),
    });
  };

  const saveEmployment = () => {
    saveSection.mutate({
      section: "professional",
      data: {
        ...profForm,
        current_ctc: profForm.current_ctc ? Number(profForm.current_ctc) : null,
        expected_ctc: profForm.expected_ctc ? Number(profForm.expected_ctc) : null,
        notice_period_days: profForm.notice_period_days ? Number(profForm.notice_period_days) : null,
        additional_months: profForm.additional_months ? Number(profForm.additional_months) : null,
      },
    });
    submitCore();
  };

  const savePersonal = () => saveSection.mutate({ section: "personal", data: personalForm });
  const saveProfessional = () => {
    saveSection.mutate({
      section: "professional",
      data: {
        ...profForm,
        current_ctc: profForm.current_ctc ? Number(profForm.current_ctc) : null,
        expected_ctc: profForm.expected_ctc ? Number(profForm.expected_ctc) : null,
        notice_period_days: profForm.notice_period_days ? Number(profForm.notice_period_days) : null,
        additional_months: profForm.additional_months ? Number(profForm.additional_months) : null,
      },
    });
    submitCore();
  };

  const saveSkills = () => {
    const rows = skillRows.filter((s) => s.name.trim());
    setCore((c) => ({ ...c, skills: rows.map((s) => s.name.trim()) }));
    saveSection.mutate({ section: "skills", data: rows });
  };

  const saveProjects = () => saveSection.mutate({ section: "projects", data: projects.filter((p) => p.title.trim()) });
  const saveCareer = () =>
    saveSection.mutate({
      section: "career",
      data: {
        ...career,
        preferred_roles: core.preferred_roles,
        preferred_locations: core.preferred_locations,
      },
    });
  const saveDiversity = () => saveSection.mutate({ section: "diversity", data: diversityForm });
  const saveCommon = () => saveSection.mutate({ section: "common_answers", data: commonAnswers });

  const saveScreeningSection = () => {
    const changes: Record<string, unknown> = {};
    for (const field of screeningFields) {
      try {
        changes[field.key] = fromDraft(field, screenDraft[field.key]);
      } catch (err) {
        toast.error((err as Error).message);
        return;
      }
    }
    saveScreening.mutate(changes);
  };

  const name = [core.first_name, core.last_name].filter(Boolean).join(" ") || initial.email;
  const completion = initial.completion?.percent ?? 0;
  const photoSrc = initial.photo_url ? `${initial.photo_url}?t=${encodeURIComponent(initial.updated_at ?? "")}` : undefined;

  const missing = initial.completion?.missing ?? [];

  return (
    <div className="space-y-6">
      <LinkedInProfileSyncPanel profile={initial} />
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              {photoSrc ? (
                <img src={photoSrc} alt="" className="h-16 w-16 rounded-full object-cover ring-2 ring-brand-100" />
              ) : (
                <UserAvatar name={name} />
              )}
              <label className="absolute -bottom-1 -right-1 cursor-pointer rounded-full bg-white p-1 shadow ring-1 ring-slate-200">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="sr-only"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) photoUpload.mutate(f);
                  }}
                />
                <span className="text-[10px] font-medium text-brand-600">Photo</span>
              </label>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900">{name}</h2>
              <p className="text-sm text-slate-500">{initial.email}</p>
              {initial.updated_at && (
                <p className="text-xs text-slate-400">Last updated {formatDateTime(initial.updated_at)}</p>
              )}
            </div>
          </div>
          <div
            className={cx(
              "min-w-[220px] space-y-2",
              completion >= 100 && missing.length === 0 && "rounded-xl bg-emerald-50 p-3 ring-1 ring-emerald-200/80",
            )}
          >
            <button
              type="button"
              className="w-full rounded-lg text-left"
              onClick={onPendingOpen}
              disabled={completion >= 100 && missing.length === 0}
            >
              <ProgressBar label="Profile completion" value={completion} max={100} successAtMax />
            </button>
            {completion >= 100 && missing.length === 0 ? (
              <p className="text-xs font-medium text-emerald-700">Profile complete</p>
            ) : completion < 100 ? (
              <button type="button" className="text-xs font-medium text-brand-600 hover:underline" onClick={onPendingOpen}>
                {missing.length === 1 ? "1 item still needed" : `${missing.length} items still needed`}
              </button>
            ) : null}
            <Button type="button" size="sm" className="w-full" loading={enhancing} onClick={onEnhance} disabled={!defaultResumeId && completion >= 100}>
              <Sparkles className="h-4 w-4" aria-hidden /> Enhance with AI
            </Button>
            {!defaultResumeId && (
              <p className="text-xs text-slate-500">
                <Link to="/app/resumes" className="font-medium text-brand-600 hover:underline">
                  Upload a default resume
                </Link>{" "}
                so AI can fill empty sections.
              </p>
            )}
          </div>
        </div>
        {photoSrc && (
          <Button type="button" variant="ghost" size="sm" className="mt-2" onClick={() => photoRemove.mutate()} loading={photoRemove.isPending}>
            Remove photo
          </Button>
        )}
      </Card>

      <div className="flex flex-col gap-6 lg:flex-row">
        <nav className="hidden shrink-0 lg:block lg:w-52" aria-label="Profile sections">
          <ul className="sticky top-20 space-y-1 text-sm">
            {SECTION_NAV.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className={cx(
                    "w-full rounded-lg px-3 py-2 text-left text-slate-600 hover:bg-slate-100",
                    openSections[s.id] && "bg-brand-50 font-medium text-brand-700",
                  )}
                  onClick={() => jumpTo(s.id)}
                >
                  {s.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="min-w-0 flex-1 space-y-4">
          <SectionShell id="personal" title="Personal details" open={openSections.personal} onToggle={() => toggle("personal")} onSave={savePersonal} saving={saveSection.isPending}>
            <div className="grid gap-4 sm:grid-cols-2">
              <TextInput label="First name" value={core.first_name} onChange={(v) => setCore((c) => ({ ...c, first_name: v }))} />
              <TextInput label="Middle name" value={personalForm.middle_name} onChange={(v) => setPersonalForm((p) => ({ ...p, middle_name: v }))} />
              <TextInput label="Last name" value={core.last_name} onChange={(v) => setCore((c) => ({ ...c, last_name: v }))} />
              <TextInput label="Email" value={initial.email} onChange={() => {}} disabled hint="Change email from account settings." />
              <TextInput label="Phone" type="tel" value={core.phone} onChange={(v) => setCore((c) => ({ ...c, phone: v }))} />
              <TextInput label="Date of birth" type="date" value={personalForm.dob} onChange={(v) => setPersonalForm((p) => ({ ...p, dob: v }))} />
              <TextInput label="Gender" value={personalForm.gender} onChange={(v) => setPersonalForm((p) => ({ ...p, gender: v }))} />
              <TextInput label="Marital status" value={personalForm.marital_status} onChange={(v) => setPersonalForm((p) => ({ ...p, marital_status: v }))} />
              <TextInput label="Street address" value={personalForm.street} onChange={(v) => setPersonalForm((p) => ({ ...p, street: v }))} className="sm:col-span-2" />
              <TextInput label="City" value={personalForm.city} onChange={(v) => setPersonalForm((p) => ({ ...p, city: v }))} />
              <TextInput label="State / region" value={personalForm.state} onChange={(v) => setPersonalForm((p) => ({ ...p, state: v }))} />
              <TextInput label="Postal / ZIP" value={personalForm.postal_code} onChange={(v) => setPersonalForm((p) => ({ ...p, postal_code: v }))} />
              <TextInput label="Country" value={personalForm.country} onChange={(v) => setPersonalForm((p) => ({ ...p, country: v }))} />
            </div>
          </SectionShell>

          <SectionShell id="professional" title="Professional overview" open={openSections.professional} onToggle={() => toggle("professional")} onSave={saveProfessional} saving={saveCore.isPending || saveSection.isPending}>
            {errors.experience_years && <Alert kind="error">{errors.experience_years}</Alert>}
            <p className="text-sm text-slate-600">Headline and summary are written from your resume. Compensation stays as you entered it.</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <TextInput label="Resume headline" value={core.headline} onChange={(v) => setCore((c) => ({ ...c, headline: v }))} />
              </div>
              <div className="sm:col-span-2">
                <TextArea label="Professional summary" value={core.summary} onChange={(v) => setCore((c) => ({ ...c, summary: v }))} rows={4} />
              </div>
              <TextInput label="Total years of experience" inputMode="numeric" value={core.experience_years} onChange={(v) => setCore((c) => ({ ...c, experience_years: v }))} />
              <TextInput label="Additional months" inputMode="numeric" value={profForm.additional_months} onChange={(v) => setProfForm((p) => ({ ...p, additional_months: v }))} />
              <TextInput label="Current designation" value={core.current_title} onChange={(v) => setCore((c) => ({ ...c, current_title: v }))} />
              <TextInput label="Current employer" value={core.current_company} onChange={(v) => setCore((c) => ({ ...c, current_company: v }))} />
              <TextInput label="Current CTC (number)" inputMode="numeric" value={profForm.current_ctc} onChange={(v) => setProfForm((p) => ({ ...p, current_ctc: v }))} />
              <TextInput label="Expected CTC (number)" inputMode="numeric" value={profForm.expected_ctc} onChange={(v) => setProfForm((p) => ({ ...p, expected_ctc: v }))} />
              <TextInput label="Salary currency" value={profForm.salary_currency} onChange={(v) => setProfForm((p) => ({ ...p, salary_currency: v }))} />
              <TextInput label="Notice period (days)" inputMode="numeric" value={profForm.notice_period_days} onChange={(v) => setProfForm((p) => ({ ...p, notice_period_days: v }))} />
              <label className="text-sm sm:col-span-2">
                <span className="font-medium text-slate-700">Availability to join</span>
                <select
                  className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                  value={profForm.availability_type}
                  onChange={(e) => setProfForm((p) => ({ ...p, availability_type: e.target.value }))}
                >
                  {["Immediately", "Within days", "Specific date", "After notice period", "Other"].map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              </label>
              {(profForm.availability_type === "Within days" || profForm.availability_type === "Other") && (
                <TextInput label="Availability details" value={profForm.availability_description} onChange={(v) => setProfForm((p) => ({ ...p, availability_description: v }))} className="sm:col-span-2" />
              )}
              {profForm.availability_type === "Specific date" && (
                <TextInput label="Joining date" type="date" value={profForm.joining_date} onChange={(v) => setProfForm((p) => ({ ...p, joining_date: v }))} />
              )}
              {profForm.availability_type === "After notice period" && (
                <TextInput label="Last working day" type="date" value={profForm.last_working_day} onChange={(v) => setProfForm((p) => ({ ...p, last_working_day: v }))} />
              )}
              <TextInput label="Experience scale confidence (1–10)" value={profForm.confidence_level} onChange={(v) => setProfForm((p) => ({ ...p, confidence_level: v }))} />
            </div>
          </SectionShell>

          <SectionShell id="education" title="Education" open={openSections.education} onToggle={() => toggle("education")} onSave={submitCore} saving={saveCore.isPending}>
            <div className="space-y-3">
              {core.education.map((ed, i) => (
                <div key={i} className="rounded-lg border border-slate-200 p-3">
                  <div className="mb-2 flex justify-end">
                    <button type="button" aria-label="Remove" onClick={() => setCore((c) => ({ ...c, education: c.education.filter((_, j) => j !== i) }))}>
                      <Trash2 className="h-4 w-4 text-slate-400 hover:text-red-600" />
                    </button>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <TextInput label="Institution" value={ed.school} onChange={(v) => setCore((c) => ({ ...c, education: c.education.map((e, j) => (j === i ? { ...e, school: v } : e)) }))} />
                    <TextInput label="Degree" value={ed.degree} onChange={(v) => setCore((c) => ({ ...c, education: c.education.map((e, j) => (j === i ? { ...e, degree: v } : e)) }))} />
                    <TextInput label="Field of study" value={ed.field} onChange={(v) => setCore((c) => ({ ...c, education: c.education.map((e, j) => (j === i ? { ...e, field: v } : e)) }))} />
                    <TextInput label="Graduation year" value={ed.end_year} onChange={(v) => setCore((c) => ({ ...c, education: c.education.map((e, j) => (j === i ? { ...e, end_year: v } : e)) }))} />
                  </div>
                </div>
              ))}
              <Button type="button" variant="secondary" size="sm" onClick={() => setCore((c) => ({ ...c, education: [...c.education, emptyEducation()] }))}>
                <Plus className="h-4 w-4" /> Add education
              </Button>
            </div>
          </SectionShell>

          <SectionShell id="employment" title="Employment history" open={openSections.employment} onToggle={() => toggle("employment")} onSave={saveEmployment} saving={saveCore.isPending || saveSection.isPending}>
            <p className="text-sm text-slate-600">
              Enhance with AI fills jobs from your resume. If the resume is fresher, experience is set to Fresher (0 years) and internships are still added when a company is named.
            </p>
            <label className="block text-sm">
              <span className="font-medium text-slate-700">Employment type</span>
              <select
                className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                value={profForm.employment_status}
                onChange={(e) => {
                  const value = e.target.value;
                  setProfForm((p) => ({ ...p, employment_status: value }));
                  if (value === "Fresher") {
                    setCore((c) => ({ ...c, experience_years: "0" }));
                  }
                }}
              >
                <option value="">Select…</option>
                {["Fresher", "Experienced", "Employed", "Unemployed"].map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </label>
            {profForm.employment_status === "Fresher" && core.work_history.filter((w) => w.company.trim()).length === 0 && (
              <Alert kind="info">No employers on the resume. Marked as Fresher with 0 years of experience. Add internships if you have them.</Alert>
            )}
            <div className="space-y-3">
              {core.work_history.map((job, i) => (
                <div key={i} className="rounded-lg border border-slate-200 p-3">
                  <div className="mb-2 flex justify-end">
                    <button type="button" aria-label="Remove" onClick={() => setCore((c) => ({ ...c, work_history: c.work_history.filter((_, j) => j !== i) }))}>
                      <Trash2 className="h-4 w-4 text-slate-400 hover:text-red-600" />
                    </button>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <TextInput label="Company" value={job.company} onChange={(v) => setCore((c) => ({ ...c, work_history: c.work_history.map((w, j) => (j === i ? { ...w, company: v } : w)) }))} />
                    <TextInput label="Job title" value={job.title} onChange={(v) => setCore((c) => ({ ...c, work_history: c.work_history.map((w, j) => (j === i ? { ...w, title: v } : w)) }))} />
                    <TextInput label="Location" value={job.location} onChange={(v) => setCore((c) => ({ ...c, work_history: c.work_history.map((w, j) => (j === i ? { ...w, location: v } : w)) }))} />
                    <TextInput label="Start" value={job.start} onChange={(v) => setCore((c) => ({ ...c, work_history: c.work_history.map((w, j) => (j === i ? { ...w, start: v } : w)) }))} />
                    <TextInput label="End" value={job.end} onChange={(v) => setCore((c) => ({ ...c, work_history: c.work_history.map((w, j) => (j === i ? { ...w, end: v } : w)) }))} />
                  </div>
                  <TextArea label="Responsibilities" value={job.summary} onChange={(v) => setCore((c) => ({ ...c, work_history: c.work_history.map((w, j) => (j === i ? { ...w, summary: v } : w)) }))} rows={2} className="mt-2" />
                </div>
              ))}
              <Button type="button" variant="secondary" size="sm" onClick={() => setCore((c) => ({ ...c, work_history: [...c.work_history, emptyWork()] }))}>
                <Plus className="h-4 w-4" /> Add employment
              </Button>
            </div>
          </SectionShell>

          <SectionShell id="skills" title="IT skills and key skills" open={openSections.skills} onToggle={() => toggle("skills")} onSave={saveSkills} saving={saveSection.isPending}>
            <p className="text-sm text-slate-600">List skills separately from total work experience. Enhance with AI fills these from your resume and will not add tools that are not written there. The automation uses these only when a form asks about a specific skill.</p>
            <TagInput label="Quick skills (also on resume)" value={core.skills} onChange={(v) => setCore((c) => ({ ...c, skills: v }))} />
            {skillRows.map((row, i) => (
              <div key={row.id} className="grid gap-2 rounded-lg border border-slate-200 p-3 sm:grid-cols-6">
                <TextInput label="Skill" value={row.name} onChange={(v) => setSkillRows((rows) => rows.map((r, j) => (j === i ? { ...r, name: v } : r)))} className="sm:col-span-2" />
                <label className="text-sm sm:col-span-2">
                  <span className="font-medium">Category</span>
                  <select className="mt-1 w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm" value={row.category} onChange={(e) => setSkillRows((rows) => rows.map((r, j) => (j === i ? { ...r, category: e.target.value } : r)))}>
                    <option value="">Select…</option>
                    {(taxonomies?.skill_categories ?? []).map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </label>
                <TextInput label="Years" value={row.years} onChange={(v) => setSkillRows((rows) => rows.map((r, j) => (j === i ? { ...r, years: v } : r)))} />
                <div className="flex items-end">
                  <Button type="button" variant="ghost" onClick={() => setSkillRows((rows) => rows.filter((_, j) => j !== i))}>Remove</Button>
                </div>
              </div>
            ))}
            <Button type="button" variant="secondary" size="sm" onClick={() => setSkillRows((r) => [...r, { id: crypto.randomUUID(), name: "", category: "", proficiency: "", years: "", description: "" }])}>
              Add skill
            </Button>
          </SectionShell>

          <SectionShell id="projects" title="Projects" open={openSections.projects} onToggle={() => toggle("projects")} onSave={saveProjects} saving={saveSection.isPending}>
            <p className="text-sm text-slate-600">Freshers: academic projects from the resume. Experienced: project work from employment history.</p>
            {projects.map((p, i) => (
              <div key={p.id} className="space-y-2 rounded-lg border border-slate-200 p-3">
                <TextInput label="Title" value={p.title} onChange={(v) => setProjects((rows) => rows.map((r, j) => (j === i ? { ...r, title: v } : r)))} />
                <TextArea label="Description" value={p.description} onChange={(v) => setProjects((rows) => rows.map((r, j) => (j === i ? { ...r, description: v } : r)))} rows={2} />
                <TextInput label="Technologies" value={p.technologies} onChange={(v) => setProjects((rows) => rows.map((r, j) => (j === i ? { ...r, technologies: v } : r)))} />
                <Button type="button" variant="ghost" size="sm" onClick={() => setProjects((rows) => rows.filter((_, j) => j !== i))}>Remove</Button>
              </div>
            ))}
            <Button type="button" variant="secondary" size="sm" onClick={() => setProjects((r) => [...r, { id: crypto.randomUUID(), title: "", description: "", role: "", technologies: "" }])}>
              Add project
            </Button>
          </SectionShell>

          <SectionShell
            id="accomplishments"
            title="Accomplishments and links (optional)"
            open={openSections.accomplishments}
            onToggle={() => toggle("accomplishments")}
            onSave={() =>
              saveSection.mutate({
                section: "accomplishments",
                data: {
                  notes: accNotes,
                  awards: accAwards
                    .filter((row) => row.title.trim())
                    .map(({ title, org, year, url }) => ({ title: title.trim(), issuer: org.trim(), year: year.trim(), url: url.trim() })),
                  publications: accPubs
                    .filter((row) => row.title.trim())
                    .map(({ title, org, year, url }) => ({ title: title.trim(), publisher: org.trim(), year: year.trim(), url: url.trim() })),
                  links: accLinks
                    .filter((row) => row.url.trim())
                    .map(({ label, url }) => ({ label: label.trim(), url: url.trim() })),
                },
              })
            }
            saving={saveSection.isPending}
          >
            <Alert kind="info">Optional. Awards, publications, and portfolio links are copied into application answers when useful. They do not block 100% completion.</Alert>
            {accAwards.map((row, i) => (
              <div key={row.id} className="space-y-2 rounded-lg border border-slate-200 p-3">
                <TextInput label="Award or certification" value={row.title} onChange={(v) => setAccAwards((rows) => rows.map((r, j) => (j === i ? { ...r, title: v } : r)))} />
                <div className="grid gap-3 sm:grid-cols-2">
                  <TextInput label="Issuer" value={row.org} onChange={(v) => setAccAwards((rows) => rows.map((r, j) => (j === i ? { ...r, org: v } : r)))} />
                  <TextInput label="Year" value={row.year} onChange={(v) => setAccAwards((rows) => rows.map((r, j) => (j === i ? { ...r, year: v } : r)))} />
                </div>
                <TextInput label="Link" value={row.url} onChange={(v) => setAccAwards((rows) => rows.map((r, j) => (j === i ? { ...r, url: v } : r)))} />
                <Button type="button" variant="ghost" size="sm" onClick={() => setAccAwards((rows) => rows.filter((_, j) => j !== i))}>Remove</Button>
              </div>
            ))}
            <Button type="button" variant="secondary" size="sm" onClick={() => setAccAwards((rows) => [...rows, emptyAccRow()])}>
              Add award
            </Button>
            {accPubs.map((row, i) => (
              <div key={row.id} className="space-y-2 rounded-lg border border-slate-200 p-3">
                <TextInput label="Publication" value={row.title} onChange={(v) => setAccPubs((rows) => rows.map((r, j) => (j === i ? { ...r, title: v } : r)))} />
                <div className="grid gap-3 sm:grid-cols-2">
                  <TextInput label="Publisher" value={row.org} onChange={(v) => setAccPubs((rows) => rows.map((r, j) => (j === i ? { ...r, org: v } : r)))} />
                  <TextInput label="Year" value={row.year} onChange={(v) => setAccPubs((rows) => rows.map((r, j) => (j === i ? { ...r, year: v } : r)))} />
                </div>
                <TextInput label="Link" value={row.url} onChange={(v) => setAccPubs((rows) => rows.map((r, j) => (j === i ? { ...r, url: v } : r)))} />
                <Button type="button" variant="ghost" size="sm" onClick={() => setAccPubs((rows) => rows.filter((_, j) => j !== i))}>Remove</Button>
              </div>
            ))}
            <Button type="button" variant="secondary" size="sm" onClick={() => setAccPubs((rows) => [...rows, emptyAccRow()])}>
              Add publication
            </Button>
            {accLinks.map((row, i) => (
              <div key={row.id} className="grid gap-3 rounded-lg border border-slate-200 p-3 sm:grid-cols-2">
                <TextInput label="Link label" value={row.label} onChange={(v) => setAccLinks((rows) => rows.map((r, j) => (j === i ? { ...r, label: v } : r)))} />
                <TextInput label="URL" value={row.url} onChange={(v) => setAccLinks((rows) => rows.map((r, j) => (j === i ? { ...r, url: v } : r)))} />
                <Button type="button" variant="ghost" size="sm" onClick={() => setAccLinks((rows) => rows.filter((_, j) => j !== i))}>Remove</Button>
              </div>
            ))}
            <Button type="button" variant="secondary" size="sm" onClick={() => setAccLinks((rows) => [...rows, emptyAccLink()])}>
              Add link
            </Button>
            <TextArea
              label="Notes"
              value={accNotes}
              onChange={setAccNotes}
              rows={3}
              hint="Anything else you want copied into application answers (patents, open-source, speaking)."
            />
          </SectionShell>

          <SectionShell id="career" title="Career profile and job preferences" open={openSections.career} onToggle={() => toggle("career")} onSave={saveCareer} saving={saveSection.isPending}>
            <p className="text-sm text-slate-600">Used on application forms. Expand titles and cities from your profile.</p>
            <TagInput label="Preferred job roles" value={core.preferred_roles} onChange={(v) => setCore((c) => ({ ...c, preferred_roles: v }))} />
            <TagInput label="Preferred work locations" value={core.preferred_locations} onChange={(v) => setCore((c) => ({ ...c, preferred_locations: v }))} />
            <p className="text-xs text-slate-500">LinkedIn job search filters live under Automation → Job search.</p>
          </SectionShell>

          <SectionShell id="diversity" title="Optional personal and diversity information" open={openSections.diversity} onToggle={() => toggle("diversity")} onSave={saveDiversity} saving={saveSection.isPending}>
            <Alert kind="info">Optional. Leave blank to skip equal-opportunity questions unless a form requires an answer.</Alert>
            <div className="grid gap-4 sm:grid-cols-2">
              <TextInput label="Disability status" value={String(diversityForm.disability_status ?? "")} onChange={(v) => setDiversityForm((d) => ({ ...d, disability_status: v }))} />
              <TextInput label="Veteran status" value={String(diversityForm.veteran_status ?? "")} onChange={(v) => setDiversityForm((d) => ({ ...d, veteran_status: v }))} />
            </div>
          </SectionShell>

          <SectionShell id="screening" title="Engine screening answers" open={openSections.screening} onToggle={() => toggle("screening")} onSave={saveScreeningSection} saving={saveScreening.isPending}>
            <p className="text-sm text-slate-600">These map directly to automation form fields (work authorization, URLs, etc.).</p>
            <div className="grid gap-4 sm:grid-cols-2">
              {screeningFields.map((field) => (
                <div key={field.key} className={field.type === "textarea" ? "sm:col-span-2" : ""}>
                  <DynamicField field={field} value={screenDraft[field.key]} onChange={(v) => setScreenDraft((d) => ({ ...d, [field.key]: v }))} />
                </div>
              ))}
            </div>
          </SectionShell>

          <SectionShell id="common" title="Common application answers" open={openSections.common} onToggle={() => toggle("common")} onSave={saveCommon} saving={saveSection.isPending}>
            <p className="text-sm text-slate-600">Reusable narrative answers. Salary and notice fields sync from Professional overview when not marked verified.</p>
            {commonAnswers.map((a, i) => (
              <div key={a.id} className="space-y-2 rounded-lg border border-slate-200 p-3">
                <p className="text-sm font-medium text-slate-800">{a.question}</p>
                <TextArea
                  label="Answer"
                  value={a.answer}
                  onChange={(v) => setCommonAnswers((rows) => rows.map((r, j) => (j === i ? { ...r, answer: v } : r)))}
                  rows={3}
                />
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={!!a.verified}
                    onChange={(e) => setCommonAnswers((rows) => rows.map((r, j) => (j === i ? { ...r, verified: e.target.checked } : r)))}
                  />
                  Verified — do not auto-sync from profile fields
                </label>
              </div>
            ))}
          </SectionShell>
        </div>
      </div>

      <PendingProfileModal
        open={pendingOpen}
        percent={completion}
        missing={missing}
        enhancing={enhancing}
        hasResume={!!defaultResumeId}
        onClose={onPendingClose}
        onEnhance={onEnhance}
        onJump={jumpTo}
      />
    </div>
  );
}
