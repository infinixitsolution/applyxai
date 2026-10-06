import { CheckCircle2, AlertCircle, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { cx } from "./ui";

interface ToastItem {
  id: number;
  kind: "success" | "error";
  message: string;
}

interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);
let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const dismiss = useCallback((id: number) => setItems((all) => all.filter((t) => t.id !== id)), []);
  const push = useCallback((kind: ToastItem["kind"], message: string) => {
    const id = nextId++;
    setItems((all) => [...all.slice(-2), { id, kind, message }]);
    window.setTimeout(() => dismiss(id), kind === "error" ? 6000 : 3500);
  }, [dismiss]);
  const api = useMemo<ToastApi>(() => ({
    success: (m) => push("success", m),
    error: (m) => push("error", m),
  }), [push]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 sm:items-end">
        {items.map((t) => (
          <div key={t.id} role={t.kind === "error" ? "alert" : "status"}
               className={cx("pointer-events-auto flex w-full max-w-sm items-start gap-2 rounded-lg p-3 text-sm shadow-lg ring-1",
                 t.kind === "success" ? "bg-white text-slate-800 ring-slate-200" : "bg-red-50 text-red-800 ring-red-200")}>
            {t.kind === "success" ? <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden />
              : <AlertCircle className="h-4 w-4" aria-hidden />}
            <span className="flex-1">{t.message}</span>
            <button type="button" aria-label="Dismiss" onClick={() => dismiss(t.id)} className="text-slate-400 hover:text-slate-600">
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
