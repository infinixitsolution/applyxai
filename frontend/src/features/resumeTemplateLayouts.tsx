import type { CSSProperties, ReactNode } from "react";
import type { ResumeTemplate } from "../types";
import { templateFontStack } from "./resumeTemplateFonts";

export type MockProps = {
  template: ResumeTemplate;
  displayName: string;
  compact: boolean;
  headingFont: string;
  bodyFont: string;
  accent: string;
};

function Section({
  title,
  children,
  compact,
  headingFont,
  accent,
  titleStyle,
}: {
  title: string;
  children: ReactNode;
  compact: boolean;
  headingFont: string;
  accent: string;
  titleStyle?: CSSProperties;
}) {
  return (
    <div style={{ marginBottom: compact ? 6 : 12 }}>
      <p
        className="font-semibold"
        style={{
          fontFamily: headingFont,
          fontSize: compact ? 10 : 12,
          color: accent,
          marginBottom: compact ? 2 : 4,
          ...titleStyle,
        }}
      >
        {title}
      </p>
      {children}
    </div>
  );
}

function Body({ compact, bodyFont, children }: { compact: boolean; bodyFont: string; children: ReactNode }) {
  return (
    <div style={{ fontFamily: bodyFont, fontSize: compact ? 10 : 13, lineHeight: compact ? 1.35 : 1.45, color: "#334155" }}>
      {children}
    </div>
  );
}

function ExperienceBlock({ compact }: { compact: boolean }) {
  return (
    <>
      <p className="font-medium" style={{ color: "#1e293b" }}>Software Engineer · Acme Corp</p>
      <p style={{ fontSize: compact ? 9 : 11, color: "#64748b" }}>2021 – Present</p>
      <ul className="list-disc pl-4" style={{ marginTop: compact ? 2 : 4 }}>
        <li>Shipped billing APIs used by 40k monthly active users.</li>
        {!compact && <li>Cut deployment time by introducing CI pipelines on AWS.</li>}
      </ul>
    </>
  );
}

export function LayoutRuledUnderline(p: MockProps) {
  const rule = { borderBottom: `2px solid ${p.accent}`, paddingBottom: 2, marginBottom: p.compact ? 4 : 6 };
  return (
    <Body compact={p.compact} bodyFont={p.bodyFont}>
      <p className="font-bold" style={{ fontFamily: p.headingFont, fontSize: p.compact ? 16 : 22, color: p.accent }}>
        {p.displayName}
      </p>
      <p style={{ fontSize: p.compact ? 9 : 11, color: "#64748b", marginBottom: p.compact ? 6 : 10 }}>alex@email.com · Bengaluru</p>
      <Section title="Summary" compact={p.compact} headingFont={p.headingFont} accent={p.accent} titleStyle={rule}>
        Backend engineer with 5 years building APIs in Python and PostgreSQL.
      </Section>
      <Section title="Skills" compact={p.compact} headingFont={p.headingFont} accent={p.accent} titleStyle={rule}>
        Python, Django, PostgreSQL, AWS
      </Section>
      <Section title="Experience" compact={p.compact} headingFont={p.headingFont} accent={p.accent} titleStyle={rule}>
        <ExperienceBlock compact={p.compact} />
      </Section>
    </Body>
  );
}

export function LayoutLeftAccentBar(p: MockProps) {
  const bar = { borderLeft: `4px solid ${p.accent}`, paddingLeft: 8 };
  return (
    <Body compact={p.compact} bodyFont={p.bodyFont}>
      <p className="font-bold" style={{ fontFamily: p.headingFont, fontSize: p.compact ? 16 : 22, color: p.accent }}>{p.displayName}</p>
      <p style={{ fontSize: p.compact ? 9 : 11, color: "#64748b", marginBottom: p.compact ? 6 : 10 }}>alex@email.com · Bengaluru</p>
      {(["Summary", "Skills", "Experience"] as const).map((title) => (
        <div key={title} style={{ marginBottom: p.compact ? 6 : 10 }}>
          <p className="font-semibold" style={{ ...bar, fontFamily: p.headingFont, color: p.accent, fontSize: p.compact ? 10 : 12 }}>
            {title}
          </p>
          <div style={{ paddingLeft: 12, marginTop: 4 }}>
            {title === "Summary" && "Backend engineer with 5 years building APIs."}
            {title === "Skills" && "Python, Django, PostgreSQL, AWS"}
            {title === "Experience" && <ExperienceBlock compact={p.compact} />}
          </div>
        </div>
      ))}
    </Body>
  );
}

export function LayoutAiryDivider(p: MockProps) {
  return (
    <Body compact={p.compact} bodyFont={p.bodyFont}>
      <p className="font-bold" style={{ fontFamily: p.headingFont, fontSize: p.compact ? 15 : 20, color: "#475569" }}>{p.displayName}</p>
      <p style={{ fontSize: p.compact ? 9 : 11, color: "#94a3b8", marginBottom: p.compact ? 8 : 14 }}>alex@email.com</p>
      {(["Summary", "Skills", "Experience"] as const).map((title) => (
        <div key={title} style={{ marginTop: p.compact ? 8 : 14, paddingTop: p.compact ? 4 : 8, borderTop: "1px solid #e2e8f0" }}>
          <p style={{ fontSize: p.compact ? 9 : 11, letterSpacing: "0.08em", textTransform: "uppercase", color: "#64748b" }}>{title}</p>
          <div style={{ marginTop: 4 }}>
            {title === "Summary" && "Backend engineer with 5 years building APIs."}
            {title === "Skills" && "Python, Django, PostgreSQL"}
            {title === "Experience" && <ExperienceBlock compact={p.compact} />}
          </div>
        </div>
      ))}
    </Body>
  );
}

export function LayoutCenteredName(p: MockProps) {
  return (
    <Body compact={p.compact} bodyFont={p.bodyFont}>
      <p className="text-center font-bold" style={{ fontFamily: p.headingFont, fontSize: p.compact ? 16 : 22, color: p.accent }}>{p.displayName}</p>
      <p className="text-center" style={{ fontSize: p.compact ? 9 : 11, color: "#64748b", marginBottom: p.compact ? 8 : 12 }}>alex@email.com · Bengaluru</p>
      {(["Summary", "Skills", "Experience"] as const).map((title) => (
        <div key={title} className="text-center" style={{ marginBottom: p.compact ? 6 : 10 }}>
          <p className="font-semibold" style={{ fontFamily: p.headingFont, color: p.accent, borderBottom: `2px solid ${p.accent}`, display: "inline-block", paddingBottom: 2 }}>
            {title}
          </p>
          <p style={{ marginTop: 4, textAlign: "left" }}>
            {title === "Summary" && "Backend engineer with 5 years building APIs."}
            {title === "Skills" && "Python, Django, PostgreSQL"}
            {title === "Experience" && <ExperienceBlock compact={p.compact} />}
          </p>
        </div>
      ))}
    </Body>
  );
}

export function LayoutTightBlocks(p: MockProps) {
  return (
    <Body compact={p.compact} bodyFont={p.bodyFont}>
      <p className="font-bold uppercase" style={{ fontFamily: p.headingFont, fontSize: p.compact ? 14 : 18, color: p.accent }}>{p.displayName}</p>
      <p style={{ fontSize: p.compact ? 8 : 10, color: "#64748b" }}>alex@email.com · +1 555 0100 · Bengaluru</p>
      <p style={{ marginTop: 4 }}><strong style={{ color: p.accent }}>Summary:</strong> Backend engineer, 5 years, Python/PostgreSQL.</p>
      <p><strong style={{ color: p.accent }}>Skills:</strong> Python, Django, AWS, Docker</p>
      <p style={{ marginTop: 4 }}><strong style={{ color: p.accent }}>Experience:</strong> Software Engineer, Acme Corp (2021–Present)</p>
    </Body>
  );
}

export function LayoutCenteredSerif(p: MockProps) {
  return (
    <Body compact={p.compact} bodyFont={p.bodyFont}>
      <p className="text-center font-bold" style={{ fontFamily: p.headingFont, fontSize: p.compact ? 17 : 24, color: p.accent }}>{p.displayName}</p>
      <p className="text-center italic" style={{ fontSize: p.compact ? 9 : 11, color: "#78716c", marginBottom: p.compact ? 8 : 12 }}>Backend engineer · Bengaluru</p>
      {(["Summary", "Skills", "Experience"] as const).map((title) => (
        <div key={title} style={{ marginBottom: p.compact ? 6 : 10 }}>
          <p className="text-center italic" style={{ fontFamily: p.headingFont, color: p.accent, fontSize: p.compact ? 10 : 13 }}>{title}</p>
          <p style={{ marginTop: 4 }}>
            {title === "Summary" && "Five years building reliable APIs and data services."}
            {title === "Skills" && "Python, Django, PostgreSQL"}
            {title === "Experience" && <ExperienceBlock compact={p.compact} />}
          </p>
        </div>
      ))}
    </Body>
  );
}

export function LayoutNameBanner(p: MockProps) {
  return (
    <Body compact={p.compact} bodyFont={p.bodyFont}>
      <div className="rounded-sm px-3 py-2 text-white" style={{ backgroundColor: p.accent, marginBottom: p.compact ? 6 : 10 }}>
        <p className="font-bold uppercase" style={{ fontFamily: p.headingFont, fontSize: p.compact ? 14 : 20 }}>{p.displayName}</p>
      </div>
      <p style={{ fontSize: p.compact ? 9 : 11, color: "#64748b" }}>alex@email.com · Bengaluru</p>
      {(["Summary", "Skills", "Experience"] as const).map((title) => (
        <div key={title} style={{ marginTop: p.compact ? 4 : 8 }}>
          <p className="font-bold uppercase tracking-wide" style={{ color: p.accent, fontSize: p.compact ? 9 : 11 }}>{title}</p>
          <div style={{ marginTop: 2 }}>
            {title === "Summary" && "Backend engineer with 5 years experience."}
            {title === "Skills" && "Python, Django, PostgreSQL"}
            {title === "Experience" && <ExperienceBlock compact={p.compact} />}
          </div>
        </div>
      ))}
    </Body>
  );
}

export function LayoutSkillsPanel(p: MockProps) {
  return (
    <div className="grid gap-2" style={{ gridTemplateColumns: p.compact ? "1fr" : "1fr 1.4fr", fontFamily: p.bodyFont, fontSize: p.compact ? 10 : 13 }}>
      <div className="rounded-md p-2" style={{ backgroundColor: "#f1f5f9", borderLeft: `4px solid ${p.accent}` }}>
        <p className="font-semibold" style={{ fontFamily: p.headingFont, color: p.accent, fontSize: p.compact ? 10 : 12 }}>Skills</p>
        <p style={{ marginTop: 4, fontFamily: templateFontStack("Consolas"), fontSize: p.compact ? 9 : 11 }}>Python<br />Django<br />PostgreSQL<br />AWS</p>
      </div>
      <div>
        <p className="font-bold" style={{ fontFamily: p.headingFont, fontSize: p.compact ? 15 : 20, color: p.accent }}>{p.displayName}</p>
        <p style={{ fontSize: p.compact ? 9 : 11, color: "#64748b" }}>alex@email.com</p>
        <Section title="Summary" compact={p.compact} headingFont={p.headingFont} accent={p.accent}>
          Backend engineer with 5 years building APIs.
        </Section>
        <Section title="Experience" compact={p.compact} headingFont={p.headingFont} accent={p.accent}>
          <ExperienceBlock compact={p.compact} />
        </Section>
      </div>
    </div>
  );
}

export function LayoutMarginStripe(p: MockProps) {
  return (
    <div style={{ borderLeft: `6px solid ${p.accent}`, paddingLeft: p.compact ? 8 : 14, fontFamily: p.bodyFont, fontSize: p.compact ? 10 : 13, color: "#334155" }}>
      <p className="font-bold" style={{ fontFamily: p.headingFont, fontSize: p.compact ? 16 : 22, color: p.accent }}>{p.displayName}</p>
      <p style={{ fontSize: p.compact ? 9 : 11, color: "#64748b", marginBottom: p.compact ? 6 : 10 }}>alex@email.com · Bengaluru</p>
      <Section title="Summary" compact={p.compact} headingFont={p.headingFont} accent={p.accent}>Backend engineer with 5 years building APIs.</Section>
      <Section title="Skills" compact={p.compact} headingFont={p.headingFont} accent={p.accent}>Python, Django, PostgreSQL</Section>
      <Section title="Experience" compact={p.compact} headingFont={p.headingFont} accent={p.accent}><ExperienceBlock compact={p.compact} /></Section>
    </div>
  );
}

export function LayoutExecutiveSplit(p: MockProps) {
  return (
    <Body compact={p.compact} bodyFont={p.bodyFont}>
      <div className="flex items-start justify-between gap-2" style={{ marginBottom: p.compact ? 6 : 10 }}>
        <p className="font-bold" style={{ fontFamily: p.headingFont, fontSize: p.compact ? 15 : 22, color: p.accent }}>{p.displayName}</p>
        <p className="text-right" style={{ fontSize: p.compact ? 8 : 10, color: "#64748b", lineHeight: 1.3 }}>
          alex@email.com<br />+1 555 0100<br />Bengaluru
        </p>
      </div>
      {(["Summary", "Skills", "Experience"] as const).map((title) => (
        <div key={title} style={{ marginBottom: p.compact ? 6 : 10, borderBottom: "1px solid #cbd5e1", paddingBottom: 4 }}>
          <p className="font-semibold" style={{ fontFamily: p.headingFont, color: p.accent, fontSize: p.compact ? 10 : 12 }}>{title}</p>
          <div style={{ marginTop: 4 }}>
            {title === "Summary" && "Backend engineer with 5 years leading API delivery."}
            {title === "Skills" && "Python, Django, PostgreSQL, AWS"}
            {title === "Experience" && <ExperienceBlock compact={p.compact} />}
          </div>
        </div>
      ))}
    </Body>
  );
}

const LAYOUTS: Record<string, (p: MockProps) => ReactNode> = {
  ruled_underline: LayoutRuledUnderline,
  left_accent_bar: LayoutLeftAccentBar,
  airy_divider: LayoutAiryDivider,
  centered_name: LayoutCenteredName,
  tight_blocks: LayoutTightBlocks,
  centered_serif: LayoutCenteredSerif,
  name_banner: LayoutNameBanner,
  skills_panel: LayoutSkillsPanel,
  margin_stripe: LayoutMarginStripe,
  executive_split: LayoutExecutiveSplit,
};

export function renderTemplateLayout(props: MockProps): ReactNode {
  const layout = props.template.layout || "left_accent_bar";
  const Render = LAYOUTS[layout] ?? LayoutLeftAccentBar;
  return Render(props);
}
