import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/Toast";
import type { Partner } from "../../types";
import { PartnerKycPage, PartnerProfilePage, PartnerReferralsPage, PartnerTaxPage } from "./Pages";

const partner: Partner = {
  id: "p1", user_id: "u3", organization: "West Coast Referral", contact_name: "Alex West",
  phone: "555", referral_code: "WCR1", status: "approved", kyc_status: "pending",
  commission_mode: "percent_payment", commission_bps: 1000, commission_flat_cents: 0,
  gstin: "27AAAAA0000A1Z5", pan_number: "ABCDE1234F",
  payout_account: "123", payout_ifsc: "HDFC0001",
  kyc_documents: [{ filename: "pan.pdf", note: "PAN card", uploaded_at: "2026-10-09T00:00:00+00:00" }],
  click_count: 4, wallet: { accrued_cents: 0, approved_cents: 0, available_cents: 0 },
  created_at: "2026-10-09T00:00:00+00:00",
};

const ok = (data: unknown) => new Response(JSON.stringify({ success: true, data }), { status: 200 });

function mockApi(routes: Record<string, unknown | ((init?: RequestInit) => unknown)>) {
  const calls: { key: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
    calls.push({ key, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (!(key in routes)) throw new Error(`unexpected request: ${key}`);
    const value = routes[key];
    return ok(typeof value === "function" ? (value as (i?: RequestInit) => unknown)(init) : value);
  }));
  return calls;
}

function renderPage(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter><ToastProvider>{ui}</ToastProvider></MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("partner portal wiring", () => {
  it("saves bound profile fields", async () => {
    const calls = mockApi({
      "GET /api/partner/me": partner,
      "PUT /api/partner/profile": (init?: RequestInit) => ({ ...partner, ...JSON.parse(String(init?.body)) }),
    });
    renderPage(<PartnerProfilePage />);
    const org = await screen.findByLabelText("Organisation");
    await userEvent.clear(org);
    await userEvent.type(org, "Pacific Referral");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /api/partner/profile")).toBe(true));
    expect(calls.find((c) => c.key === "PUT /api/partner/profile")?.body).toMatchObject({
      organization: "Pacific Referral", contact_name: "Alex West", phone: "555",
    });
  });

  it("saves tax details from initialized fields", async () => {
    const calls = mockApi({
      "GET /api/partner/me": partner,
      "PUT /api/partner/tax": partner,
    });
    renderPage(<PartnerTaxPage />);
    await screen.findByDisplayValue("HDFC0001");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /api/partner/tax")).toBe(true));
    expect(calls.find((c) => c.key === "PUT /api/partner/tax")?.body).toMatchObject({
      gstin: "27AAAAA0000A1Z5", payout_ifsc: "HDFC0001",
    });
  });

  it("records a KYC document with a note", async () => {
    const calls = mockApi({
      "GET /api/partner/me": partner,
      "POST /api/partner/kyc": partner,
    });
    renderPage(<PartnerKycPage />);
    expect(await screen.findByText("pan.pdf")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Document name"), "gst.pdf");
    await userEvent.type(screen.getByLabelText("Note"), "GST certificate");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /api/partner/kyc")).toBe(true));
    expect(calls.find((c) => c.key === "POST /api/partner/kyc")?.body).toMatchObject({
      filename: "gst.pdf", note: "GST certificate",
    });
  });

  it("lists referred campuses on the referrals page", async () => {
    mockApi({
      "GET /api/partner/referrals": {
        referral_code: "WCR1", referral_path: "/r/WCR1", click_count: 4,
        institutes: [{ ...partner, id: "i1", name: "Harbor College", email: "dean@harbor.edu", status: "active" }],
      },
    });
    renderPage(<PartnerReferralsPage />);
    expect(await screen.findByText("Harbor College")).toBeInTheDocument();
    expect(screen.getByText("Code WCR1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy link" })).toBeInTheDocument();
  });
});
