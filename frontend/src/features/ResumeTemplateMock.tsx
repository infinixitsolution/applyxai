import type { ResumeTemplate } from "../types";
import { templateFontStack } from "./resumeTemplateFonts";
import { renderTemplateLayout } from "./resumeTemplateLayouts";

type Props = {
  template: ResumeTemplate;
  displayName?: string;
  variant?: "thumb" | "full";
};

export function ResumeTemplateMock({ template, displayName = "Alex Morgan", variant = "full" }: Props) {
  const compact = variant === "thumb";
  const mockProps = {
    template,
    displayName,
    compact,
    headingFont: templateFontStack(template.heading_font),
    bodyFont: templateFontStack(template.body_font),
    accent: template.accent,
  };

  return (
    <div
      className={
        "bg-white text-left shadow-inner " +
        (compact ? "pointer-events-none origin-top-left scale-[0.38] p-3" : "rounded-lg p-6 ring-1 ring-slate-200")
      }
      style={{
        minHeight: compact ? 0 : undefined,
        width: compact ? 260 : undefined,
      }}
    >
      {renderTemplateLayout(mockProps)}
    </div>
  );
}
