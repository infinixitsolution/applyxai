import type { FieldMeta } from "../types";
import { ChipSelect, Select, TagInput, TextArea, TextInput } from "./form";

/** Form state for engine settings: numbers are edited as strings, unset values are "" (or [] for lists). */
export type DraftValue = string | string[];

export function toDraft(field: FieldMeta, value: unknown): DraftValue {
  if (field.type === "list") return Array.isArray(value) ? value.map(String) : [];
  if (field.type === "bool") return value === true ? "true" : value === false ? "false" : "";
  return value === undefined || value === null ? "" : String(value);
}

/** Draft -> API value. `null` means "not set" (the engine default applies). Throws with a user message. */
export function fromDraft(field: FieldMeta, draft: DraftValue): unknown {
  if (field.type === "list") return (draft as string[]).length ? draft : null;
  const text = (draft as string).trim();
  if (field.type === "bool") return text === "" ? null : text === "true";
  if (field.type === "number") {
    if (text === "") return null;
    if (!/^-?\d+$/.test(text)) throw new Error("Enter a whole number.");
    return Number.parseInt(text, 10);
  }
  if (field.type === "select") {
    return text === "" && !(field.options ?? []).includes("") ? null : text;
  }
  return text === "" ? null : text;
}

export function sameValue(a: unknown, b: unknown): boolean {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

const SELECT_EMPTY_LABEL = "Not set (use default)";

export function DynamicField({ field, value, onChange, error }:
  { field: FieldMeta; value: DraftValue; onChange: (value: DraftValue) => void; error?: string }) {
  const hint = field.help || undefined;
  switch (field.type) {
    case "bool":
      return (
        <Select label={field.label} hint={hint} error={error} value={value as string} onChange={onChange}
                options={[{ value: "", label: SELECT_EMPTY_LABEL }, { value: "true", label: "Yes" }, { value: "false", label: "No" }]} />
      );
    case "select": {
      const options = field.options ?? [];
      const choices = [
        ...(options.includes("") ? [] : [{ value: "", label: SELECT_EMPTY_LABEL }]),
        ...options.map((o) => ({ value: o, label: o === "" ? "Leave unanswered" : o })),
      ];
      return <Select label={field.label} hint={hint} error={error} value={value as string} onChange={onChange} options={choices} />;
    }
    case "list":
      return field.options
        ? <ChipSelect label={field.label} hint={hint} error={error} options={field.options} value={value as string[]} onChange={onChange} />
        : <TagInput label={field.label} hint={hint} error={error} value={value as string[]} onChange={onChange} />;
    case "number":
      return <TextInput label={field.label} hint={hint} error={error} inputMode="numeric" value={value as string} onChange={onChange} />;
    case "textarea":
      return <TextArea label={field.label} hint={hint} error={error} value={value as string} onChange={onChange} maxLength={10000} />;
    default:
      return <TextInput label={field.label} hint={hint} error={error} value={value as string} onChange={onChange} maxLength={1000} />;
  }
}
