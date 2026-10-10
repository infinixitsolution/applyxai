import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Briefcase, Building, Mail, Phone, Users } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Alert, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime, safeExternalUrl } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { admin } from "../../services/endpoints";
import { Stat, Table, Td } from "./shared";

export function AdminCompanyPage() {
  const { company: encoded = "" } = useParams();
  const name = decodeURIComponent(encoded);
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "company", name],
    queryFn: () => admin.company(name),
    enabled: Boolean(name),
  });

  return (
    <>
      <Link
        to="/admin/companies"
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden /> All companies
      </Link>
      {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : (
        <>
          <PageHeader title={data.company} description="Jobs this company turned up in searches, and the people we can reach." />
          <div className="grid gap-6 lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-start">
            <aside className="space-y-4 lg:sticky lg:top-6">
              <Card title="Directory">
                <div className="border-b border-slate-100 pb-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Company overview</p>
                  <p className="mt-2 text-lg font-semibold text-slate-900">{data.company}</p>
                  <p className="mt-1 text-sm text-slate-600">
                    {data.locations.length ? data.locations.join(" · ") : "No location recorded"}
                  </p>
                  <dl className="mt-4 space-y-2 text-sm">
                    <div className="flex justify-between gap-3"><dt className="text-slate-500">Jobs found</dt><dd className="font-medium text-slate-900">{data.jobs}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-slate-500">Applied</dt><dd className="font-medium text-slate-900">{data.applied}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-slate-500">Candidates</dt><dd className="font-medium text-slate-900">{data.users}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-slate-500">Search filters</dt><dd className="font-medium text-slate-900">{data.search_filters}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-slate-500">Last seen</dt><dd className="text-right text-slate-900">{data.last_seen ? formatDateTime(data.last_seen) : "—"}</dd></div>
                  </dl>
                </div>
                <nav className="mt-4 flex flex-col gap-1 text-sm" aria-label="Company sections">
                  <a href="#jobs" className="rounded-lg px-2 py-1.5 font-medium text-slate-700 hover:bg-slate-50">Jobs</a>
                  <a href="#contacts" className="rounded-lg px-2 py-1.5 font-medium text-slate-700 hover:bg-slate-50">Contact directory</a>
                </nav>
              </Card>
            </aside>

            <div className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Stat icon={<Briefcase className="h-4 w-4" />} label="Jobs found" value={data.jobs} />
                <Stat icon={<Building className="h-4 w-4" />} label="Applied" value={data.applied} />
                <Stat icon={<Users className="h-4 w-4" />} label="Candidates" value={data.users} />
                <Stat icon={<Mail className="h-4 w-4" />} label="Company contacts" value={data.contacts.length} sub="Published on the job, not the applicant" />
              </div>

              <Card title="Jobs">
                <div id="jobs">
                  {data.job_list.length === 0 ? (
                    <EmptyState icon={<Briefcase className="h-10 w-10" />} title="No jobs yet">
                      Nobody's search has returned a posting at this company.
                    </EmptyState>
                  ) : (
                    <Table head={["Job", "Location", "Applied", "Other", "Users", "Last seen"]}>
                      {data.job_list.map((job) => {
                        const url = safeExternalUrl(job.job_url);
                        return (
                          <tr key={job.id} className="hover:bg-slate-50/80">
                            <Td className="max-w-xs font-medium text-slate-900">
                              {url ? (
                                <a href={url} target="_blank" rel="noopener noreferrer" className="hover:text-brand-700">{job.title}</a>
                              ) : job.title}
                            </Td>
                            <Td className="max-w-[10rem] text-slate-600">{job.location || "—"}</Td>
                            <Td className="font-medium text-slate-900">{job.applied}</Td>
                            <Td className="text-slate-600">{job.other}</Td>
                            <Td>{job.users}</Td>
                            <Td className="whitespace-nowrap text-slate-600">{job.last_seen ? formatDateTime(job.last_seen) : "—"}</Td>
                          </tr>
                        );
                      })}
                    </Table>
                  )}
                </div>
              </Card>

              <Card title="Contact directory">
                <div id="contacts">
                  <p className="mb-4 text-sm text-slate-500">
                    Name, email, or phone the company published on the posting. Applicant accounts are not listed here.
                  </p>
                  {data.contacts.length === 0 ? (
                    <EmptyState icon={<Phone className="h-10 w-10" />} title="No company contact published">
                      These postings did not include a name, email, or phone. New searches save them when LinkedIn shows them.
                    </EmptyState>
                  ) : (
                    <Table head={["Name", "Email", "Phone", "Found on"]}>
                      {data.contacts.map((c, index) => {
                        const profile = safeExternalUrl(c.link);
                        return (
                        <tr key={`${c.email}-${c.phone}-${c.name}-${index}`} className="hover:bg-slate-50/80">
                          <Td>
                            {profile ? (
                              <a href={profile} target="_blank" rel="noopener noreferrer" className="font-medium text-slate-900 hover:text-brand-700">{c.name || "Hiring contact"}</a>
                            ) : (
                              <span className="font-medium text-slate-900">{c.name || "—"}</span>
                            )}
                            {c.role && <p className="mt-1 text-xs text-slate-500">{c.role}</p>}
                          </Td>
                          <Td className="max-w-[14rem] truncate">
                            {c.email ? <a className="text-brand-700 hover:underline" href={`mailto:${c.email}`}>{c.email}</a> : <span className="text-slate-400">—</span>}
                          </Td>
                          <Td className="whitespace-nowrap">
                            {c.phone ? <a className="inline-flex items-center gap-1 text-slate-900 hover:text-brand-700" href={`tel:${c.phone.replace(/\s/g, "")}`}><Phone className="h-3.5 w-3.5 text-slate-400" aria-hidden />{c.phone}</a> : <span className="text-slate-400">—</span>}
                          </Td>
                          <Td className="max-w-[12rem] text-slate-600">
                            {c.jobs.map((job) => job.title).join(", ") || "—"}
                          </Td>
                        </tr>
                        );
                      })}
                    </Table>
                  )}
                </div>
              </Card>
            </div>
          </div>
        </>
      )}
    </>
  );
}
