import { useState } from "react";
import { Modal } from "../components/Modal";
import { Button } from "../components/ui";
import type { ResumeTemplate } from "../types";
import { ResumeTemplateMock } from "./ResumeTemplateMock";

type Props = {
  templates: ResumeTemplate[];
  value: string;
  onUse: (id: string) => void;
  disabled?: boolean;
  compact?: boolean;
  displayName?: string;
  useLabel?: string;
};

export function ResumeTemplatePicker({
  templates,
  value,
  onUse,
  disabled,
  compact,
  displayName,
  useLabel = "Use this style",
}: Props) {
  const [previewId, setPreviewId] = useState<string | null>(null);
  const preview = templates.find((t) => t.id === previewId) ?? null;

  const apply = (id: string) => {
    onUse(id);
    setPreviewId(null);
  };

  return (
    <>
      <div
        className={
          compact
            ? "grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5"
            : "grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
        }
        role="listbox"
        aria-label="Resume style"
      >
        {templates.map((t) => {
          const selected = t.id === value;
          return (
            <button
              key={t.id}
              type="button"
              role="option"
              aria-selected={selected}
              disabled={disabled}
              onClick={() => setPreviewId(t.id)}
              className={
                "overflow-hidden rounded-xl text-left ring-1 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-60 " +
                (selected ? "ring-2 ring-brand-500 bg-brand-50/40" : "ring-slate-200 bg-white hover:bg-slate-50")
              }
            >
              <div className="h-2 shrink-0" style={{ backgroundColor: t.accent }} aria-hidden />
              <div className={compact ? "p-1.5" : "p-2"}>
                <div
                  className="relative mb-2 h-[80px] overflow-hidden rounded-md bg-slate-50 ring-1 ring-slate-100"
                  aria-hidden
                >
                  <div className="absolute inset-0 flex items-start justify-center pt-1">
                    <ResumeTemplateMock template={t} displayName={displayName} variant="thumb" />
                  </div>
                </div>
                <p className={`font-medium text-slate-900 ${compact ? "text-xs" : "text-sm"}`}>{t.name}</p>
                {!compact && <p className="line-clamp-2 text-xs text-slate-500">{t.description}</p>}
                <p className="text-[10px] uppercase tracking-wide text-slate-400">{t.layout_label}</p>
                {selected && (
                  <p className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-brand-600">In use</p>
                )}
              </div>
            </button>
          );
        })}
      </div>

      <Modal
        open={!!preview}
        onClose={() => setPreviewId(null)}
        title={preview ? `${preview.name} template` : "Template preview"}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setPreviewId(null)}>
              Cancel
            </Button>
            <Button disabled={disabled} onClick={() => preview && apply(preview.id)}>
              {useLabel}
            </Button>
          </>
        }
      >
        {preview && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">{preview.description}</p>
            <p className="text-xs text-slate-500">
              Layout: {preview.layout_label} · Headings: {preview.heading_font} · Body: {preview.body_font}
            </p>
            <div className="mx-auto max-w-lg bg-slate-100 p-4 sm:p-6">
              <ResumeTemplateMock template={preview} displayName={displayName} variant="full" />
            </div>
            <p className="text-center text-xs text-slate-500">
              Preview shows sample content. Your real resume keeps your text with this layout applied on export.
            </p>
          </div>
        )}
      </Modal>
    </>
  );
}
