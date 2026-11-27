import { ChevronRight, History, Scale } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { ApiError, api } from "../api/client";
import type { CreatorView, VerdictLabel } from "../api/types";
import { ErrorState, PageHeader, Spinner } from "../components/States";
import { VerdictBadge } from "../components/VerdictBadge";
import { VERDICTS, VERDICT_ORDER, formatDate } from "../lib/verdicts";

export function CreatorPage() {
  const { handle = "" } = useParams();
  const [data, setData] = useState<CreatorView | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  useEffect(() => {
    api.getCreator(handle).then(setData).catch(setError);
  }, [handle]);

  if (error) {
    return <ErrorState title={error.status === 404 ? `No checks for @${handle.replace(/^@/, "")} yet` : "Something went wrong"}>{error.status === 404 ? "Check some of their content to start a record." : error.message}</ErrorState>;
  }
  if (!data) return <Spinner label="Loading creator" />;

  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
      <PageHeader eyebrow="Creator" title={data.handle}>
        {data.checks} check{data.checks === 1 ? "" : "s"} of this creator's content.
      </PageHeader>

      <div className="flex gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-sm leading-relaxed text-slate-700">
        <Scale className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" aria-hidden="true" />
        {data.note}
      </div>

      <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {VERDICT_ORDER.map((label) => (
          <div key={label} className={`rounded-xl p-4 ${VERDICTS[label].bg}`}>
            <p className={`text-2xl font-bold ${VERDICTS[label].text}`}>{data.totals[label] ?? 0}</p>
            <p className="text-xs font-medium text-slate-700">{VERDICTS[label].label}</p>
          </div>
        ))}
        <div className="rounded-xl bg-amber-50 p-4">
          <p className="text-2xl font-bold text-misleading">{data.totals.official_flags ?? 0}</p>
          <p className="text-xs font-medium text-slate-700">Official SEBI flags</p>
        </div>
        <div className="rounded-xl bg-sky-50 p-4">
          <p className="text-2xl font-bold text-sky-800">{data.totals.potential_concerns ?? 0}</p>
          <p className="text-xs font-medium text-slate-700">AI concerns</p>
        </div>
      </div>

      <h2 className="mt-12 text-xl font-bold tracking-tight">Recent checks</h2>
      <ul className="mt-4 space-y-3">
        {data.recent.map((c) => (
          <li key={c.id}>
            <Link to={`/checks/${c.id}`} className="card flex items-center justify-between gap-4 p-4 hover:border-brand-500">
              <div>
                <p className="font-medium">
                  {c.claims} claim{c.claims === 1 ? "" : "s"} · {formatDate(c.created_at)}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(Object.entries(c.verdicts) as [VerdictLabel, number][]).map(([label, n]) => (
                    <span key={label} className="inline-flex items-center gap-1 text-xs">
                      <VerdictBadge label={label} size="sm" /> × {n}
                    </span>
                  ))}
                </div>
              </div>
              <ChevronRight className="h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>

      <div className="card mt-10 flex gap-4 p-6">
        <History className="h-6 w-6 shrink-0 text-brand-600" aria-hidden="true" />
        <div>
          <h2 className="font-semibold">Claim Ledger: coming soon</h2>
          <p className="mt-1 text-sm leading-relaxed text-slate-600">
            Past stock calls will be re-checked against actual prices after their deadlines, building a track record based on what can be verified.
          </p>
        </div>
      </div>
    </div>
  );
}
