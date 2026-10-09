import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { storedNext } from "../auth/session";
import { RegisterPage } from "./auth";

const ok = (data: unknown) => new Response(JSON.stringify({ success: true, data }), { status: 200 });

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("register next", () => {
  it("keeps the invite path after creating an account", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ok({ message: "ok", verification_required: true })));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/register?next=/invite/tok1"]}>
          <Routes>
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/check-email" element={<p>check email</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.type(screen.getByLabelText("Email"), "student@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse");
    await userEvent.type(screen.getByLabelText("Confirm password"), "correct horse");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("check email")).toBeInTheDocument();
    expect(storedNext()).toBe("/invite/tok1");
  });
});
