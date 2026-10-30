import { resolveAgentCredentials } from "./agentToken";
import { PRODUCT_VERSION } from "./productVersion";

const DESKTOP_USER_AGENT = `ApplyXAI-Desktop/${PRODUCT_VERSION}`;

export type LiveInterviewSessionPayload = {
  id: string;
  transcript?: { role: string; text: string; at?: string }[];
  started_at?: string | null;
};

async function agentFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { server, token } = await resolveAgentCredentials();
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  headers.set("Accept", "application/json");
  if (!headers.has("User-Agent")) headers.set("User-Agent", DESKTOP_USER_AGENT);
  return fetch(`${server}/api/agent${path}`, { ...init, headers });
}

async function parseJson<T>(resp: Response): Promise<T> {
  const body = (await resp.json()) as { success?: boolean; data?: T; error?: { message?: string } };
  if (!resp.ok || body.success === false) {
    throw new Error(body.error?.message || `Request failed (${resp.status})`);
  }
  return body.data as T;
}

export async function liveInterviewStart(
  token: string,
  applicationId: string | null,
): Promise<LiveInterviewSessionPayload> {
  const body: { token: string; application_id?: string } = { token: token.replace(/\D/g, "").slice(0, 8) };
  if (applicationId) body.application_id = applicationId;
  const resp = await agentFetch("/live-interview/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson(resp);
}

export async function liveInterviewClip(sessionId: string, speaker: string, wav: Buffer): Promise<{
  transcript?: { role: string; text: string; at?: string }[];
  answer_pending?: boolean;
}> {
  const form = new FormData();
  form.append("speaker", speaker);
  form.append("defer_answer", "true");
  form.append("file", new Blob([new Uint8Array(wav)]), "clip.wav");
  const resp = await agentFetch(`/live-interview/sessions/${sessionId}/clip`, {
    method: "POST",
    body: form,
  });
  return parseJson(resp);
}

export async function* liveInterviewAnswerStream(sessionId: string): AsyncGenerator<string> {
  const { server, token } = await resolveAgentCredentials();
  const resp = await fetch(`${server}/api/agent/live-interview/sessions/${sessionId}/answer-stream`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "text/plain",
      "User-Agent": DESKTOP_USER_AGENT,
    },
  });
  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => "");
    throw new Error(text || `Answer stream failed (${resp.status})`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value) yield decoder.decode(value, { stream: true });
  }
}

export async function liveInterviewEnd(sessionId: string): Promise<void> {
  const resp = await agentFetch(`/live-interview/sessions/${sessionId}/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  await parseJson(resp);
}

export async function isAgentLinked(): Promise<boolean> {
  try {
    await resolveAgentCredentials();
    return true;
  } catch {
    return false;
  }
}
