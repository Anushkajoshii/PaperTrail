import { History } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { LedgerStatus, LedgerView } from "../api/types";
import { LEDGER_STATUS, LedgerList } from "../components/LedgerList";
import { ErrorState, PageHeader, Spinner } from "../components/States";

const ORDER: LedgerStatus[] = ["hit", "missed", "open", "no_data"];

export function LedgerPage() {
  const [data, setData] = useState<LedgerView | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  useEffect(() => {
    api.getLedger().then(setData).catch(setError);
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
      <PageHeader eyebrow="Claim Ledger" title="Did the stock calls come true?">
        When a creator gives a price target, PaperTrail keeps it and checks it against real prices once the deadline passes.
      </PageHeader>

      <section className="card flex gap-4 p-5 text-sm leading-relaxed text-slate-700" aria-labelledby="how-title">
        <History className="h-6 w-6 shrink-0 text-brand-600" aria-hidden="true" />
        <div>
          <h2 id="how-title" className="font-semibold text-ink">
            How a call is settled
          </h2>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>
              <strong>Target reached</strong>: on some day before the deadline, the price touched the target.
            </li>
            <li>
              <strong>Target missed</strong>: the deadline passed and it never did.
            </li>
            <li>
              The symbol, target and deadline come from the creator's own words, never from an AI guess. With no deadline, 90 days are used.
            </li>
            <li>Tracking starts when PaperTrail first saw the call, which can be later than when it was made.</li>
          </ul>
        </div>
      </section>

      {error ? (
        <ErrorState title="Could not load the ledger">{error.message}</ErrorState>
      ) : !data ? (
        <Spinner label="Loading the ledger" />
      ) : (
        <>
          <dl className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {ORDER.map((s) => (
              <div key={s} className={`rounded-xl p-4 ${LEDGER_STATUS[s].className}`}>
                <dd className="text-2xl font-bold">{data.summary.counts[s] ?? 0}</dd>
                <dt className="text-xs font-medium text-slate-700">{LEDGER_STATUS[s].label}</dt>
              </div>
            ))}
          </dl>
          <div className="mt-6">
            <LedgerList entries={data.summary.entries} showCreator />
          </div>
        </>
      )}
    </div>
  );
}
