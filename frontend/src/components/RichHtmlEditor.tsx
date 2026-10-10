import {
  Bold, Code, Eye, Heading2, Heading3, Italic, Link2, List, ListOrdered, Pilcrow,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { contentForLegalEditor, sanitizeLegalHtml } from "../lib/htmlContent";
import { cx } from "./ui";

type EditorMode = "visual" | "html" | "preview";

const PROSE =
  "prose prose-sm prose-slate max-w-none [&_a]:text-brand-700 [&_h2]:mt-6 [&_h2]:text-lg [&_h2]:font-semibold [&_ul]:list-disc [&_ol]:list-decimal";

function ToolbarButton({
  label,
  onClick,
  active,
  children,
}: {
  label: string;
  onClick: () => void;
  active?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      className={cx(
        "rounded-md p-1.5 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900",
        active && "bg-slate-200 text-slate-900",
      )}
    >
      {children}
    </button>
  );
}

export function RichHtmlEditor({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  onChange: (html: string) => void;
  hint?: string;
}) {
  const [mode, setMode] = useState<EditorMode>("visual");
  const editorRef = useRef<HTMLDivElement>(null);
  const seeded = useRef(false);

  const syncFromVisual = useCallback(() => {
    if (!editorRef.current) return;
    onChange(sanitizeLegalHtml(editorRef.current.innerHTML));
  }, [onChange]);

  const runCommand = (command: string, arg?: string) => {
    editorRef.current?.focus();
    document.execCommand(command, false, arg);
    syncFromVisual();
  };

  const insertLink = () => {
    const url = window.prompt("Link URL (https://…)");
    if (!url?.trim()) return;
    runCommand("createLink", url.trim());
  };

  useEffect(() => {
    if (mode !== "visual" || !editorRef.current || seeded.current) return;
    editorRef.current.innerHTML = sanitizeLegalHtml(contentForLegalEditor(value));
    seeded.current = true;
  }, [mode, value]);

  useEffect(() => {
    seeded.current = false;
  }, [label]);

  const switchMode = (next: EditorMode) => {
    if (mode === "visual" && next !== "visual") syncFromVisual();
    if (next === "visual") seeded.current = false;
    setMode(next);
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const html = e.clipboardData.getData("text/html");
    const text = e.clipboardData.getData("text/plain");
    const toInsert = html ? sanitizeLegalHtml(html) : text.replace(/\n/g, "<br>");
    document.execCommand("insertHTML", false, toInsert);
    syncFromVisual();
  };

  return (
    <div className="mb-6 last:mb-0">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-slate-700">{label}</span>
        <div className="flex rounded-lg bg-slate-100 p-0.5 text-xs font-medium">
          {(["visual", "html", "preview"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => switchMode(m)}
              className={cx(
                "rounded-md px-2.5 py-1 capitalize transition-colors",
                mode === m ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900",
              )}
            >
              {m === "visual" ? "Visual" : m === "html" ? "HTML" : "Preview"}
            </button>
          ))}
        </div>
      </div>

      {mode === "visual" && (
        <div className="overflow-hidden rounded-lg ring-1 ring-slate-300 focus-within:ring-2 focus-within:ring-brand-600">
          <div className="flex flex-wrap items-center gap-0.5 border-b border-slate-200 bg-slate-50 px-2 py-1.5">
            <ToolbarButton label="Paragraph" onClick={() => runCommand("formatBlock", "p")}>
              <Pilcrow className="h-4 w-4" aria-hidden />
            </ToolbarButton>
            <ToolbarButton label="Heading 2" onClick={() => runCommand("formatBlock", "h2")}>
              <Heading2 className="h-4 w-4" aria-hidden />
            </ToolbarButton>
            <ToolbarButton label="Heading 3" onClick={() => runCommand("formatBlock", "h3")}>
              <Heading3 className="h-4 w-4" aria-hidden />
            </ToolbarButton>
            <span className="mx-1 h-5 w-px bg-slate-200" aria-hidden />
            <ToolbarButton label="Bold" onClick={() => runCommand("bold")}>
              <Bold className="h-4 w-4" aria-hidden />
            </ToolbarButton>
            <ToolbarButton label="Italic" onClick={() => runCommand("italic")}>
              <Italic className="h-4 w-4" aria-hidden />
            </ToolbarButton>
            <ToolbarButton label="Link" onClick={insertLink}>
              <Link2 className="h-4 w-4" aria-hidden />
            </ToolbarButton>
            <span className="mx-1 h-5 w-px bg-slate-200" aria-hidden />
            <ToolbarButton label="Bullet list" onClick={() => runCommand("insertUnorderedList")}>
              <List className="h-4 w-4" aria-hidden />
            </ToolbarButton>
            <ToolbarButton label="Numbered list" onClick={() => runCommand("insertOrderedList")}>
              <ListOrdered className="h-4 w-4" aria-hidden />
            </ToolbarButton>
          </div>
          <div
            ref={editorRef}
            contentEditable
            suppressContentEditableWarning
            role="textbox"
            aria-multiline
            aria-label={`${label} visual editor`}
            onInput={syncFromVisual}
            onBlur={syncFromVisual}
            onPaste={handlePaste}
            className={cx(
              "min-h-[12rem] bg-white px-3 py-3 text-sm leading-relaxed text-slate-800 outline-none",
              PROSE,
            )}
          />
        </div>
      )}

      {mode === "html" && (
        <textarea
          aria-label={`${label} HTML source`}
          className="min-h-[12rem] w-full rounded-lg border-0 bg-white px-3 py-2 font-mono text-xs text-slate-900 shadow-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-brand-600"
          rows={14}
          value={value}
          onChange={(e) => onChange(sanitizeLegalHtml(e.target.value))}
        />
      )}

      {mode === "preview" && (
        <div
          className={cx(
            "min-h-[12rem] rounded-lg bg-slate-50/80 px-4 py-3 text-sm leading-relaxed text-slate-700 ring-1 ring-slate-200",
            PROSE,
          )}
        >
          {value.trim() ? (
            <div dangerouslySetInnerHTML={{ __html: sanitizeLegalHtml(contentForLegalEditor(value)) }} />
          ) : (
            <p className="flex items-center gap-2 text-slate-500">
              <Eye className="h-4 w-4" aria-hidden /> Nothing to preview yet.
            </p>
          )}
        </div>
      )}

      {hint && <p className="mt-1.5 text-xs text-slate-500">{hint}</p>}
      {mode === "html" && (
        <p className="mt-1.5 text-xs text-slate-500">
          <Code className="mr-1 inline h-3 w-3 align-text-bottom" aria-hidden />
          HTML is sanitized on save. Legacy Markdown is converted when you open Visual mode.
        </p>
      )}
    </div>
  );
}
