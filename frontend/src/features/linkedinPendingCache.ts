import type { QueryClient } from "@tanstack/react-query";
import type { ApplicationPreferencesOut } from "../types";

export function patchPendingQuestionsCache(
  client: QueryClient,
  updater: (pending: ApplicationPreferencesOut["pending_form_questions"]) => ApplicationPreferencesOut["pending_form_questions"],
) {
  client.setQueryData<ApplicationPreferencesOut>(["preferences", "application"], (old) => {
    if (!old) return old;
    return { ...old, pending_form_questions: updater(old.pending_form_questions ?? []) };
  });
}

export function removePendingIds(client: QueryClient, ids: string[]) {
  const drop = new Set(ids);
  patchPendingQuestionsCache(client, (list) => list.filter((q) => !drop.has(q.id)));
}
