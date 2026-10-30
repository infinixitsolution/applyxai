import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImagePlus } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { TextInput } from "../../../components/form";
import { RichHtmlEditor } from "../../../components/RichHtmlEditor";
import { useToast } from "../../../components/Toast";
import { editorHtmlToPlainText, plainTextToEditorHtml } from "../../../lib/outreachTemplateHtml";
import { Alert, Button, Card, PageHeader, Spinner } from "../../../components/ui";
import { errorMessage } from "../../../services/api";
import { admin } from "../../../services/endpoints";
import type { AuthEmailTemplate, EmailTemplates } from "../../../types";

const KEY = "institute_proposal";
const PLACEHOLDERS =
  "{contact_name}, {institute_name}, {link}, {app_name}, {proposal_image_url} (email HTML)";

type ProposalTemplate = AuthEmailTemplate & { whatsapp?: string };

export function AdminOutreachTemplatesPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const settings = useQuery({ queryKey: ["admin", "settings"], queryFn: admin.settings });
  const imageInfo = useQuery({
    queryKey: ["admin-outreach-proposal-image"],
    queryFn: () => admin.outreachProposalImageInfo(),
  });
  const [draft, setDraft] = useState<ProposalTemplate>({
    subject: "",
    body: "",
    html: "",
    whatsapp: "",
  });
  const [emailHtml, setEmailHtml] = useState("");
  const [whatsappHtml, setWhatsappHtml] = useState("");
  const [editorEpoch, setEditorEpoch] = useState(0);

  useEffect(() => {
    const row = settings.data?.email_templates?.auth?.[KEY] as ProposalTemplate | undefined;
    if (row) {
      setDraft({
        subject: row.subject || "",
        body: row.body || "",
        html: row.html || "",
        whatsapp: row.whatsapp || "",
      });
      const htmlSource = (row.html || "").trim() ? row.html : row.body;
      setEmailHtml(plainTextToEditorHtml(htmlSource || ""));
      setWhatsappHtml(plainTextToEditorHtml(row.whatsapp || ""));
      setEditorEpoch((n) => n + 1);
    }
  }, [settings.data]);

  const previewUrl = useMemo(() => {
    const base = imageInfo.data?.url || "/outreach/campus-partnership-proposal.jpg";
    const v = imageInfo.data?.updated_at;
    return v ? `${base}?v=${Math.floor(v)}` : base;
  }, [imageInfo.data]);

  const uploadImage = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return admin.outreachProposalImageUpload(form);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-outreach-proposal-image"] });
      toast.success("Partnership image updated.");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const save = useMutation({
    mutationFn: async () => {
      const html = emailHtml.trim();
      const bodyPlain = editorHtmlToPlainText(html || emailHtml);
      const whatsappPlain = editorHtmlToPlainText(whatsappHtml || draft.whatsapp || "");
      const current = settings.data?.email_templates ?? { auth: {}, events: {} };
      const auth = {
        ...current.auth,
        [KEY]: {
          ...draft,
          body: bodyPlain || draft.body,
          html,
          whatsapp: whatsappPlain,
        },
      };
      const payload: EmailTemplates = { auth, events: current.events ?? {} };
      return admin.updateEmailTemplates(payload);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin", "settings"] });
      toast.success("Outreach templates saved. Regenerate proposals on leads to apply new copy.");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (settings.isLoading) return <Spinner label="Loading templates…" />;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Outreach templates"
        description="Email and WhatsApp copy for institute partnership proposals, plus the banner image sent on WhatsApp."
        actions={
          <Link to="/admin/system" className="text-sm font-medium text-brand-700 underline">
            All email templates
          </Link>
        }
      />

      <Alert kind="info">
        Placeholders: {PLACEHOLDERS}. After editing, open a lead → <strong>Generate proposal</strong> again, then send.
      </Alert>

      <Card title="Partnership banner image">
        <p className="text-sm text-slate-600 mb-4">
          Attached to WhatsApp outreach sends and embedded in HTML emails via{" "}
          <code className="text-xs">{`{proposal_image_url}`}</code>. JPG, PNG, or WebP, max 8 MB.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 items-start">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-2 max-w-md">
            <img
              src={previewUrl}
              alt="Campus partnership preview"
              className="max-h-48 w-full object-contain rounded"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          </div>
          <div className="space-y-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
              className="sr-only"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadImage.mutate(file);
                e.target.value = "";
              }}
            />
            <Button
              variant="secondary"
              loading={uploadImage.isPending}
              onClick={() => fileInputRef.current?.click()}
            >
              <ImagePlus className="h-4 w-4 mr-1" aria-hidden />
              Upload new image
            </Button>
            {!imageInfo.data?.exists ? (
              <p className="text-xs text-amber-700">No custom image yet — using bundled default if present.</p>
            ) : null}
          </div>
        </div>
      </Card>

      <Card title="Email proposal">
        <div className="grid gap-4">
          <TextInput
            label="Subject"
            value={draft.subject}
            onChange={(v) => setDraft((d) => ({ ...d, subject: v }))}
            maxLength={500}
          />
          <RichHtmlEditor
            key={`email-${editorEpoch}`}
            label="Email body (rich HTML)"
            hint="Use {proposal_image_url} in HTML mode to place the banner. Plain-text email is generated from this content on save."
            value={emailHtml}
            onChange={setEmailHtml}
          />
        </div>
      </Card>

      <Card title="WhatsApp proposal">
        <p className="text-sm text-slate-600 mb-3">
          Rich text is converted to plain text for WhatsApp. The partnership banner image is sent automatically with
          outreach.
        </p>
        <RichHtmlEditor
          key={`wa-${editorEpoch}`}
          label="WhatsApp message"
          hint="Bold, lists, and links are supported in the editor; WhatsApp receives plain text. Use placeholders like {institute_name} and {link}."
          value={whatsappHtml}
          onChange={setWhatsappHtml}
        />
      </Card>

      <div className="flex justify-end">
        <Button loading={save.isPending} onClick={() => save.mutate()}>
          Save outreach templates
        </Button>
      </div>
      {save.error ? <Alert kind="error">{errorMessage(save.error)}</Alert> : null}
    </div>
  );
}
