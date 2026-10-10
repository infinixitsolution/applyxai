import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AgentConnectPage } from "./AgentConnect";

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
});
