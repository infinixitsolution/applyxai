import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Pencil, Star, Trash2, Upload } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { TextInput } from "../components/form";
import { ConfirmDialog, Modal } from "../components/Modal";
import { useToast } from "../components/Toast";
import { Alert, Badge, Button, EmptyState, Spinner } from "../components/ui";
import { formatBytes, formatDate } from "../lib/format";
import { errorMessage } from "../services/api";
import { resumes as resumesApi } from "../services/endpoints";
import type { Resume } from "../types";

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

export function ResumeManager() {
  const client = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [renaming, setRenaming] = useState<Resume | null>(null);
  const [newName, setNewName] = useState("");
  const [deleting, setDeleting] = useState<Resume | null>(null);
  const { data, isLoading, error } = useQuery({ queryKey: ["resumes"], queryFn: resumesApi.list });

  const refresh = () => {
    client.invalidateQueries({ queryKey: ["resumes"] });
    client.invalidateQueries({ queryKey: ["usage"] });
  };
  const upload = useMutation({
    mutationFn: (file: File) => resumesApi.upload(file),
    onSuccess: (r) => { refresh(); toast.success(`Uploaded "${r.name}"`); },
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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-600">
          {data.resumes.length} of {data.limit} resume{data.limit === 1 ? "" : "s"} used · PDF or DOCX, up to 5 MB
        </p>
        <input ref={input} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
               className="hidden" onChange={onFile} aria-label="Choose resume file" />
        <Button onClick={() => input.current?.click()} loading={upload.isPending} disabled={atLimit}>
          <Upload className="h-4 w-4" aria-hidden /> Upload resume
        </Button>
      </div>
      {atLimit && (
        <Alert kind="info">You've reached your plan's resume limit. Delete one, or <Link to="/app/billing" className="font-medium underline">upgrade your plan</Link>.</Alert>
      )}

      {data.resumes.length === 0 ? (
        <EmptyState icon={<FileText className="h-10 w-10" />} title="No resumes yet">
          Upload the resume you want the automation to attach to applications.
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
              </div>
              <div className="flex flex-wrap gap-1">
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
    </div>
  );
}
