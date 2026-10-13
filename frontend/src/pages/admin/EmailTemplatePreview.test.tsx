import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EmailTemplatePreview, renderTemplate } from "./EmailTemplatePreview";

function mockPreview(html: string) {
  const calls: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
    calls.push(JSON.parse(String(init?.body)));
    return new Response(JSON.stringify({ success: true, data: { html, text: "" } }), { status: 200 });
  }));
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe("EmailTemplatePreview", () => {
  it("fills placeholders like the server and blanks unknown ones", () => {
    expect(renderTemplate("Hi from {app_name}{missing}!", { app_name: "ApplyXAI" })).toBe("Hi from ApplyXAI!");
  });

  it("shows the plain-text version with the signature and an in-app tab", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
    render(
      <EmailTemplatePreview
        from="ApplyXAI <noreply@applyxai.com>"
        subject="Verify your {app_name} email"
        body={"Confirm here:\n{link}"}
        html=""
        vars={{ app_name: "ApplyXAI", link: "https://applyxai.com/verify-email?token=t" }}
        inApp={{ title: "Welcome to {app_name}", body: "Thanks for joining." }}
      />,
    );
    expect(screen.getByText("Verify your ApplyXAI email")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "https://applyxai.com/verify-email?token=t" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "info@applyxai.com" })).toHaveAttribute("href", "mailto:info@applyxai.com");
    expect(screen.getByRole("link", { name: "www.applyxai.com" })).toHaveAttribute("href", "https://www.applyxai.com");
    await userEvent.click(screen.getByRole("tab", { name: "In-app notification" }));
    expect(screen.getByText("Welcome to ApplyXAI")).toBeInTheDocument();
  });

  it("shows the server's branded HTML in a sandboxed frame", async () => {
    const calls = mockPreview('<html><body><img alt="ApplyXAI"><p>Hello X</p></body></html>');
    render(
      <EmailTemplatePreview from="ApplyXAI" subject="S" body="Plain" html="<p>Hello {app_name}</p>" vars={{ app_name: "X" }} />,
    );
    const frame = await screen.findByTitle("Email HTML preview");
    expect(frame).toHaveAttribute("sandbox", "");
    expect(frame.getAttribute("srcdoc")).toContain("<p>Hello X</p>");
    expect(calls).toEqual([{ subject: "S", body: "Plain", html: "<p>Hello X</p>" }]);
    await userEvent.click(screen.getByRole("tab", { name: "Plain-text fallback" }));
    expect(screen.getByText(/^Plain\s+Regards,/)).toBeInTheDocument();
  });
});
