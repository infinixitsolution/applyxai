import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ConfirmDialog } from "../components/Modal";
import { TextInput } from "../components/form";
import { useToast } from "../components/Toast";
import { Alert, Button, Card, EmptyState, Spinner } from "../components/ui";
import { formatDateTime } from "../lib/format";
import { errorMessage } from "../services/api";
import { customQuestions, preferences } from "../services/endpoints";
import type { HumanQuestion } from "../types";
import { findDuplicatePatterns, mergeDuplicateQuestions } from "../lib/customQuestionsDedupe";
import { LinkedInCapturedQuestions } from "./LinkedInCapturedQuestions";

function emptyQuestion(): HumanQuestion {
  return {
    id: crypto.randomUUID(),
    match: "contains",
    pattern: "",
    answer: "",
    field_types: ["text", "textarea", "select", "radio"],
    verified: false,
    usage_count: 0,
    input_type: "text",
  };
}

export function CustomApplicationQuestions() {
  const client = useQueryClient();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const appPrefs = useQuery({ queryKey: ["preferences", "application"], queryFn: preferences.application });
  const { data, isLoading, error } = useQuery({ queryKey: ["custom-questions"], queryFn: customQuestions.list });

  const [rows, setRows] = useState<HumanQuestion[]>([]);
  useEffect(() => {
    if (data) setRows(mergeDuplicateQuestions(data.items));
  }, [data]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter(
      (r) => r.pattern.toLowerCase().includes(needle) || r.answer.toLowerCase().includes(needle) || (r.company ?? "").toLowerCase().includes(needle),
    );
  }, [rows, q]);

  const save = useMutation({
    mutationFn: () => {
      const merged = mergeDuplicateQuestions(rows.filter((r) => r.pattern.trim() || r.answer.trim()));
      return customQuestions.replace(merged);
    },
    onSuccess: (saved) => {
      client.setQueryData(["custom-questions"], saved);
      setRows(saved.items);
      toast.success("Questions saved");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const remove = useMutation({
    mutationFn: (id: string) => customQuestions.remove(id),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["custom-questions"] });
      setDeleteId(null);
      toast.success("Deleted");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const syncFromProfile = useMutation({
    mutationFn: () => customQuestions.syncFromProfile(),
    onSuccess: (saved) => {
      client.setQueryData(["custom-questions"], { items: saved.items, total: saved.total });
      setRows(saved.items);
      const n = saved.updated.length;
      const dropped = saved.dropped_standard.length;
      toast.success(
        n || dropped
          ? `Filled from your resume${n ? ` (${n} answer${n === 1 ? "" : "s"})` : ""}${dropped ? `. Removed ${dropped} field${dropped === 1 ? "" : "s"} that belong on the profile.` : "."}`
          : "Already filled from your resume.",
      );
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const dupes = useMemo(() => findDuplicatePatterns(rows), [rows]);

  if (isLoading || appPrefs.isLoading) return <Spinner />;
  if (error || !data || !appPrefs.data) return <Alert kind="error">{errorMessage(error ?? appPrefs.error)}</Alert>;

  const mergeDupes = () => {
    const merged = mergeDuplicateQuestions(rows);
    const removed = rows.length - merged.length;
    setRows(merged);
    toast.success(removed > 0 ? `Merged ${removed} duplicate row(s)` : "No duplicates to merge");
  };

  return (
    <div className="space-y-6">
      <Alert kind="info">
        Standard questions (salary, notice period, years of experience, work authorization) are answered from your{" "}
        <strong>Master Profile</strong>. Fill with AI uses your default resume and will not invent employers.
      </Alert>

      <LinkedInCapturedQuestions aiAvailable={appPrefs.data.ai_available} />

      <Card title="Search and filter">
        <TextInput label="Search questions" value={q} onChange={setQ} placeholder="Filter by question, answer, or company" />
      </Card>

      {dupes.length > 0 && (
        <Alert kind="info">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span>
              Some questions use the same pattern text twice (often from captured + manual entries). Saving will merge
              them automatically, or use Merge duplicates to clean up the table first.
            </span>
            <Button type="button" size="sm" variant="secondary" onClick={mergeDupes}>
              Merge duplicates
            </Button>
          </div>
        </Alert>
      )}

      {filtered.length === 0 ? (
        <Card>
          <EmptyState title="No custom questions yet">
            Questions captured during applications appear above. Add your own patterns below.
          </EmptyState>
        </Card>
      ) : (
        <Card
          title="Saved screening answers"
          actions={
            <Button
              type="button"
              size="sm"
              loading={syncFromProfile.isPending}
              disabled={syncFromProfile.isPending || save.isPending}
              onClick={() => syncFromProfile.mutate()}
            >
              <Sparkles className="h-4 w-4" aria-hidden /> Fill with AI
            </Button>
          }
        >
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-3">Question</th>
                  <th className="py-2 pr-3">Answer</th>
                  <th className="py-2 pr-3">Match</th>
                  <th className="py-2 pr-3">Verified</th>
                  <th className="py-2 pr-3">Used</th>
                  <th className="py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => {
                  const globalIdx = rows.findIndex((r) => r.id === row.id);
                  return (
                    <tr key={row.id} className="border-b border-slate-100 align-top">
                      <td className="max-w-xs py-3 pr-3">
                        <TextInput label="" value={row.pattern} onChange={(v) => setRows((rs) => rs.map((r, i) => (i === globalIdx ? { ...r, pattern: v } : r)))} />
                        {(row.company || row.job_title) && (
                          <p className="mt-1 text-xs text-slate-500">{[row.job_title, row.company].filter(Boolean).join(" · ")}</p>
                        )}
                      </td>
                      <td className="max-w-xs py-3 pr-3">
                        <TextInput label="" value={row.answer} onChange={(v) => setRows((rs) => rs.map((r, i) => (i === globalIdx ? { ...r, answer: v } : r)))} />
                      </td>
                      <td className="py-3 pr-3">
                        <select
                          className="rounded-md border border-slate-200 px-2 py-1 text-sm"
                          value={row.match}
                          onChange={(e) =>
                            setRows((rs) =>
                              rs.map((r, i) => (i === globalIdx ? { ...r, match: e.target.value as HumanQuestion["match"] } : r)),
                            )
                          }
                        >
                          <option value="contains">Contains</option>
                          <option value="exact">Exact</option>
                        </select>
                      </td>
                      <td className="py-3 pr-3">
                        <input
                          type="checkbox"
                          checked={!!row.verified}
                          aria-label={`Verified ${row.pattern}`}
                          onChange={(e) => setRows((rs) => rs.map((r, i) => (i === globalIdx ? { ...r, verified: e.target.checked } : r)))}
                        />
                      </td>
                      <td className="py-3 pr-3 text-xs text-slate-500">
                        {row.usage_count ?? 0}
                        {row.last_used_at && <div>{formatDateTime(row.last_used_at)}</div>}
                      </td>
                      <td className="py-3">
                        <Button type="button" variant="ghost" onClick={() => setDeleteId(row.id)}>
                          Delete
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Button type="button" variant="secondary" onClick={() => setRows((r) => [...r, emptyQuestion()])}>
        Add question manually
      </Button>

      <div className="flex flex-wrap justify-end gap-2">
        <Button
          type="button"
          variant="secondary"
          loading={syncFromProfile.isPending}
          disabled={syncFromProfile.isPending || save.isPending}
          onClick={() => syncFromProfile.mutate()}
        >
          <Sparkles className="h-4 w-4" aria-hidden /> Fill with AI
        </Button>
        <Button loading={save.isPending} onClick={() => save.mutate()} disabled={syncFromProfile.isPending}>
          Save all questions
        </Button>
      </div>

      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        title="Delete this question?"
        danger
        confirmLabel="Delete"
        loading={remove.isPending}
        onConfirm={() => deleteId && remove.mutate(deleteId)}
        message="Future applications will no longer reuse this answer."
      />
    </div>
  );
}
