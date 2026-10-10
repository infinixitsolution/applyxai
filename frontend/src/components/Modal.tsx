import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { Button, cx } from "./ui";

export function Modal({ open, onClose, title, children, footer, wide, size }:
  { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean; size?: "md" | "lg" | "xl" }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const width = size === "xl" ? "max-w-3xl" : wide || size === "lg" ? "max-w-2xl" : "max-w-md";

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal?.();
    if (!open && dialog.open) dialog.close?.();
  }, [open]);

  if (!open) return null;
  return (
    <dialog ref={ref} aria-labelledby={titleId} onCancel={(e) => { e.preventDefault(); onClose(); }}
            onClick={(e) => { if (e.target === ref.current) onClose(); }}
            className={cx("m-auto w-[calc(100%-1rem)] rounded-xl p-0 shadow-xl backdrop:bg-slate-900/40 sm:w-[calc(100%-2rem)]",
              width)}>
      <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3 sm:gap-4 sm:px-5 sm:py-4">
        <h2 id={titleId} className="pr-2 text-base font-semibold leading-snug text-slate-900">{title}</h2>
        <button type="button" aria-label="Close" onClick={onClose} className="text-slate-400 hover:text-slate-600">
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="max-h-[70vh] overflow-y-auto px-5 py-4 text-sm text-slate-700">{children}</div>
      {footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</div>}
    </dialog>
  );
}

export function ConfirmDialog({ open, title, message, confirmLabel = "Confirm", danger, loading, onConfirm, onClose }: {
  open: boolean; title: string; message: ReactNode; confirmLabel?: string; danger?: boolean; loading?: boolean;
  onConfirm: () => void; onClose: () => void;
}) {
  return (
    <Modal open={open} onClose={onClose} title={title} footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button variant={danger ? "danger" : "primary"} loading={loading} onClick={onConfirm}>{confirmLabel}</Button>
      </>
    }>
      {message}
    </Modal>
  );
}
