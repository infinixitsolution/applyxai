import type { HumanQuestion } from "../types";

function patternKey(pattern: string): string {
  return pattern.trim().toLowerCase();
}

function rowScore(row: HumanQuestion): number {
  let score = (row.usage_count ?? 0) * 10;
  if (row.verified) score += 50;
  if (row.answer.trim()) score += 5;
  return score;
}

function later(a?: string | null, b?: string | null): string | undefined {
  if (!a) return b ?? undefined;
  if (!b) return a;
  return a > b ? a : b;
}

function mergePair(a: HumanQuestion, b: HumanQuestion): HumanQuestion {
  const primary = rowScore(b) > rowScore(a) ? b : a;
  const secondary = primary === a ? b : a;
  return {
    ...primary,
    usage_count: Math.max(a.usage_count ?? 0, b.usage_count ?? 0),
    verified: !!(a.verified || b.verified),
    answer: primary.answer.trim() || secondary.answer.trim() || primary.answer,
    company: primary.company || secondary.company,
    job_title: primary.job_title || secondary.job_title,
    last_used_at: later(a.last_used_at, b.last_used_at),
  };
}

/** Collapse rows that share the same question pattern (case-insensitive). Empty patterns are kept as-is. */
export function mergeDuplicateQuestions(rows: HumanQuestion[]): HumanQuestion[] {
  const emptyRows: HumanQuestion[] = [];
  const byPattern = new Map<string, HumanQuestion>();

  for (const row of rows) {
    const key = patternKey(row.pattern);
    if (!key) {
      emptyRows.push(row);
      continue;
    }
    const existing = byPattern.get(key);
    byPattern.set(key, existing ? mergePair(existing, row) : { ...row });
  }

  return [...byPattern.values(), ...emptyRows];
}

export function findDuplicatePatterns(rows: HumanQuestion[]): HumanQuestion[] {
  return rows.filter(
    (r, i) =>
      patternKey(r.pattern) &&
      rows.findIndex((x) => patternKey(x.pattern) === patternKey(r.pattern)) !== i,
  );
}
