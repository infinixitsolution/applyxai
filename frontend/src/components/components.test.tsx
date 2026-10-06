import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { LoginPage } from "../pages/auth";
import { ChipSelect, TagInput } from "./form";
import { ToastProvider } from "./Toast";

function Chips({ initial = [] as string[] }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <ChipSelect label="Job type" options={["Full-time", "Part-time", "Contract"]} value={value} onChange={setValue} />
      <output data-testid="value">{JSON.stringify(value)}</output>
    </>
  );
}

function Tags() {
  const [value, setValue] = useState<string[]>([]);
  return (
    <>
      <TagInput label="Keywords" value={value} onChange={setValue} />
      <output data-testid="value">{JSON.stringify(value)}</output>
    </>
  );
}

describe("ChipSelect", () => {
  it("toggles exact option values and keeps the option order", async () => {
    const user = userEvent.setup();
    render(<Chips />);
    await user.click(screen.getByRole("button", { name: "Contract" }));
    await user.click(screen.getByRole("button", { name: "Full-time" }));
    expect(screen.getByTestId("value")).toHaveTextContent('["Full-time","Contract"]');
    expect(screen.getByRole("button", { name: "Contract" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Contract" }));
    expect(screen.getByTestId("value")).toHaveTextContent('["Full-time"]');
  });
});

describe("TagInput", () => {
  it("adds on Enter/comma, trims, ignores duplicates, and removes", async () => {
    const user = userEvent.setup();
    render(<Tags />);
    const input = screen.getByLabelText("Keywords");
    await user.type(input, " Python Developer {enter}");
    await user.type(input, "python developer,Backend,");
    expect(screen.getByTestId("value")).toHaveTextContent('["Python Developer","Backend"]');
    await user.click(screen.getByRole("button", { name: "Remove Backend" }));
    expect(screen.getByTestId("value")).toHaveTextContent('["Python Developer"]');
  });
});

describe("LoginPage", () => {
  function renderLogin() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={client}>
        <MemoryRouter><ToastProvider><LoginPage /></ToastProvider></MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("shows the server's error message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(
      { success: false, error: { code: "INVALID_CREDENTIALS", message: "Incorrect email or password." } }), { status: 401 })));
    const user = userEvent.setup();
    renderLogin();
    await user.type(screen.getByLabelText("Email"), "a@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong password!");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
    vi.unstubAllGlobals();
  });

  it("offers a new verification link for unverified accounts", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(
        { success: false, error: { code: "EMAIL_NOT_VERIFIED", message: "Please verify your email." } }), { status: 403 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ success: true, data: { message: "sent" } }), { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderLogin();
    await user.type(screen.getByLabelText("Email"), "a@example.com");
    await user.type(screen.getByLabelText("Password"), "correct horse battery");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    await user.click(await screen.findByRole("button", { name: "Send a new link" }));
    expect(await screen.findByText("We've sent a new link.")).toBeInTheDocument();
    expect(fetchMock.mock.calls[1][0]).toBe("/api/auth/resend-verification");
    vi.unstubAllGlobals();
  });
});
