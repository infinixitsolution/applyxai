import { useMemo } from "react";
import { Select, TextInput } from "../components/form";
import {
  CUSTOM_ANSWER,
  formatForQuestion,
  numericPresetsForLabel,
  textPresetsForLabel,
} from "../lib/questionAnswerFormat";
import type { PendingFormQuestion } from "../types";

function usableOptions(options: string[]): string[] {
  return options.filter((o) => {
    const t = o.trim().toLowerCase();
    return t.length > 0 && t !== "select an option" && !t.startsWith("select an option");
  });
}

export function PendingQuestionAnswerField({
  q,
  value,
  onChange,
}: {
  q: PendingFormQuestion;
  value: string;
  onChange: (v: string) => void;
}) {
  const fmt = formatForQuestion(q);
  const choiceOpts = usableOptions(q.options);
  const numericPresets = useMemo(() => numericPresetsForLabel(q.label), [q.label]);
  const textPresets = useMemo(() => textPresetsForLabel(q.label), [q.label]);

  if (fmt === "choice") {
    return (
      <Select
        label="Your answer (choose one)"
        value={value}
        onChange={onChange}
        options={[
          { value: "", label: "Choose an option…" },
          ...choiceOpts.map((o) => ({ value: o, label: o })),
        ]}
      />
    );
  }

  if (fmt === "number") {
    const inPreset = numericPresets.includes(value);
    const selectValue = value === "" ? "" : inPreset ? value : CUSTOM_ANSWER;
    return (
      <div className="space-y-3">
        <Select
          label="Expected answer: number"
          value={selectValue}
          onChange={(v) => {
            if (v === "" || v === CUSTOM_ANSWER) {
              if (v === "") onChange("");
              return;
            }
            onChange(v);
          }}
          options={[
            { value: "", label: "Choose a number…" },
            ...numericPresets.map((n) => ({ value: n, label: n })),
            { value: CUSTOM_ANSWER, label: "Other number…" },
          ]}
        />
        {(selectValue === CUSTOM_ANSWER || (value !== "" && !inPreset)) && (
          <TextInput
            label="Custom number"
            inputMode="numeric"
            value={value}
            onChange={onChange}
            placeholder="Digits only"
          />
        )}
      </div>
    );
  }

  if (textPresets.length > 0) {
    const inPreset = textPresets.includes(value);
    const selectValue = value === "" ? "" : inPreset ? value : CUSTOM_ANSWER;
    return (
      <div className="space-y-3">
        <Select
          label="Expected answer: text"
          value={selectValue}
          onChange={(v) => {
            if (v === "" || v === CUSTOM_ANSWER) {
              if (v === "") onChange("");
              return;
            }
            onChange(v);
          }}
          options={[
            { value: "", label: "Choose a quick answer…" },
            ...textPresets.map((t) => ({ value: t, label: t })),
            { value: CUSTOM_ANSWER, label: "Custom text…" },
          ]}
        />
        {(selectValue === CUSTOM_ANSWER || (value !== "" && !inPreset)) && (
          <TextInput label="Custom answer" value={value} onChange={onChange} placeholder="Type your answer" />
        )}
      </div>
    );
  }

  return (
    <TextInput
      label="Your answer for next time"
      value={value}
      onChange={onChange}
      placeholder="Type your answer"
    />
  );
}
