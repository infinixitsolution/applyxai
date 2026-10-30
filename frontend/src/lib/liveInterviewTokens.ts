import type { SupportMessage } from "../types";

export type ParsedInterviewToken = {
  code: string;
  status: "unused" | "reserved" | "used";
  messageId: string;
};

/** Latest token that can still start (or resume) an interview. */
export function pickUsableToken(messages: SupportMessage[]): ParsedInterviewToken | null {
  let chosen: ParsedInterviewToken | null = null;
  for (const message of messages) {
    if (message.kind !== "token" || !message.meta.token) continue;
    const digits = message.meta.token.replace(/\D/g, "");
    if (digits.length !== 8) continue;
    const status = message.meta.token_status ?? "unused";
    if (status === "used") continue;
    chosen = { code: digits, status, messageId: message.id };
  }
  return chosen;
}

export function latestPaymentLink(messages: SupportMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.kind === "payment_link" && message.meta.url) return message.meta.url;
  }
  return null;
}
