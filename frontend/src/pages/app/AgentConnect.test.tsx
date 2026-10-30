import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgentConnectPage } from "./AgentConnect";

const ok = (data: unknown) => new Response(JSON.stringify({ success: true, data }), { status: 200 });

afterEach(() => vi.unstubAllGlobals());

describe("AgentConnectPage", () => {
  it("shows error when connect session is missing", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/app/agent-connect"]}>
          <AgentConnectPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/invalid connect link/i)).toBeTruthy();
  });

  it("approves a valid connect session", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/automation/devices/connect/approve") && String(init?.method || "").toUpperCase() === "POST") {
        return ok({ ok: true, device_name: "Office PC" });
      }
      throw new Error(`${init?.method} ${url}`);
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/app/agent-connect?session=11111111-1111-1111-1111-111111111111"]}>
          <AgentConnectPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Connected")).toBeTruthy();
    expect(screen.getByRole("link", { name: /open automation/i })).toBeTruthy();
  });
});
