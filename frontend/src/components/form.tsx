import { Check, X } from "lucide-react";
import { useId, useState, type InputHTMLAttributes, type KeyboardEvent, type ReactNode, type SelectHTMLAttributes,
  type TextareaHTMLAttributes } from "react";
import { cx } from "./ui";

const INPUT = "block w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset " +
  "ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-brand-600 disabled:bg-slate-50";

interface FieldProps {
  label: string;
  error?: string;
  hint?: ReactNode;
  children: (id: string, describedBy: string | undefined) => ReactNode;
}

export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      {children(id, describedBy)}
      {error ? <p id={`${id}-error`} className="mt-1 text-sm text-red-600">{error}</p>
        : hint ? <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

type TextInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "onChange"> & {
  label: string;
  error?: string;
  hint?: ReactNode;
  onChange: (value: string) => void;
};

export function TextInput({ label, error, hint, onChange, className, ...rest }: TextInputProps) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(id, describedBy) => (
        <input id={id} aria-invalid={!!error} aria-describedby={describedBy} {...rest}
               onChange={(e) => onChange(e.target.value)}
               className={cx(INPUT, error && "ring-red-400", className)} />
      )}
    </Field>
  );
}

type TextAreaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "onChange"> & {
  label: string;
  error?: string;
  hint?: ReactNode;
  onChange: (value: string) => void;
};

export function TextArea({ label, error, hint, onChange, ...rest }: TextAreaProps) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(id, describedBy) => (
        <textarea id={id} rows={4} aria-invalid={!!error} aria-describedby={describedBy} {...rest}
                  onChange={(e) => onChange(e.target.value)} className={cx(INPUT, error && "ring-red-400")} />
      )}
    </Field>
  );
}

type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "onChange"> & {
  label: string;
  options: { value: string; label: string }[];
  error?: string;
  hint?: ReactNode;
  onChange: (value: string) => void;
};

export function Select({ label, options, error, hint, onChange, ...rest }: SelectProps) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(id, describedBy) => (
        <select id={id} aria-invalid={!!error} aria-describedby={describedBy} {...rest}
                onChange={(e) => onChange(e.target.value)} className={cx(INPUT, "pr-8", error && "ring-red-400")}>
          {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      )}
    </Field>
  );
}

export function Toggle({ label, checked, onChange, hint }:
  { label: string; checked: boolean; onChange: (value: boolean) => void; hint?: ReactNode }) {
  const id = useId();
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <label htmlFor={id} className="text-sm font-medium text-slate-700">{label}</label>
        {hint && <p className="text-xs text-slate-500">{hint}</p>}
      </div>
      <button id={id} type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
              className={cx("relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors",
                checked ? "bg-brand-600" : "bg-slate-200")}>
        <span className={cx("absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-5" : "translate-x-0.5")} />
      </button>
    </div>
  );
}

/** Multi-select for enumerated engine values: users pick, never type. */
export function ChipSelect({ label, options, value, onChange, error, hint }: {
  label: string; options: string[]; value: string[]; onChange: (value: string[]) => void; error?: string; hint?: ReactNode;
}) {
  const toggle = (option: string) =>
    onChange(value.includes(option) ? value.filter((v) => v !== option) : options.filter((o) => o === option || value.includes(o)));
  return (
    <fieldset>
      <legend className="mb-1 text-sm font-medium text-slate-700">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const selected = value.includes(option);
          return (
            <button key={option} type="button" aria-pressed={selected} onClick={() => toggle(option)}
                    className={cx("inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                      selected ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
              {selected && <Check className="h-3.5 w-3.5" aria-hidden />}
              {option}
            </button>
          );
        })}
      </div>
      {error ? <p className="mt-1 text-sm text-red-600">{error}</p>
        : hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </fieldset>
  );
}

/** Free-text list (keywords, skills). Enter or comma adds; duplicates are ignored. */
export function TagInput({ label, value, onChange, placeholder, error, hint, maxItems = 100 }: {
  label: string; value: string[]; onChange: (value: string[]) => void; placeholder?: string;
  error?: string; hint?: ReactNode; maxItems?: number;
}) {
  const [draft, setDraft] = useState("");
  const id = useId();

  const add = (raw: string) => {
    const items = raw.split(",").map((s) => s.trim()).filter(Boolean);
    const next = [...value];
    for (const item of items) {
      if (next.length >= maxItems) break;
      if (!next.some((v) => v.toLowerCase() === item.toLowerCase())) next.push(item);
    }
    if (next.length !== value.length) onChange(next);
    setDraft("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <div className={cx("flex flex-wrap items-center gap-1.5 rounded-lg bg-white px-2 py-1.5 shadow-sm ring-1 ring-inset",
        "focus-within:ring-2 focus-within:ring-brand-600", error ? "ring-red-400" : "ring-slate-300")}>
        {value.map((item) => (
          <span key={item} className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-sm text-slate-700">
            {item}
            <button type="button" aria-label={`Remove ${item}`} onClick={() => onChange(value.filter((v) => v !== item))}
                    className="text-slate-400 hover:text-slate-700"><X className="h-3.5 w-3.5" /></button>
          </span>
        ))}
        <input id={id} value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={onKeyDown}
               onBlur={() => draft && add(draft)} placeholder={value.length ? "" : placeholder}
               className="min-w-[8rem] flex-1 border-0 bg-transparent p-1 text-sm focus:outline-none focus:ring-0" />
      </div>
      {error ? <p className="mt-1 text-sm text-red-600">{error}</p>
        : <p className="mt-1 text-xs text-slate-500">{hint ?? "Press Enter or comma to add."}</p>}
    </div>
  );
}
