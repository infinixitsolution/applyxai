import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Palette, Pencil, Star, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { Select, TextInput } from "../components/form";
import { ConfirmDialog, Modal } from "../components/Modal";
import { useToast } from "../components/Toast";
import { Alert, Badge, Button, EmptyState, Spinner } from "../components/ui";
import { formatBytes, formatDate } from "../lib/format";
import { errorMessage } from "../services/api";
import { applications as applicationsApi, profile as profileApi, resumes as resumesApi } from "../services/endpoints";
import type { Application, ProfileInput, Resume } from "../types";
import { ResumeTemplatePicker } from "./ResumeTemplatePicker";

export const MAX_RESUME_BYTES = 5 * 1024 * 1024;
const ACCEPTED = [".pdf", ".docx"];

/** Client-side pre-check for a friendlier message; the server validates the real content. */
export function resumeFileProblem(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED.some((ext) => name.endsWith(ext))) return "Please choose a PDF or DOCX file.";
  if (file.size === 0) return "That file is empty.";
  if (file.size > MAX_RESUME_BYTES) return "Resumes must be 5 MB or smaller.";
  return null;
}

type ResumeManagerProps = {
  /** First-time setup: require upload, run intake, hide skip elsewhere. */
  onboarding?: boolean;
  onIntakeDone?: () => void;
};

export function ResumeManager({ onboarding = false, onIntakeDone }: ResumeManagerProps = {}) {
  const client = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [renaming, setRenaming] = useState<Resume | null>(null);
  const [newName, setNewName] = useState("");
  const [deleting, setDeleting] = useState<Resume | null>(null);
  const [tailoring, setTailoring] = useState<Resume | null>(null);
  const [styling, setStyling] = useState<Resume | null>(null);
  const [jd, setJd] = useState("");
  const [preview, setPreview] = useState<import("../types").ResumeAiPreview | null>(null);
  const [templateId, setTemplateId] = useState("modern");
  const [linkApplicationId, setLinkApplicationId] = useState("");

  const { data, isLoading, error } = useQuery({ queryKey: ["resumes"], queryFn: resumesApi.list });
  const { data: applicationChoices } = useQuery({
    queryKey: ["applications", "for-resume-link"],
    queryFn: () => applicationsApi.list({ page: 1, page_size: 50, sort: "-applied_at" }),
  });
  const { data: templatesData } = useQuery({ queryKey: ["resume-templates"], queryFn: resumesApi.templates });
  const { data: profile } = useQuery({ queryKey: ["profile"], queryFn: profileApi.get });

  useEffect(() => {
    if (profile?.preferred_resume_template) setTemplateId(profile.preferred_resume_template);
  }, [profile?.preferred_resume_template]);

  const templates = templatesData?.templates ?? [];

  const refresh = () => {
    client.invalidateQueries({ queryKey: ["resumes"] });
    client.invalidateQueries({ queryKey: ["usage"] });
    client.invalidateQueries({ queryKey: ["applications"] });
  };

  const saveTemplatePreference = useMutation({
    mutationFn: async (id: string) => {
      if (!profile) throw new Error("Profile not loaded");
      const body: ProfileInput = {
        first_name: profile.first_name,
        last_name: profile.last_name,
        phone: profile.phone,
        headline: profile.headline,
        summary: profile.summary,
        current_title: profile.current_title,
        current_company: profile.current_company,
        experience_years: profile.experience_years,
        skills: profile.skills,
        preferred_roles: profile.preferred_roles,
        preferred_locations: profile.preferred_locations,
        preferred_resume_template: id,
        education: profile.education ?? [],
        work_history: profile.work_history ?? [],
      };
      return profileApi.update(body);
    },
    onSuccess: (saved) => {
      client.setQueryData(["profile"], saved);
      toast.success("Default resume style saved");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const onTemplateChange = (id: string) => {
    setTemplateId(id);
    saveTemplatePreference.mutate(id);
  };

  const intake = useMutation({
    mutationFn: (id: string) => resumesApi.intake(id, true),
    onSuccess: (result) => {
      client.setQueryData(["profile"], result.profile);
      void client.invalidateQueries({ queryKey: ["preferences", "application"] });
      void client.invalidateQueries({ queryKey: ["me"] });
      const via = result.source === "ai" ? "AI" : "your resume";
      const ocr =
        result.text_extraction === "ocr" || result.text_extraction === "pdf_text+ocr"
          ? " (scanned PDF read with OCR)"
          : "";
      toast.success(`Profile and cover letter filled from ${via}${ocr}. Review the next steps.`);
      onIntakeDone?.();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const upload = useMutation({
    mutationFn: (file: File) => resumesApi.upload(file),
    onSuccess: (r) => {
      refresh();
      if (onboarding) {
        toast.success(`Uploaded "${r.name}". Reading it now…`);
        intake.mutate(r.id);
      } else {
        toast.success(`Uploaded "${r.name}"`);
      }
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const rename = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => resumesApi.rename(id, name),
    onSuccess: () => { refresh(); setRenaming(null); toast.success("Renamed"); },
  });
  const makeDefault = useMutation({
    mutationFn: resumesApi.makeDefault,
    onSuccess: (r) => { refresh(); toast.success(`"${r.name}" is now your default resume`); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => resumesApi.remove(id),
    onSuccess: () => { refresh(); setDeleting(null); toast.success("Resume deleted"); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const analyze = useMutation({
    mutationFn: (id: string) => resumesApi.analyzeMaster(id),
    onSuccess: (r) => { refresh(); toast.success(`Detected ${r.master_skills?.length ?? 0} master skills`); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const applyStyle = useMutation({
    mutationFn: ({ id, template_id }: { id: string; template_id: string }) => resumesApi.applyStyle(id, template_id),
    onSuccess: (r) => {
      refresh();
      setStyling(null);
      toast.success(`Saved styled copy "${r.name}"`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const aiPreview = useMutation({
    mutationFn: () => resumesApi.aiPreview({ resume_id: tailoring!.id, job_description: jd.trim() }),
    onSuccess: (p) => setPreview(p),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const aiTailor = useMutation({
    mutationFn: () =>
      resumesApi.aiTailor({
        resume_id: tailoring!.id,
        job_description: jd.trim(),
        template_id: templateId,
        application_id: linkApplicationId || undefined,
        job_id: applicationChoices?.items.find((a: Application) => a.id === linkApplicationId)?.job.external_id,
      }),
    onSuccess: () => {
      refresh();
      setTailoring(null);
      setJd("");
      setPreview(null);
      toast.success("Tailored resume saved");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const problem = resumeFileProblem(file);
    if (problem) toast.error(problem);
    else upload.mutate(file);
  };

  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  const atLimit = data.resumes.length >= data.limit;

  return (
    <div className="space-y-4">
      {templates.length > 0 && (
        <section className="rounded-xl bg-white p-4 ring-1 ring-slate-200 sm:p-5">
          <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Resume style</h2>
              <p className="text-xs text-slate-600">
                Choose a layout for tailored exports and styled copies. Your default is saved to your profile.
              </p>
            </div>
            {saveTemplatePreference.isPending && <span className="text-xs text-slate-500">Saving…</span>}
          </div>
          <ResumeTemplatePicker
            templates={templates}
            value={templateId}
            onUse={onTemplateChange}
            disabled={saveTemplatePreference.isPending || !profile}
            displayName={[profile?.first_name, profile?.last_name].filter(Boolean).join(" ") || undefined}
          />
        </section>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-600">
          {data.resumes.length} of {data.limit} resume{data.limit === 1 ? "" : "s"} used · PDF or DOCX, up to 5 MB · scanned PDFs use OCR
        </p>
        <input ref={input} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
               className="hidden" onChange={onFile} aria-label="Choose resume file" />
        <Button
          onClick={() => input.current?.click()}
          loading={upload.isPending || intake.isPending}
          disabled={atLimit}
        >
          <Upload className="h-4 w-4" aria-hidden /> Upload resume
        </Button>
      </div>
      {atLimit && (
        <Alert kind="info">You've reached your plan's resume limit. Delete one, or <Link to="/app/billing" className="font-medium underline">upgrade your plan</Link>.</Alert>
      )}

      {onboarding && data.resumes.length === 0 && (
        <Alert kind="info">
          Upload your resume first (PDF or DOCX). Scanned PDFs are read with <strong>OCR</strong> so photos and image-only CVs still
          fill your profile, experience, education, and application answers.
        </Alert>
      )}

      {data.resumes.length === 0 ? (
        <EmptyState icon={<FileText className="h-10 w-10" />} title="No resumes yet">
          {onboarding
            ? "Choose a PDF or DOCX file to continue setup."
            : "Upload the resume you want the automation to attach to applications."}
        </EmptyState>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-xl bg-white ring-1 ring-slate-200">
          {data.resumes.map((r) => (
            <li key={r.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
              <FileText className="hidden h-8 w-8 shrink-0 text-slate-400 sm:block" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 font-medium text-slate-900">
                  <span className="truncate">{r.name}</span>
                  {r.is_default && <Badge tone="brand">Default</Badge>}
                </p>
                <p className="truncate text-xs text-slate-500">
                  {r.filename} · {r.file_type.toUpperCase()} · {formatBytes(r.file_size)} · uploaded {formatDate(r.created_at)}
                </p>
                {typeof r.ai_metadata?.template_name === "string" && (
                  <p className="mt-1 text-xs text-slate-600">Style: {String(r.ai_metadata.template_name)}</p>
                )}
                {r.master_skills && r.master_skills.length > 0 && (
                  <p className="mt-1 text-xs text-slate-600">
                    Master skills: {r.master_skills.slice(0, 8).join(", ")}
                    {r.master_skills.length > 8 ? "…" : ""}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-1">
                <Button variant="ghost" size="sm" loading={analyze.isPending && analyze.variables === r.id}
                        onClick={() => analyze.mutate(r.id)}>Analyze skills</Button>
                <Button variant="ghost" size="sm" onClick={() => { setStyling(r); }}>
                  <Palette className="h-4 w-4" aria-hidden /> Apply style
                </Button>
                <Button variant="ghost" size="sm" onClick={() => { setTailoring(r); setPreview(null); setJd(""); setLinkApplicationId(""); }}>
                  Tailor to job
                </Button>
                {!r.is_default && (
                  <Button variant="ghost" size="sm" onClick={() => makeDefault.mutate(r.id)}>
                    <Star className="h-4 w-4" aria-hidden /> Make default
                  </Button>
                )}
                <a href={resumesApi.downloadUrl(r.id)} className="inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100">
                  <Download className="h-4 w-4" aria-hidden /> Download
                </a>
                <Button variant="ghost" size="sm" aria-label={`Rename ${r.name}`} onClick={() => { setRenaming(r); setNewName(r.name); }}>
                  <Pencil className="h-4 w-4" aria-hidden />
                </Button>
                <Button variant="ghost" size="sm" aria-label={`Delete ${r.name}`} onClick={() => setDeleting(r)}>
                  <Trash2 className="h-4 w-4 text-red-600" aria-hidden />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal open={!!renaming} onClose={() => setRenaming(null)} title="Rename resume" footer={
        <>
          <Button variant="secondary" onClick={() => setRenaming(null)}>Cancel</Button>
          <Button loading={rename.isPending} disabled={!newName.trim()}
                  onClick={() => renaming && rename.mutate({ id: renaming.id, name: newName.trim() })}>Save</Button>
        </>
      }>
        {rename.error && <div className="mb-3"><Alert kind="error">{errorMessage(rename.error)}</Alert></div>}
        <TextInput label="Name" value={newName} onChange={setNewName} maxLength={255} autoFocus />
      </Modal>

      <ConfirmDialog open={!!deleting} onClose={() => setDeleting(null)} title="Delete resume?" danger confirmLabel="Delete"
                     loading={remove.isPending} onConfirm={() => deleting && remove.mutate(deleting.id)}
                     message={<>"{deleting?.name}" will be permanently deleted.{deleting?.is_default && " Your newest remaining resume becomes the default."}</>} />

      <Modal open={!!styling} onClose={() => setStyling(null)} title={`Apply style to "${styling?.name ?? ""}"`}
             footer={
               <>
                 <Button variant="secondary" onClick={() => setStyling(null)}>Cancel</Button>
                 <Button
                   loading={applyStyle.isPending}
                   disabled={atLimit || !templates.length}
                   onClick={() => styling && applyStyle.mutate({ id: styling.id, template_id: templateId })}
                 >
                   Save styled DOCX
                 </Button>
               </>
             }>
        {atLimit && (
          <div className="mb-3">
            <Alert kind="info">
              Resume limit reached — delete a resume or upgrade before saving a styled copy.
            </Alert>
          </div>
        )}
        <p className="mb-3 text-sm text-slate-600">
          Creates a new Word file with your content and the selected fonts, spacing, and section colors.
        </p>
        {templates.length > 0 && (
          <ResumeTemplatePicker
            templates={templates}
            value={templateId}
            onUse={setTemplateId}
            compact
            displayName={[profile?.first_name, profile?.last_name].filter(Boolean).join(" ") || undefined}
            useLabel="Use for export"
          />
        )}
      </Modal>

      <Modal open={!!tailoring} onClose={() => { setTailoring(null); setPreview(null); }} title={`Tailor "${tailoring?.name ?? ""}"`}
             footer={
               <>
                 <Button variant="secondary" onClick={() => { setTailoring(null); setPreview(null); }}>Close</Button>
                 <Button variant="secondary" loading={aiPreview.isPending} disabled={jd.trim().length < 40}
                         onClick={() => aiPreview.mutate()}>Preview match</Button>
                 <Button loading={aiTailor.isPending} disabled={!preview?.gate_passed}
                         onClick={() => aiTailor.mutate()}>Save tailored resume</Button>
               </>
             }>
        <div className="mb-3">
        <Alert kind="info">
          Requires ≥60% keyword match. Edits stay in your existing layout (summary/skills/bullets), plain wording, no extra AI sections. Fit score is an estimate only.
        </Alert>
        </div>
        {templates.length > 0 && (
          <div className="mb-4">
            <p className="mb-2 text-sm font-medium text-slate-800">Export style</p>
            <ResumeTemplatePicker
              templates={templates}
              value={templateId}
              onUse={setTemplateId}
              compact
              displayName={[profile?.first_name, profile?.last_name].filter(Boolean).join(" ") || undefined}
              useLabel="Use for export"
            />
          </div>
        )}
        {(applicationChoices?.items.length ?? 0) > 0 && (
          <div className="mb-4">
            <Select
              label="Link to application (optional)"
              value={linkApplicationId}
              onChange={setLinkApplicationId}
              options={[
                { value: "", label: "Don't link yet" },
                ...applicationChoices!.items.map((a: Application) => ({
                  value: a.id,
                  label: `${a.job.title} · ${a.job.company}`,
                })),
              ]}
            />
          </div>
        )}
        <textarea className="min-h-[160px] w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={jd}
                  onChange={(e) => setJd(e.target.value)} placeholder="Paste the job description…" />
        {preview && (
          <div className="mt-4 space-y-2 text-sm">
            <p>Match score: <strong>{preview.match_score}%</strong>{preview.gate_passed ? "" : " (below 60% gate)"}</p>
            {preview.fit_score != null && <p>Estimated fit: <strong>{preview.fit_score}%</strong></p>}
            {preview.missing_keywords?.length > 0 && (
              <p className="text-slate-600">Missing keywords: {preview.missing_keywords.slice(0, 12).join(", ")}</p>
            )}
            {preview.disclaimer && <p className="text-xs text-slate-500">{preview.disclaimer}</p>}
          </div>
        )}
      </Modal>
    </div>
  );
}
