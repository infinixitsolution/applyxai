import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useSession, useSetSession } from "../../auth/session";
import { TextArea, TextInput } from "../../components/form";
import { ConfirmDialog } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { formatDate, formatDateTime, formatMoney } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { auth, partner } from "../../services/endpoints";

function Pending() {
  return <Alert kind="info">Your partner application is waiting for approval. Referral links work; commissions start after approval and KYC.</Alert>;
}

async function copyText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

async function copyOrToast(toast: { success: (m: string) => void; error: (m: string) => void }, value: string, ok = "Link copied.") {
  const copied = await copyText(value);
  if (copied) toast.success(ok);
  else toast.error("Couldn't copy.");
}

function referralUrl(path: string): string {
  return `${window.location.origin}${path}`;
}

export function PartnerDashboardPage() {
  const { data: user } = useSession();
  const toast = useToast();
  const { data, isLoading, error } = useQuery({ queryKey: ["partner", "dashboard"], queryFn: partner.dashboard });
  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  const link = referralUrl(data.referral_path);
  return (
    <>
      <PageHeader title={data.partner.organization} description="Refer institutes and earn on verified campus payments." />
      {user?.partner_status === "pending" && <div className="mb-6"><Pending /></div>}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card><p className="text-sm text-slate-500">Institutes</p><p className="mt-1 text-2xl font-semibold">{data.institutes}</p></Card>
        <Card><p className="text-sm text-slate-500">Clicks</p><p className="mt-1 text-2xl font-semibold">{data.partner.click_count}</p></Card>
        <Card><p className="text-sm text-slate-500">Available</p><p className="mt-1 text-2xl font-semibold">{formatMoney(data.partner.wallet.available_cents, "INR")}</p></Card>
      </div>
      <Card className="mt-6">
        <p className="text-sm text-slate-600">Referral link</p>
        <p className="mt-1 font-mono text-sm">{link}</p>
        <Button className="mt-3" variant="secondary" size="sm" onClick={() => void copyOrToast(toast, link)}>Copy link</Button>
      </Card>
    </>
  );
}

export function PartnerInstitutesPage() {
  const toast = useToast();
  const client = useQueryClient();
  const [form, setForm] = useState({ name: "", email: "", password: "", contact_name: "", phone: "" });
  const { data, isLoading } = useQuery({ queryKey: ["partner", "institutes"], queryFn: partner.institutes });
  const enroll = useMutation({
    mutationFn: () => partner.enroll(form),
    onSuccess: () => {
      setForm({ name: "", email: "", password: "", contact_name: "", phone: "" });
      client.invalidateQueries({ queryKey: ["partner"] });
      toast.success("Institute enrolled.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <>
      <PageHeader title="Institutes" description="Enroll a campus. They get their own login." />
      <Card className="mb-6">
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); enroll.mutate(); }} className="grid gap-3 sm:grid-cols-2">
          <TextInput label="Institute name" value={form.name} onChange={(name) => setForm((f) => ({ ...f, name }))} required />
          <TextInput label="Admin email" type="email" value={form.email} onChange={(email) => setForm((f) => ({ ...f, email }))} required />
          <TextInput label="Contact name" value={form.contact_name} onChange={(contact_name) => setForm((f) => ({ ...f, contact_name }))} />
          <TextInput label="Phone" value={form.phone} onChange={(phone) => setForm((f) => ({ ...f, phone }))} />
          <TextInput label="Password" type="password" value={form.password} onChange={(password) => setForm((f) => ({ ...f, password }))} required />
          <div className="sm:col-span-2"><Button type="submit" loading={enroll.isPending}>Enroll institute</Button></div>
        </form>
      </Card>
      {isLoading ? <Spinner /> : !data?.items.length ? <EmptyState title="No institutes yet" /> : (
        <Card>
          <ul className="divide-y divide-slate-100">
            {data.items.map((i) => (
              <li key={i.id} className="flex justify-between py-3 text-sm">
                <div><p className="font-medium">{i.name}</p><p className="text-xs text-slate-500">{i.email}</p></div>
                <Badge>{i.status}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

export function PartnerReferralsPage() {
  const toast = useToast();
  const { data, isLoading } = useQuery({ queryKey: ["partner", "referrals"], queryFn: partner.referrals });
  if (isLoading) return <Spinner />;
  const link = referralUrl(data?.referral_path ?? "");
  return (
    <>
      <PageHeader title="Referrals" description={`${data?.click_count ?? 0} clicks on your link.`} />
      <Card className="mb-6">
        <p className="font-mono text-sm">{link}</p>
        <p className="mt-1 text-xs text-slate-500">Code {data?.referral_code}</p>
        <Button className="mt-3" variant="secondary" size="sm" onClick={() => void copyOrToast(toast, link)}>Copy link</Button>
      </Card>
      {!data?.institutes.length ? <EmptyState title="No campuses from this link yet" /> : (
        <Card>
          <ul className="divide-y divide-slate-100">
            {data.institutes.map((i) => (
              <li key={i.id} className="flex justify-between py-3 text-sm">
                <div>
                  <p className="font-medium">{i.name}</p>
                  <p className="text-xs text-slate-500">{i.email}</p>
                </div>
                <Badge>{i.status}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

export function PartnerCampaignsPage() {
  const toast = useToast();
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const { data, isLoading } = useQuery({ queryKey: ["partner", "campaigns"], queryFn: partner.campaigns });
  const create = useMutation({
    mutationFn: () => partner.createCampaign(name, note),
    onSuccess: () => { setName(""); setNote(""); client.invalidateQueries({ queryKey: ["partner"] }); toast.success("Campaign created."); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <>
      <PageHeader title="Campaigns" />
      <Card className="mb-6">
        <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="grid gap-3 sm:grid-cols-2">
          <TextInput label="Name" value={name} onChange={setName} required />
          <TextInput label="Note" value={note} onChange={setNote} />
          <div className="sm:col-span-2"><Button type="submit" loading={create.isPending} disabled={!name.trim()}>Create</Button></div>
        </form>
      </Card>
      {isLoading ? <Spinner /> : (
        <Card>
          <ul className="divide-y divide-slate-100">
            {(data?.items ?? []).map((c) => (
              <li key={c.id} className="flex justify-between py-3 text-sm">
                <span>{c.name} <span className="font-mono text-xs text-slate-500">{c.path}</span></span>
                <span>{c.click_count} clicks</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

export function PartnerCommissionsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["partner", "commissions"], queryFn: partner.commissions });
  if (isLoading) return <Spinner />;
  return (
    <>
      <PageHeader title="Commissions" description={`Approved ${formatMoney(data?.wallet.approved_cents ?? 0, "INR")}`} />
      <Card>
        <ul className="divide-y divide-slate-100">
          {(data?.items ?? []).map((c) => (
            <li key={c.id} className="flex justify-between py-3 text-sm">
              <span>{formatDate(c.created_at)} · {c.note || c.institute_name || "Commission"}</span>
              <span>{formatMoney(c.amount_cents, c.currency)} <Badge>{c.status}</Badge></span>
            </li>
          ))}
          {!data?.items.length && <li className="py-6 text-sm text-slate-500">No commissions yet.</li>}
        </ul>
      </Card>
    </>
  );
}

export function PartnerPayoutsPage() {
  const toast = useToast();
  const client = useQueryClient();
  const [amount, setAmount] = useState("");
  const { data, isLoading } = useQuery({ queryKey: ["partner", "payouts"], queryFn: partner.payouts });
  const request = useMutation({
    mutationFn: () => {
      const rupees = Number(amount);
      return partner.requestPayout(amount && Number.isFinite(rupees) ? Math.round(rupees * 100) : undefined);
    },
    onSuccess: () => { setAmount(""); client.invalidateQueries({ queryKey: ["partner"] }); toast.success("Payout requested."); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (isLoading) return <Spinner />;
  return (
    <>
      <PageHeader title="Payouts" description={`Available ${formatMoney(data?.wallet.available_cents ?? 0, "INR")}`} />
      <Card className="mb-6">
        <form onSubmit={(e) => { e.preventDefault(); request.mutate(); }} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="max-w-xs">
            <TextInput label="Amount (₹)" value={amount} onChange={setAmount} placeholder="Leave blank for full available" />
          </div>
          <Button type="submit" loading={request.isPending}>Request payout</Button>
        </form>
      </Card>
      <Card>
        <ul className="divide-y divide-slate-100">
          {(data?.items ?? []).map((p) => (
            <li key={p.id} className="flex justify-between py-3 text-sm">
              <span>{formatDate(p.created_at)}</span>
              <span>{formatMoney(p.amount_cents, p.currency)} <Badge>{p.status}</Badge></span>
            </li>
          ))}
          {!data?.items.length && <li className="py-6 text-sm text-slate-500">No payout requests yet.</li>}
        </ul>
      </Card>
    </>
  );
}

export function PartnerMarketingPage() {
  const toast = useToast();
  const { data, isLoading } = useQuery({ queryKey: ["partner", "marketing"], queryFn: partner.marketing });
  if (isLoading) return <Spinner />;
  return (
    <>
      <PageHeader title="Marketing" />
      <div className="grid gap-4 sm:grid-cols-2">
        {(data?.assets ?? []).map((a) => (
          <Card key={a.title}>
            <h3 className="font-semibold">{a.title}</h3>
            <p className="mt-2 text-sm text-slate-600">{a.text}</p>
            <Button className="mt-3" size="sm" variant="secondary" onClick={() => void copyOrToast(toast, a.text, "Copied.")}>Copy</Button>
          </Card>
        ))}
      </div>
    </>
  );
}

export function PartnerLinksPage() {
  const toast = useToast();
  const { data, isLoading } = useQuery({ queryKey: ["partner", "links"], queryFn: partner.links });
  if (isLoading) return <Spinner />;
  const main = referralUrl(data?.referral_path ?? "");
  return (
    <>
      <PageHeader title="Tracking links" />
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-mono text-sm">{main}</p>
          <Button size="sm" variant="secondary" onClick={() => void copyOrToast(toast, main)}>Copy</Button>
        </div>
        <ul className="mt-4 divide-y divide-slate-100">
          {(data?.campaigns ?? []).map((c) => {
            const href = referralUrl(c.path);
            return (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="font-mono text-xs">{href}</span>
                <Button size="sm" variant="ghost" onClick={() => void copyOrToast(toast, href)}>Copy</Button>
              </li>
            );
          })}
        </ul>
      </Card>
    </>
  );
}

export function PartnerProfilePage() {
  const toast = useToast();
  const client = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["partner", "me"], queryFn: partner.me });
  const [form, setForm] = useState({ organization: "", contact_name: "", phone: "" });
  useEffect(() => {
    if (!data) return;
    setForm({ organization: data.organization, contact_name: data.contact_name, phone: data.phone });
  }, [data]);
  const save = useMutation({
    mutationFn: () => partner.saveProfile(form),
    onSuccess: (updated) => {
      client.setQueryData(["partner", "me"], updated);
      void client.invalidateQueries({ queryKey: ["partner"] });
      toast.success("Saved.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (isLoading || !data) return <Spinner />;
  return (
    <>
      <PageHeader title="Profile" />
      <Card>
        <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="space-y-4">
          <TextInput label="Organisation" required value={form.organization} onChange={(organization) => setForm((f) => ({ ...f, organization }))} maxLength={190} />
          <TextInput label="Contact name" value={form.contact_name} onChange={(contact_name) => setForm((f) => ({ ...f, contact_name }))} maxLength={190} />
          <TextInput label="Phone" value={form.phone} onChange={(phone) => setForm((f) => ({ ...f, phone }))} maxLength={32} />
          <Button type="submit" loading={save.isPending} disabled={!form.organization.trim()}>Save</Button>
        </form>
      </Card>
    </>
  );
}

export function PartnerKycPage() {
  const toast = useToast();
  const client = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["partner", "me"], queryFn: partner.me });
  const [filename, setFilename] = useState("");
  const [note, setNote] = useState("");
  const add = useMutation({
    mutationFn: () => partner.addKyc(filename, note),
    onSuccess: (updated) => {
      setFilename(""); setNote("");
      client.setQueryData(["partner", "me"], updated);
      toast.success("Document recorded.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (isLoading || !data) return <Spinner />;
  return (
    <>
      <PageHeader title="KYC" description={`Status: ${data.kyc_status}`} />
      <Card className="mb-6">
        <form onSubmit={(e) => { e.preventDefault(); add.mutate(); }} className="space-y-3">
          <TextInput label="Document name" value={filename} onChange={setFilename} required hint="Record the file you hold. Uploads are reviewed by ApplyXAI." />
          <TextArea label="Note" value={note} onChange={setNote} maxLength={255} />
          <Button type="submit" loading={add.isPending} disabled={!filename.trim()}>Add</Button>
        </form>
      </Card>
      <Card>
        <ul className="divide-y divide-slate-100 text-sm">
          {data.kyc_documents.map((d) => (
            <li key={`${d.uploaded_at}-${d.filename}`} className="py-2">
              <p className="font-medium">{d.filename}</p>
              {d.note && <p className="text-slate-600">{d.note}</p>}
              <p className="text-xs text-slate-400">{formatDateTime(d.uploaded_at)}</p>
            </li>
          ))}
          {!data.kyc_documents.length && <li className="py-6 text-slate-500">No documents recorded.</li>}
        </ul>
      </Card>
    </>
  );
}

export function PartnerTaxPage() {
  const toast = useToast();
  const client = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["partner", "me"], queryFn: partner.me });
  const [form, setForm] = useState({ gstin: "", pan_number: "", payout_account: "", payout_ifsc: "" });
  useEffect(() => {
    if (!data) return;
    setForm({ gstin: data.gstin, pan_number: data.pan_number, payout_account: data.payout_account, payout_ifsc: data.payout_ifsc });
  }, [data]);
  const save = useMutation({
    mutationFn: () => partner.saveTax(form),
    onSuccess: (updated) => {
      client.setQueryData(["partner", "me"], updated);
      toast.success("Saved.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (isLoading || !data) return <Spinner />;
  return (
    <>
      <PageHeader title="Tax and payouts" />
      <Card>
        <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="space-y-4">
          <TextInput label="GSTIN" value={form.gstin} onChange={(gstin) => setForm((f) => ({ ...f, gstin }))} maxLength={15} />
          <TextInput label="PAN" value={form.pan_number} onChange={(pan_number) => setForm((f) => ({ ...f, pan_number }))} maxLength={10} />
          <TextInput label="Account number" value={form.payout_account} onChange={(payout_account) => setForm((f) => ({ ...f, payout_account }))} />
          <TextInput label="IFSC" value={form.payout_ifsc} onChange={(payout_ifsc) => setForm((f) => ({ ...f, payout_ifsc }))} />
          <Button type="submit" loading={save.isPending}>Save</Button>
        </form>
      </Card>
    </>
  );
}

export function PartnerSettingsPage() {
  const { data: user } = useSession();
  const { data } = useQuery({ queryKey: ["partner", "me"], queryFn: partner.me });
  const setSession = useSetSession();
  const navigate = useNavigate();
  const toast = useToast();
  const [confirmAll, setConfirmAll] = useState(false);
  const reset = useMutation({
    mutationFn: () => auth.forgotPassword(user!.email),
    onSuccess: () => toast.success("Check your email for a link to set a new password."),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const logoutAll = useMutation({
    mutationFn: auth.logoutAll,
    onSuccess: () => { setSession(null); navigate("/login", { replace: true }); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const link = data ? referralUrl(`/r/${data.referral_code}`) : "";
  return (
    <>
      <PageHeader title="Settings" description="Referral code and account security." />
      <div className="space-y-6">
        <Card title="Referral">
          <p className="text-sm text-slate-600">Referral code: <span className="font-mono">{data?.referral_code ?? "—"}</span></p>
          {data && (
            <>
              <p className="mt-1 font-mono text-xs text-slate-500">{link}</p>
              <Button className="mt-3" size="sm" variant="secondary" onClick={() => void copyOrToast(toast, link)}>Copy link</Button>
            </>
          )}
        </Card>
        <Card title="Password">
          <p className="mb-4 text-sm text-slate-600">We'll email you a secure link to choose a new password.</p>
          <Button variant="secondary" onClick={() => reset.mutate()} loading={reset.isPending} disabled={!user}>Email me a reset link</Button>
        </Card>
        <Card title="Sessions">
          <p className="mb-4 text-sm text-slate-600">Sign out everywhere, including this browser.</p>
          <Button variant="danger" onClick={() => setConfirmAll(true)}>Log out of all devices</Button>
        </Card>
      </div>
      <ConfirmDialog open={confirmAll} onClose={() => setConfirmAll(false)} title="Log out everywhere?" danger
                     confirmLabel="Log out everywhere" loading={logoutAll.isPending} onConfirm={() => logoutAll.mutate()}
                     message="Every session, including this one, will end. You'll need to log in again." />
    </>
  );
}
