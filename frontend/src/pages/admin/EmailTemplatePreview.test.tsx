import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { EmailTemplatePreview, renderTemplate } from "./EmailTemplatePreview";

describe("EmailTemplatePreview", () => {
  it("fills placeholders like the server and blanks unknown ones", () => {
    expect(renderTemplate("Hi from {app_name}{missing}!", { app_name: "ApplyXAI" })).toBe("Hi from ApplyXAI!");
  });

  it("renders a plain-text email with the sample link and an in-app tab", async () => {
    render(
      <EmailTemplatePreview
        from="ApplyXAI <no-reply@applyxai.com>"
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

  it("shows HTML in a sandboxed frame with a plain-text tab", () => {
    render(
      <EmailTemplatePreview from="ApplyXAI" subject="S" body="Plain" html="<p>Hello {app_name}</p>" vars={{ app_name: "X" }} />,
    );
    const frame = screen.getByTitle("Email HTML preview");
    expect(frame).toHaveAttribute("sandbox", "");
    const srcdoc = frame.getAttribute("srcdoc") ?? "";
    expect(srcdoc.startsWith("<p>Hello X</p>")).toBe(true);
    expect(srcdoc).toContain("info@applyxai.com");
    expect(screen.getByRole("tab", { name: "Plain-text fallback" })).toBeInTheDocument();
  });
});
