import { CheckCircle2, CircleDashed, CircleHelp, XCircle } from "lucide-react";
import { Link } from "react-router";
import type { LedgerEntryView, LedgerStatus } from "../api/types";
import { formatDate } from "../lib/verdicts";

export const LEDGER_STATUS: Record<LedgerStatus, { label: string; className: string; Icon: typeof CheckCircle2 }> = {
  hit: { label: "Target reached", className: "bg-emerald-50 text-supported", Icon: CheckCircle2 },
  missed: { label: "Target missed", className: "bg-rose-50 text-contradicted", Icon: XCircle },
  open: { label: "Still running", className: "bg-slate-100 text-slate-700", Icon: CircleDashed },
  no_data: { label: "No price data", className: "bg-amber-50 text-misleading", Icon: CircleHelp },
};

function rupees(n: number | null | undefined) {
  return n == null ? "–" : `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

export function LedgerStatusBadge({ status }: { status: LedgerStatus }) {
  const s = LEDGER_STATUS[status];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${s.className}`}>
      <s.Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {s.label}
    </span>
  );
}

/** Stock calls and what happened to them. Each row links back to the check it came from. */
export function LedgerList({ entries, showCreator = false }: { entries: LedgerEntryView[]; showCreator?: boolean }) {
  if (entries.length === 0) {
    return <p className="text-sm text-slate-600">No stock calls with a price target have been tracked yet.</p>;
  }
  return (
    <ul className="space-y-3" aria-label="Tracked stock calls">
      {entries.map(({ entry: e, target, status_description }) => (
        <li key={e.id} className="card p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">
              {e.ticker} · {e.direction === "down" ? "falls to" : "reaches"} {rupees(target)}
              {e.target_pct != null && target == null && ` (${e.direction === "down" ? "−" : "+"}${e.target_pct}%)`}
              <span className="font-normal text-slate-600"> by {formatDate(e.due_on)}</span>
              {!e.deadline_stated && <span className="text-xs font-normal text-slate-500"> (no deadline given; 90 days used)</span>}
            </p>
            <LedgerStatusBadge status={e.status} />
          </div>
          <p className="mt-2 text-sm italic text-slate-600">“{e.quote}”</p>
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600 sm:grid-cols-4">
            <div>
              <dt className="text-slate-500">Tracked from</dt>
              <dd>{formatDate(e.made_on)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Starting price</dt>
              <dd>{rupees(e.baseline_price)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">{e.status === "hit" ? "Reached on" : "Closest so far"}</dt>
              <dd>{e.status === "hit" && e.hit_on ? formatDate(e.hit_on) : rupees(e.best_price)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Last price</dt>
              <dd>{rupees(e.last_price)}</dd>
            </div>
          </dl>
          <p className="mt-2 text-xs text-slate-500">
            {status_description}
            {e.price_source && ` Prices: ${e.price_source}.`}{" "}
            <Link to={`/checks/${e.check_id}`} className="font-medium text-brand-700 hover:underline">
              See the check
            </Link>
            {showCreator && e.creator && (
              <>
                {" · "}
                <Link to={`/creators/${e.creator}`} className="font-medium text-brand-700 hover:underline">
                  @{e.creator}
                </Link>
              </>
            )}
          </p>
        </li>
      ))}
    </ul>
  );
}
