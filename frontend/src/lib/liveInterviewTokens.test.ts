import { describe, expect, it } from "vitest";
import { latestPaymentLink, pickUsableToken } from "./liveInterviewTokens";
import type { SupportMessage } from "../types";

const msg = (partial: Partial<SupportMessage> & Pick<SupportMessage, "id" | "kind">): SupportMessage => ({
  sender: "system",
  body: "",
  meta: {},
  created_at: null,
  ...partial,
});

describe("liveInterviewTokens", () => {
  it("picks the latest unused token", () => {
    const messages: SupportMessage[] = [
      msg({ id: "1", kind: "token", meta: { token: "11111111", token_status: "used" } }),
      msg({ id: "2", kind: "token", meta: { token: "22222222", token_status: "unused" } }),
      msg({ id: "3", kind: "token", meta: { token: "33333333", token_status: "reserved" } }),
    ];
    expect(pickUsableToken(messages)?.code).toBe("33333333");
  });

  it("finds the latest payment link", () => {
    const messages: SupportMessage[] = [
      msg({ id: "a", kind: "payment_link", meta: { url: "https://pay/old" } }),
      msg({ id: "b", kind: "payment_link", meta: { url: "https://pay/new" } }),
    ];
    expect(latestPaymentLink(messages)).toBe("https://pay/new");
  });
});
