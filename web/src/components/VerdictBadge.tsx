import type { VerdictLabel } from "../api/types";
import { VERDICTS } from "../lib/verdicts";
import { Term } from "./Term";

export function VerdictBadge({ label, size = "md" }: { label: VerdictLabel; size?: "sm" | "md" }) {
  const v = VERDICTS[label];
  const Icon = v.icon;
  const pad = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ring-1 ${v.bg} ${v.text} ${v.ring} ${pad}`}>
      <Icon className={size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4"} aria-hidden="true" />
      <Term term={v.label}>{v.label}</Term>
    </span>
  );
}
