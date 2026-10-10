import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { formatRelative } from "../lib/format";
import { notificationLink } from "../lib/notificationLink";
import { formatNotificationType } from "../lib/notificationLabel";
import { notifications } from "../services/endpoints";
import { cx } from "./ui";

/** @deprecated Use notificationLink from ../lib/notificationLink */
export function appLink(link: string): string {
  return notificationLink(link);
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const client = useQueryClient();
  const { data: prefs } = useQuery({
    queryKey: ["notifications", "preferences"],
    queryFn: notifications.preferences,
    staleTime: 5 * 60_000,
  });
  const { data } = useQuery({
    queryKey: ["notifications", "bell"],
    queryFn: () => notifications.list({ page_size: 6 }),
    refetchInterval: open ? 15_000 : 60_000,
    refetchOnWindowFocus: true,
  });
  const readAll = useMutation({
    mutationFn: notifications.readAll,
    onSuccess: () => client.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const readOne = useMutation({
    mutationFn: notifications.read,
    onSuccess: () => client.invalidateQueries({ queryKey: ["notifications"] }),
  });

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  const typeLabel = (type: string) => prefs?.types[type]?.label ?? formatNotificationType(type);
  const unread = data?.unread_count ?? 0;

  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
              aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
              className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700">
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 rounded-xl bg-white shadow-lg ring-1 ring-slate-200">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <span className="text-sm font-semibold">Notifications</span>
            {unread > 0 && (
              <button type="button" onClick={() => readAll.mutate()} className="text-xs font-medium text-brand-600 hover:underline">
                Mark all as read
              </button>
            )}
          </div>
          <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
            {data?.items.length ? data.items.map((n) => {
              const href = n.link ? notificationLink(n.link) : "/app/notifications";
              return (
                <li key={n.id} className={cx("px-4 py-3 text-sm", !n.read_at && "bg-brand-50/50")}>
                  <Link
                    to={href}
                    onClick={() => { if (!n.read_at) readOne.mutate(n.id); setOpen(false); }}
                    className="block"
                  >
                    <p className="text-xs font-medium text-slate-500">{typeLabel(n.type)}</p>
                    <p className="font-medium text-slate-900">{n.title}</p>
                    {n.body && <p className="mt-0.5 text-slate-600">{n.body}</p>}
                    <p className="mt-1 text-xs text-slate-400">{formatRelative(n.created_at)}</p>
                  </Link>
                </li>
              );
            }) : <li className="px-4 py-8 text-center text-sm text-slate-500">You're all caught up.</li>}
          </ul>
          <Link to="/app/notifications" onClick={() => setOpen(false)}
                className="block border-t border-slate-100 px-4 py-2.5 text-center text-sm font-medium text-brand-600 hover:bg-slate-50">
            View all
          </Link>
        </div>
      )}
    </div>
  );
}
