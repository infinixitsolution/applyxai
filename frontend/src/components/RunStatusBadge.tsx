import { Badge } from "./ui";
import type { RunStatus } from "../types";

const RUN_STATUS: Record<RunStatus, { label: string; tone: "blue" | "amber" | "green" | "red" | "slate" }> = {
  queued: { label: "Waiting", tone: "blue" },
  running: { label: "Running", tone: "blue" },
  paused: { label: "Paused", tone: "amber" },
  completed: { label: "Finished", tone: "green" },
  failed: { label: "Failed", tone: "red" },
  cancelled: { label: "Stopped", tone: "slate" },
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const { label, tone } = RUN_STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}
