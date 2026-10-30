import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Eye,
  Loader2,
  MessageCircle,
  Pencil,
  Radar,
  Search,
  Send,
  Sparkles,
  Upload,
  UserPlus,
  Users,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Select, TextInput } from "../../../components/form";
import { Modal } from "../../../components/Modal";
import { Pagination } from "../../../components/Pagination";
import { useToast } from "../../../components/Toast";
import { formatRelative } from "../../../lib/format";
import { useDebounced } from "../../../lib/useDebounced";
import { Alert, Badge, Button, ButtonLink, Card, EmptyState, PageHeader, Spinner, cx } from "../../../components/ui";
import { FilterChip, FilterChipBrand, Stat } from "../shared";
import { contactsFromSpreadsheetBuffer, OUTREACH_BULK_SHEET_ACCEPT } from "../../../lib/outreachBulkExcel";
import { errorMessage } from "../../../services/api";
import { admin } from "../../../services/endpoints";
import type { OutreachBulkActionResult, OutreachBulkImportResult, OutreachLead } from "../../../types";
import {
  draftFromLead,
  LeadCompletenessScore,
  outreachLeadStatusLabel,
  outreachLeadStatusTone,
  OutreachSetupAlert,
  payloadFromDraft,
} from "./shared";
import type { LeadEditDraft } from "./shared";

const LEADS_PAGE_SIZE = 25;

function buildSingleLeadImportLine(name: string, email: string, phone: string): string {
  return [name.trim(), email.trim(), phone.trim()].filter(Boolean).join(", ");
}

const LEAD_STATUS_FILTERS = [
  { value: "discovered", label: "Discovered" },
  { value: "completing_profile", label: "Completing profile" },
  { value: "enriched", label: "Enriched" },
  { value: "ready", label: "Ready" },
  { value: "proposal_ready", label: "Proposal ready" },
  { value: "sent", label: "Sent" },
  { value: "replied", label: "Replied" },
  { value: "skipped_incomplete", label: "Skipped" },
] as const;

const LEAD_SOURCE_OPTIONS = [
  { value: "", label: "All sources" },
  { value: "manual", label: "Manual upload" },
  { value: "google", label: "Google / web" },
  { value: "facebook", label: "Facebook" },
  { value: "instagram", label: "Instagram" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "whatsapp", label: "WhatsApp" },
];

const PROFILE_SCORE_FILTERS = [
  { value: "", label: "Any score" },
  { value: "complete", label: "100% complete" },
  { value: "incomplete", label: "Under 100%" },
] as const;

export function AdminOutreachLeadsPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const location = useLocation();
  const navigate = useNavigate();
  const [editLeadId, setEditLeadId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<LeadEditDraft | null>(null);
  const [editBaseProfile, setEditBaseProfile] = useState<Record<string, unknown>>({});
  const [bulkOpen, setBulkOpen] = useState(false);
  const [singleOpen, setSingleOpen] = useState(false);
  const [singleName, setSingleName] = useState("");
  const [singleEmail, setSingleEmail] = useState("");
  const [singlePhone, setSinglePhone] = useState("");
  const [singleEnrich, setSingleEnrich] = useState(true);
  const [bulkText, setBulkText] = useState("");
  const [bulkEnrich, setBulkEnrich] = useState(true);
  const [bulkResult, setBulkResult] = useState<OutreachBulkImportResult | null>(null);
  const [sheetFileName, setSheetFileName] = useState("");
  const sheetInputRef = useRef<HTMLInputElement>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkActionResult, setBulkActionResult] = useState<OutreachBulkActionResult | null>(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [scoreFilter, setScoreFilter] = useState<(typeof PROFILE_SCORE_FILTERS)[number]["value"]>("");
  const [searchQ, setSearchQ] = useState("");
  const debouncedQ = useDebounced(searchQ.trim());

  const stats = useQuery({
    queryKey: ["admin-outreach-leads-stats"],
    queryFn: () => admin.outreachLeadStats(),
    refetchInterval: (query) => ((query.state.data?.profile_completing ?? 0) > 0 ? 3000 : 15000),
  });

  const pendingCompletion = stats.data?.profile_completion_pending ?? 0;
  const statsBusy = pendingCompletion > 0;

  const leads = useQuery({
    queryKey: ["admin-outreach-leads", page, statusFilter, sourceFilter, scoreFilter, debouncedQ],
    queryFn: () =>
      admin.outreachLeads({
        page,
        page_size: LEADS_PAGE_SIZE,
        ...(statusFilter ? { status: statusFilter } : {}),
        ...(sourceFilter ? { source: sourceFilter } : {}),
        ...(scoreFilter === "complete" ? { profile_complete: true } : {}),
        ...(scoreFilter === "incomplete" ? { profile_complete: false } : {}),
        ...(debouncedQ ? { q: debouncedQ } : {}),
      }),
    placeholderData: keepPreviousData,
    refetchInterval: statsBusy ? 3000 : 8000,
  });

  const bulkAction = useMutation({
    mutationFn: (action: "complete" | "enhance") =>
      admin.outreachBulkLeadAction({ lead_ids: [...selectedIds], action }),
    onSuccess: (data) => {
      setBulkActionResult(data);
      void qc.invalidateQueries({ queryKey: ["admin-outreach-leads"] });
      void qc.invalidateQueries({ queryKey: ["admin-outreach-leads-stats"] });
      toast.success(
        `${data.action === "complete" ? "Complete profile" : "Enhance"}: ${data.succeeded} ok` +
          (data.failed ? `, ${data.failed} failed` : ""),
      );
      if (data.failed === 0) setSelectedIds(new Set());
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const invalidateLeadLists = () => {
    void qc.invalidateQueries({ queryKey: ["admin-outreach-leads"] });
    void qc.invalidateQueries({ queryKey: ["admin-outreach-leads-stats"] });
  };

  const singleImport = useMutation({
    mutationFn: () =>
      admin.outreachBulkImportLeads({
        contacts: buildSingleLeadImportLine(singleName, singleEmail, singlePhone),
        enrich: singleEnrich,
      }),
    onSuccess: (data) => {
      invalidateLeadLists();
      const row = data.items[0];
      if (data.invalid || !row?.lead_id) {
        toast.error(row?.error || "Could not add that contact. Check email or phone format.");
        return;
      }
      toast.success(
        row.status === "created"
          ? `Lead added${data.enrich_queued ? " — profile completion queued" : ""}.`
          : `Lead updated${data.enrich_queued ? " — profile completion queued" : ""}.`,
      );
      setSingleOpen(false);
      setSingleName("");
      setSingleEmail("");
      setSinglePhone("");
      if (row.lead_id) navigate(`/admin/outreach/leads/${row.lead_id}`);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const bulkImport = useMutation({
    mutationFn: () => admin.outreachBulkImportLeads({ contacts: bulkText, enrich: bulkEnrich }),
    onSuccess: (data) => {
      setBulkResult(data);
      invalidateLeadLists();
      toast.success(
        `Import done: ${data.created} new, ${data.existing} updated` +
          (data.invalid ? `, ${data.invalid} invalid` : "") +
          (data.enrich_queued
            ? `. Complete profile queued for ${data.enrich_queued} lead(s) — scores update in the list as enrichment runs.`
            : ""),
      );
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const saveLead = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      admin.outreachUpdateLead(id, { payload }),
    onSuccess: () => {
      toast.success("Lead profile saved");
      void qc.invalidateQueries({ queryKey: ["admin-outreach-leads"] });
      void qc.invalidateQueries({ queryKey: ["admin-outreach-leads-stats"] });
      void qc.invalidateQueries({ queryKey: ["admin-outreach-lead"] });
      setEditLeadId(null);
      setEditDraft(null);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const onSpreadsheetSelected = async (file: File | null) => {
    if (!file) return;
    setSheetFileName("");
    try {
      const buffer = await file.arrayBuffer();
      const { lines } = contactsFromSpreadsheetBuffer(buffer);
      if (!lines.length) {
        toast.error("No email or phone rows found in the sheet. Use columns named Email and/or Phone.");
        return;
      }
      setBulkText(lines.join("\n"));
      setSheetFileName(file.name);
      toast.success(`Loaded ${lines.length} contact(s) from ${file.name}.`);
    } catch {
      toast.error("Could not read that file. Use .xlsx, .xls, or .csv.");
    } finally {
      if (sheetInputRef.current) sheetInputRef.current.value = "";
    }
  };

  const openEdit = (lead: OutreachLead) => {
    setEditLeadId(lead.id);
    setEditDraft(draftFromLead(lead));
    setEditBaseProfile({ ...lead.profile });
  };

  useEffect(() => {
    const fromState = (location.state as { editLeadId?: string } | null)?.editLeadId;
    if (!fromState || !leads.data?.items.length) return;
    const lead = leads.data.items.find((l) => l.id === fromState);
    if (lead) openEdit(lead);
    navigate(location.pathname, { replace: true, state: {} });
  }, [location.state, leads.data?.items, location.pathname, navigate]);

  const pageItems = leads.data?.items ?? [];
  const allOnPageSelected = pageItems.length > 0 && pageItems.every((l) => selectedIds.has(l.id));
  const someSelected = selectedIds.size > 0;

  const toggleAllOnPage = () => {
    if (allOnPageSelected) {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        pageItems.forEach((l) => next.delete(l.id));
        return next;
      });
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        pageItems.forEach((l) => next.add(l.id));
        return next;
      });
    }
  };

  const toggleOne = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const setStatusFilterAndPage = (status: string) => {
    setStatusFilter(status);
    setPage(1);
  };

  const hasActiveFilters = Boolean(statusFilter || sourceFilter || scoreFilter || debouncedQ);

  const clearFilters = () => {
    setStatusFilter("");
    setSourceFilter("");
    setScoreFilter("");
    setSearchQ("");
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Outreach leads"
        description="Dashboard for institute discovery, profile enrichment, and partnership outreach."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {stats.dataUpdatedAt > 0 && (
              <span className={cx("text-xs text-slate-500", stats.isFetching && "opacity-60")}>
                Updated {formatRelative(new Date(stats.dataUpdatedAt).toISOString())}
              </span>
            )}
            <ButtonLink to="/admin/outreach/scrape" variant="secondary" size="sm">
              <Radar className="h-3.5 w-3.5 mr-1.5" aria-hidden />
              Scrape
            </ButtonLink>
            <ButtonLink to="/admin/outreach/whatsapp" variant="secondary" size="sm">
              <MessageCircle className="h-3.5 w-3.5 mr-1.5" aria-hidden />
              WhatsApp
            </ButtonLink>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setSingleOpen(true)}
            >
              <UserPlus className="h-3.5 w-3.5 mr-1.5" aria-hidden />
              Add lead
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setBulkOpen(true);
                setBulkResult(null);
              }}
            >
              <Upload className="h-3.5 w-3.5 mr-1.5" aria-hidden />
              Bulk upload
            </Button>
          </div>
        }
      />
      <OutreachSetupAlert />

      {stats.isLoading ? (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      ) : stats.data ? (
        <>
          {statsBusy && (
            <Card className="border-brand-200 bg-gradient-to-r from-brand-50/90 to-white p-4 sm:p-5">
              <div className="flex flex-wrap items-center gap-3">
                <Loader2 className="h-5 w-5 shrink-0 animate-spin text-brand-600" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">Background profile completion</p>
                  <p className="text-sm text-slate-600">
                    <span className="font-semibold tabular-nums text-brand-800">{pendingCompletion}</span>{" "}
                    {pendingCompletion === 1 ? "lead is" : "leads are"} being enriched (Firecrawl + AI). Counts refresh
                    every few seconds.
                  </p>
                </div>
                <Button
                  size="sm"
                  variant={statusFilter === "completing_profile" ? "primary" : "secondary"}
                  onClick={() =>
                    setStatusFilterAndPage(statusFilter === "completing_profile" ? "" : "completing_profile")
                  }
                >
                  {statusFilter === "completing_profile" ? "Show all leads" : "View pending in list"}
                </Button>
              </div>
            </Card>
          )}

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat
              icon={<Users className="h-4 w-4" aria-hidden />}
              label="Total leads"
              value={stats.data.total.toLocaleString()}
              sub="All institutes in the pipeline"
            />
            <button
              type="button"
              className="text-left"
              onClick={() =>
                setStatusFilterAndPage(statusFilter === "completing_profile" ? "" : "completing_profile")
              }
            >
              <Stat
                icon={
                  <Loader2
                    className={cx("h-4 w-4", statsBusy && "animate-spin text-brand-600")}
                    aria-hidden
                  />
                }
                label="Completing profile"
                value={pendingCompletion.toLocaleString()}
                sub={statsBusy ? "Pending in background — click to filter list" : "None running right now"}
              />
            </button>
            <Stat
              icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}
              label="Profile 100%"
              value={stats.data.completeness_full.toLocaleString()}
              sub={`${stats.data.enriched.toLocaleString()} marked enriched`}
            />
            <Stat
              icon={<Send className="h-4 w-4" aria-hidden />}
              label="Outreach sent"
              value={stats.data.sent.toLocaleString()}
              sub={`${stats.data.skipped_incomplete.toLocaleString()} skipped (incomplete)`}
            />
          </div>
        </>
      ) : stats.isError ? (
        <Alert kind="error">{errorMessage(stats.error)}</Alert>
      ) : null}

      {leads.isError && (
        <Alert kind="error">
          {errorMessage(leads.error)}
          {import.meta.env.DEV && (
            <p className="mt-2 text-xs text-slate-600">
              Check the API terminal for a traceback. Confirm you are signed in as admin and Firecrawl + Platform AI are
              configured under Admin → Settings.
            </p>
          )}
        </Alert>
      )}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Lead pipeline</h2>
          <p className="text-sm text-slate-600">Select rows for bulk complete / enhance, or open a lead to send outreach.</p>
        </div>
        {leads.data && (
          <p className="text-sm text-slate-500 tabular-nums">
            {leads.data.total.toLocaleString()} {hasActiveFilters ? "matching" : "total"}
          </p>
        )}
      </div>

      {someSelected && (
        <Card className="p-4 flex flex-wrap items-center gap-3 border-brand-200 bg-brand-50/40">
          <span className="text-sm font-medium text-slate-800">
            {selectedIds.size} selected (max 25 per run)
          </span>
          <Button
            size="sm"
            loading={bulkAction.isPending && bulkAction.variables === "complete"}
            disabled={bulkAction.isPending || selectedIds.size > 25}
            onClick={() => bulkAction.mutate("complete")}
          >
            <Search className="h-3.5 w-3.5 mr-1.5" aria-hidden />
            Bulk complete profile
          </Button>
          <Button
            size="sm"
            variant="secondary"
            loading={bulkAction.isPending && bulkAction.variables === "enhance"}
            disabled={bulkAction.isPending || selectedIds.size > 25}
            onClick={() => bulkAction.mutate("enhance")}
          >
            <Sparkles className="h-3.5 w-3.5 mr-1.5" aria-hidden />
            Bulk enhance
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>
            Clear selection
          </Button>
          {selectedIds.size > 25 && (
            <span className="text-xs text-amber-800">Deselect down to 25 leads to run bulk actions.</span>
          )}
        </Card>
      )}

      {bulkActionResult && (
        <Alert kind={bulkActionResult.failed ? "info" : "success"}>
          <p className="text-sm">
            {bulkActionResult.action === "complete" ? "Complete profile" : "Enhance"} finished:{" "}
            {bulkActionResult.succeeded} succeeded, {bulkActionResult.failed} failed.
          </p>
          {bulkActionResult.items.some((r) => !r.ok) && (
            <ul className="mt-2 text-xs list-disc pl-4 max-h-24 overflow-y-auto">
              {bulkActionResult.items
                .filter((r) => !r.ok)
                .map((r) => (
                  <li key={r.lead_id}>
                    {r.display_name || r.lead_id}: {r.error}
                  </li>
                ))}
            </ul>
          )}
        </Alert>
      )}

      <Card className="p-0 overflow-hidden">
        <div className="border-b border-slate-100 p-4 sm:p-5 space-y-4">
          <TextInput
            label="Search institutes"
            hint="Matches institute name, source URL, or WhatsApp number"
            value={searchQ}
            onChange={(v) => {
              setSearchQ(v);
              setPage(1);
            }}
            placeholder="e.g. KodNest, Bangalore, +9198…"
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Select
              label="Source"
              value={sourceFilter}
              options={LEAD_SOURCE_OPTIONS}
              onChange={(v) => {
                setSourceFilter(v);
                setPage(1);
              }}
            />
            <Select
              label="Profile score"
              value={scoreFilter}
              options={PROFILE_SCORE_FILTERS.map((f) => ({ value: f.value, label: f.label }))}
              onChange={(v) => {
                setScoreFilter(v as (typeof PROFILE_SCORE_FILTERS)[number]["value"]);
                setPage(1);
              }}
            />
          </div>
          <div>
            <span className="mb-2 block text-sm font-medium text-slate-700">Status</span>
            <div className="flex flex-wrap gap-2">
              <FilterChip active={statusFilter === ""} onClick={() => setStatusFilterAndPage("")}>
                All
              </FilterChip>
              {LEAD_STATUS_FILTERS.map((f) => (
                <FilterChipBrand
                  key={f.value}
                  active={statusFilter === f.value}
                  onClick={() => setStatusFilterAndPage(statusFilter === f.value ? "" : f.value)}
                >
                  {f.label}
                </FilterChipBrand>
              ))}
            </div>
          </div>
          {hasActiveFilters && (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-slate-600">Active filters</span>
              {debouncedQ ? <Badge tone="brand">Search: {debouncedQ}</Badge> : null}
              {statusFilter ? <Badge tone="brand">{outreachLeadStatusLabel(statusFilter)}</Badge> : null}
              {sourceFilter ? (
                <Badge tone="brand">
                  {LEAD_SOURCE_OPTIONS.find((o) => o.value === sourceFilter)?.label ?? sourceFilter}
                </Badge>
              ) : null}
              {scoreFilter ? (
                <Badge tone="brand">{PROFILE_SCORE_FILTERS.find((f) => f.value === scoreFilter)?.label}</Badge>
              ) : null}
              <button type="button" className="font-medium text-brand-700 hover:underline" onClick={clearFilters}>
                Clear all
              </button>
            </div>
          )}
        </div>
        {leads.isLoading ? (
          <div className="p-8 flex justify-center">
            <Spinner />
          </div>
        ) : !leads.data?.total ? (
          <EmptyState title={hasActiveFilters ? "No matching leads" : "No leads"}>
            {hasActiveFilters
              ? "Try different search terms or clear filters to see the full pipeline."
              : "Run a scrape job to discover institutes, or use Bulk upload to add contacts by email or phone."}
          </EmptyState>
        ) : (
          <>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left">
              <tr>
                <th className="p-3 w-10">
                  <input
                    type="checkbox"
                    aria-label="Select all on this page"
                    checked={allOnPageSelected}
                    onChange={toggleAllOnPage}
                    className="rounded border-slate-300"
                  />
                </th>
                <th className="p-3">Institute</th>
                <th className="p-3">Source</th>
                <th className="p-3">Score</th>
                <th className="p-3">Status</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {leads.data.items.map((l) => (
                <tr
                  key={l.id}
                  className={cx(
                    "border-t hover:bg-slate-50",
                    editLeadId === l.id && "bg-brand-50",
                    selectedIds.has(l.id) && "bg-brand-50/60",
                  )}
                >
                  <td className="p-3">
                    <input
                      type="checkbox"
                      aria-label={`Select ${l.display_name || "lead"}`}
                      checked={selectedIds.has(l.id)}
                      onChange={() => toggleOne(l.id)}
                      className="rounded border-slate-300"
                    />
                  </td>
                  <td className="p-3 font-medium">{l.display_name || "—"}</td>
                  <td className="p-3 capitalize">{l.source_platform}</td>
                  <td className="p-3">
                    <LeadCompletenessScore lead={l} />
                  </td>
                  <td className="p-3">
                    <Badge tone={outreachLeadStatusTone(l.status)}>
                      {outreachLeadStatusLabel(l.status)}
                    </Badge>
                  </td>
                  <td className="p-3">
                    <div className="flex justify-end gap-1">
                      <ButtonLink to={`/admin/outreach/leads/${l.id}`} variant="ghost" size="sm">
                        <Eye className="h-3.5 w-3.5 mr-1" aria-hidden />
                        View
                      </ButtonLink>
                      <Button size="sm" variant="secondary" onClick={() => openEdit(l)}>
                        <Pencil className="h-3.5 w-3.5 mr-1" aria-hidden />
                        Edit
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t border-slate-100 px-4 pb-4 sm:px-5">
            <Pagination
              page={leads.data.page}
              pageSize={leads.data.page_size}
              total={leads.data.total}
              onPage={setPage}
            />
          </div>
          </>
        )}
      </Card>

      <Modal
        open={singleOpen}
        onClose={() => {
          if (!singleImport.isPending) setSingleOpen(false);
        }}
        title="Add lead"
        footer={
          <>
            <Button variant="secondary" disabled={singleImport.isPending} onClick={() => setSingleOpen(false)}>
              Cancel
            </Button>
            <Button
              loading={singleImport.isPending}
              disabled={!singleEmail.trim() && !singlePhone.trim()}
              onClick={() => singleImport.mutate()}
            >
              {singleEnrich ? "Add & complete profile" : "Add lead"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Alert kind="info">
            Add one institute by contact details. At least an <strong>email</strong> or <strong>phone</strong> is
            required. Optional enrichment runs complete profile in the background (same as bulk upload).
          </Alert>
          <TextInput label="Institute name (optional)" value={singleName} onChange={setSingleName} />
          <TextInput
            label="Email"
            type="email"
            value={singleEmail}
            onChange={setSingleEmail}
            placeholder="contact@institute.com"
          />
          <TextInput
            label="Phone / WhatsApp"
            value={singlePhone}
            onChange={setSinglePhone}
            placeholder="+91 98765 43210"
          />
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={singleEnrich}
              onChange={(e) => setSingleEnrich(e.target.checked)}
              className="rounded border-slate-300"
            />
            Run complete profile after add (recommended)
          </label>
        </div>
      </Modal>

      <Modal
        open={bulkOpen}
        onClose={() => {
          if (!bulkImport.isPending) {
            setBulkOpen(false);
            setBulkResult(null);
          }
        }}
        title="Bulk upload leads"
        size="lg"
        footer={
          <>
            <Button
              variant="secondary"
              disabled={bulkImport.isPending}
              onClick={() => {
                setBulkOpen(false);
                setBulkResult(null);
              }}
            >
              Close
            </Button>
            <Button
              loading={bulkImport.isPending}
              disabled={!bulkText.trim()}
              onClick={() => bulkImport.mutate()}
            >
              Import{bulkEnrich ? " (enrich in background)" : ""}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Alert kind="info">
            Paste contacts or upload an <strong>Excel / CSV</strong> sheet (.xlsx, .xls, .csv). Use columns{" "}
            <strong>Name</strong> (optional), <strong>Email</strong>, and/or <strong>Phone</strong> — or one contact per
            line below. With enrichment on, <strong>Complete profile</strong> (Firecrawl + AI) runs in the
            background after import — refresh the leads list to watch scores update.
          </Alert>
          <div className="flex flex-wrap items-center gap-3">
            <input
              ref={sheetInputRef}
              type="file"
              accept={OUTREACH_BULK_SHEET_ACCEPT}
              className="hidden"
              onChange={(e) => void onSpreadsheetSelected(e.target.files?.[0] ?? null)}
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={bulkImport.isPending}
              onClick={() => sheetInputRef.current?.click()}
            >
              <Upload className="h-3.5 w-3.5 mr-1.5" aria-hidden />
              Upload Excel / CSV
            </Button>
            {sheetFileName ? (
              <span className="text-xs text-slate-600">
                Loaded from <span className="font-medium">{sheetFileName}</span>
              </span>
            ) : (
              <span className="text-xs text-slate-500">First worksheet is used; header row is auto-detected.</span>
            )}
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={bulkEnrich}
              onChange={(e) => setBulkEnrich(e.target.checked)}
              className="rounded border-slate-300"
            />
            Run complete profile after import (recommended)
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Contacts</span>
            <textarea
              className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm min-h-[10rem]"
              placeholder={"info@institute.com\n9876543210\nBright Skills | +919876543210"}
              value={bulkText}
              onChange={(e) => setBulkText(e.target.value)}
              disabled={bulkImport.isPending}
            />
          </label>
          {bulkResult && (
            <div className="max-h-48 overflow-y-auto rounded-lg border border-slate-200 text-xs">
              <table className="w-full">
                <thead className="bg-slate-50 sticky top-0">
                  <tr>
                    <th className="p-2 text-left">Line</th>
                    <th className="p-2 text-left">Result</th>
                    <th className="p-2 text-right">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {bulkResult.items.map((row, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="p-2 font-mono truncate max-w-[12rem]" title={row.line}>
                        {row.line}
                      </td>
                      <td className="p-2">
                        {row.status === "invalid" ? (
                          <span className="text-red-700">{row.error || "Invalid"}</span>
                        ) : (
                          <span>
                            {row.status}
                            {row.enrich_queued ? (
                              <span className="block text-slate-500">Profile completion queued</span>
                            ) : null}
                            {row.lead_id ? (
                              <ButtonLink
                                to={`/admin/outreach/leads/${row.lead_id}`}
                                variant="ghost"
                                size="sm"
                                className="ml-1 !px-1"
                              >
                                View
                              </ButtonLink>
                            ) : null}
                          </span>
                        )}
                      </td>
                      <td className="p-2 text-right">{row.completeness_score ?? "—"}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Modal>

      <Modal
        open={Boolean(editLeadId && editDraft)}
        onClose={() => {
          setEditLeadId(null);
          setEditDraft(null);
        }}
        title="Edit lead profile"
        size="xl"
        footer={
          editLeadId && editDraft ? (
            <>
              <Button
                variant="secondary"
                onClick={() => {
                  setEditLeadId(null);
                  setEditDraft(null);
                }}
              >
                Cancel
              </Button>
              <Button
                loading={saveLead.isPending}
                onClick={() =>
                  saveLead.mutate({
                    id: editLeadId,
                    payload: payloadFromDraft(editDraft, editBaseProfile),
                  })
                }
              >
                Save changes
              </Button>
            </>
          ) : undefined
        }
      >
        {editDraft && (
          <div className="grid gap-4 sm:grid-cols-2">
            <TextInput label="Institute name" value={editDraft.name} onChange={(v) => setEditDraft({ ...editDraft, name: v })} />
            <TextInput
              label="Institute type"
              value={editDraft.institute_type}
              onChange={(v) => setEditDraft({ ...editDraft, institute_type: v })}
              placeholder="IT_TRAINING, COACHING, …"
            />
            <TextInput label="Contact name" value={editDraft.contact_name} onChange={(v) => setEditDraft({ ...editDraft, contact_name: v })} />
            <TextInput label="Website" value={editDraft.website} onChange={(v) => setEditDraft({ ...editDraft, website: v })} />
            <TextInput
              label="Emails (comma-separated)"
              value={editDraft.emails}
              onChange={(v) => setEditDraft({ ...editDraft, emails: v })}
              className="sm:col-span-2"
            />
            <TextInput
              label="Phones (comma-separated)"
              value={editDraft.phones}
              onChange={(v) => setEditDraft({ ...editDraft, phones: v })}
              className="sm:col-span-2"
            />
            <TextInput label="Address line" value={editDraft.address_line} onChange={(v) => setEditDraft({ ...editDraft, address_line: v })} />
            <TextInput label="City" value={editDraft.city} onChange={(v) => setEditDraft({ ...editDraft, city: v })} />
            <TextInput label="State" value={editDraft.state} onChange={(v) => setEditDraft({ ...editDraft, state: v })} />
            <TextInput label="PIN" value={editDraft.pin} onChange={(v) => setEditDraft({ ...editDraft, pin: v })} />
            <TextInput
              label="Programs (comma-separated)"
              value={editDraft.programs}
              onChange={(v) => setEditDraft({ ...editDraft, programs: v })}
              className="sm:col-span-2"
            />
            <label className="block text-sm sm:col-span-2">
              <span className="mb-1 block font-medium text-slate-700">Description</span>
              <textarea
                className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-[6rem]"
                value={editDraft.description}
                onChange={(e) => setEditDraft({ ...editDraft, description: e.target.value })}
              />
            </label>
          </div>
        )}
      </Modal>
    </div>
  );
}
