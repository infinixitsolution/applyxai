import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApplicationsPage } from "./Applications";

const ok = (data: unknown) => new Response(JSON.stringify({ success: true, data }), { status: 200 });

const listItem = {
  id: "app1",
  status: "applied",
  applied_at: "2026-10-10T08:00:00Z",
  failure_reason: "",
  resume_id: "res1",
  automation_job_id: null,
  created_at: "2026-10-10T07:00:00Z",
  updated_at: "2026-10-10T08:00:00Z",
  job: {
    id: "job1", platform: "linkedin", external_id: "4392", title: "AI Engineer", company: "Hired",
    location: "India", job_url: "https://www.linkedin.com/jobs/view/4392", work_setting: "Remote",
    employment_type: "Full-time", experience_level: "Mid", salary_min: null, salary_max: null,
    discovered_at: "2026-10-10T07:00:00Z",
  },
  resume: {
    id: "res1", name: "Ada_AI Engineer_Hired_5 years", filename: "Ada_AI Engineer_Hired_5 years.docx",
    file_type: "docx", created_at: "2026-10-10T07:30:00Z", generated_by: "ai",
    job_title: "AI Engineer", company: "Hired", match_score: 82, fit_score: 76,
  },
  generated_resumes: [],
};

afterEach(() => vi.unstubAllGlobals());

describe("application view", () => {
  it("opens a popup that shows the resume added for the job", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/applications/app1")) {
        return ok({ ...listItem, job: { ...listItem.job, description: "Build models." } });
      }
      return ok({ items: [listItem], total: 1, page: 1, page_size: 20 });
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ApplicationsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("button", { name: "View" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "View" }));
    await waitFor(() => expect(document.querySelector("dialog")?.textContent).toContain("Resume added"));
    const dialog = document.querySelector("dialog");
    expect(dialog?.textContent).toContain("Resume added");
    expect(dialog?.textContent).toContain("Ada_AI Engineer_Hired_5 years");
    expect(dialog?.textContent).toContain("Prepared for AI Engineer at Hired");
    expect(Array.from(dialog?.querySelectorAll("a") ?? []).some((link) => link.getAttribute("href")?.includes("res1"))).toBe(true);
  });

  it("opens a resume popup from the attachment icon next to the date", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ok({ items: [listItem], total: 1, page: 1, page_size: 20 })));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ApplicationsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Open resume Ada_AI Engineer_Hired_5 years" }));
    await waitFor(() => expect(document.querySelector("dialog")?.textContent).toContain("Download resume"));
    const dialog = document.querySelector("dialog");
    expect(dialog?.textContent).toContain("Resume");
    expect(dialog?.querySelector("a")?.getAttribute("href")).toContain("res1");
  });
});
