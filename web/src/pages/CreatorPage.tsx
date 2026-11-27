import { ChevronRight, Columns2, History, Scale, ShieldAlert, Sparkles } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ApiError, api } from "../api/client";
import type { CreatorProfile, TrackRecord, VerdictLabel } from "../api/types";
import { LedgerList } from "../components/LedgerList";
import { ErrorState, PageHeader, Spinner } from "../components/States";
import { VerdictBadge } from "../components/VerdictBadge";
import { VERDICTS, VERDICT_ORDER, formatDate } from "../lib/verdicts";

export function CreatorPage() {
  const { handle = "" } = useParams();
  const [data, setData] = useState<CreatorProfile | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  useEffect(() => {
    setData(null);
    setError(null);
    api.getCreator(handle).then(setData).catch(setError);
  }, [handle]);

  if (error) {
    return (
      <ErrorState title={error.status === 404 ? `No checks for @${handle.replace(/^@/, "")} yet` : "Something went wrong"}>
        {error.status === 404 ? "Check some of their content to start a record." : error.message}
      </ErrorState>
    );
  }
  if (!data) return <Spinner label="Loading creator" />;

  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
      <PageHeader eyebrow="Creator profile" title={data.handle}>
        {data.checks} check{data.checks === 1 ? "" : "s"} of their content, {formatDate(data.first_checked)}
        {data.first_checked !== data.last_checked && ` to ${formatDate(data.last_checked)}`} · SEBI registration: {data.registration}
      </PageHeader>

      <div className="flex gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-sm leading-relaxed text-slate-700">
        <Scale className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" aria-hidden="true" />
        {data.note}
      </div>

      <section className="mt-10" aria-labelledby="record-title">
        <h2 id="record-title" className="text-xl font-bold tracking-tight">
          Track record of checked claims
        </h2>
        <Record record={data.track_record} />
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
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
      </section>

      <section className="mt-12" aria-labelledby="ledger-title">
        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-brand-600" aria-hidden="true" />
          <h2 id="ledger-title" className="text-xl font-bold tracking-tight">
            Claim Ledger: did their stock calls come true?
          </h2>
        </div>
        <p className="mt-1 text-sm text-slate-600">
          {data.ledger.settled > 0
            ? `${data.ledger.counts.hit ?? 0} of ${data.ledger.settled} settled call${data.ledger.settled === 1 ? "" : "s"} reached the target.`
            : "No call has been settled against prices yet."}{" "}
          {data.ledger.hit_share == null && data.ledger.settled > 0 && "Too few to show a percentage."}{" "}
          <Link to="/ledger" className="font-medium text-brand-700 hover:underline">
            How the ledger works
          </Link>
        </p>
        <div className="mt-4">
          <LedgerList entries={data.ledger.entries} />
        </div>
      </section>

      <section className="mt-12" aria-labelledby="timeline-title">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-5 w-5 text-misleading" aria-hidden="true" />
          <h2 id="timeline-title" className="text-xl font-bold tracking-tight">
            Red-flag timeline
          </h2>
        </div>
        {data.timeline.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">No rulebook flags in the checked content.</p>
        ) : (
          <ol className="mt-4 space-y-3 border-l-2 border-slate-200 pl-5" aria-label="Red flags over time">
            {data.timeline.map((t, i) => (
              <li key={`${t.check_id}-${i}`} className="relative">
                <span
                  className={`absolute -left-[27px] top-1.5 h-3 w-3 rounded-full ${t.official ? "bg-amber-500" : "bg-sky-400"}`}
                  aria-hidden="true"
                />
                <p className="text-xs text-slate-500">
                  {formatDate(t.date)} · {t.official ? "Official SEBI flag" : "AI potential concern"}
                </p>
                <p className="text-sm font-medium">{t.what}</p>
                <p className="text-sm italic text-slate-600">
                  “{t.quote}”{" "}
                  <Link to={`/checks/${t.check_id}`} className="not-italic text-brand-700 hover:underline">
                    See the check
                  </Link>
                </p>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="mt-12" aria-labelledby="recent-title">
        <h2 id="recent-title" className="text-xl font-bold tracking-tight">
          Recent checks
        </h2>
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
      </section>

      <CompareForm handle={data.handle} />
    </div>
  );
}

function Record({ record: r }: { record: TrackRecord }) {
  return (
    <p className="mt-1 text-sm text-slate-600">
      {r.claims_checked} claim{r.claims_checked === 1 ? "" : "s"} checked; {r.assessed} could be assessed against evidence.{" "}
      {r.supported_share != null ? (
        <>
          <strong className="text-ink">{Math.round(r.supported_share * 100)}%</strong> of those were supported by reliable sources.
        </>
      ) : (
        "Too few assessed claims to show a percentage."
      )}
    </p>
  );
}

function CompareForm({ handle }: { handle: string }) {
  const [other, setOther] = useState("");
  const navigate = useNavigate();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (other.trim()) navigate(`/compare?handles=${encodeURIComponent(handle)},${encodeURIComponent(other.trim())}`);
  };
  return (
    <form onSubmit={submit} className="card mt-12 flex flex-wrap items-end gap-3 p-5">
      <Columns2 className="mb-2 h-5 w-5 text-brand-600" aria-hidden="true" />
      <label className="flex-1 text-sm font-medium">
        Compare {handle} with another creator
        <input
          value={other}
          onChange={(e) => setOther(e.target.value)}
          placeholder="@another_creator"
          className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
        />
      </label>
      <button type="submit" className="btn-primary" disabled={!other.trim()}>
        <Sparkles className="h-4 w-4" aria-hidden="true" /> Compare
      </button>
    </form>
  );
}
