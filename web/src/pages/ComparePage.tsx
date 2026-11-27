import { Info } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { ApiError, api } from "../api/client";
import type { CompareView, CreatorProfile } from "../api/types";
import { ErrorState, PageHeader, Spinner } from "../components/States";
import { formatDate } from "../lib/verdicts";

type Row = { label: string; hint?: string; value: (c: CreatorProfile) => ReactNode };

const pct = (x: number | null | undefined) => (x == null ? "Too few to say" : `${Math.round(x * 100)}%`);

const ROWS: Row[] = [
  { label: "Checks of their content", value: (c) => c.checks },
  {
    label: "Checked",
    value: (c) =>
      c.first_checked === c.last_checked
        ? formatDate(c.first_checked)
        : `${formatDate(c.first_checked)} to ${formatDate(c.last_checked)}`,
  },
  { label: "SEBI registration", value: (c) => c.registration },
  { label: "Claims checked", value: (c) => c.track_record.claims_checked },
  { label: "Supported", value: (c) => c.track_record.supported },
  { label: "Contradicted", value: (c) => c.track_record.contradicted },
  { label: "Misleading", value: (c) => c.track_record.misleading },
  { label: "Not verifiable", value: (c) => c.track_record.not_verifiable },
  {
    label: "Share supported",
    hint: "Of claims that could be assessed; shown from 5 assessed claims",
    value: (c) => pct(c.track_record.supported_share),
  },
  { label: "Official SEBI flags", value: (c) => c.totals.official_flags ?? 0 },
  { label: "AI potential concerns", value: (c) => c.totals.potential_concerns ?? 0 },
  { label: "Stock calls: reached target", value: (c) => c.ledger.counts.hit ?? 0 },
  { label: "Stock calls: missed", value: (c) => c.ledger.counts.missed ?? 0 },
  { label: "Stock calls: still running", value: (c) => c.ledger.counts.open ?? 0 },
  { label: "Calls that hit", hint: "Of settled calls; shown from 5 settled calls", value: (c) => pct(c.ledger.hit_share) },
];

function parseHandles(raw: string | null) {
  return (raw ?? "")
    .split(",")
    .map((h) => h.trim())
    .filter(Boolean)
    .slice(0, 3);
}

export function ComparePage() {
  const [params, setParams] = useSearchParams();
  const handles = parseHandles(params.get("handles"));
  const key = handles.join(",");
  const [data, setData] = useState<CompareView | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [draft, setDraft] = useState(key);

  useEffect(() => {
    setData(null);
    setError(null);
    if (key.split(",").filter(Boolean).length >= 2) api.compareCreators(key.split(",")).then(setData).catch(setError);
  }, [key]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setParams({ handles: parseHandles(draft).join(",") });
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
      <PageHeader eyebrow="Compare creators" title="Side by side">
        Facts about checked claims for two or three creators.
      </PageHeader>

      <form onSubmit={submit} className="card flex flex-wrap items-end gap-3 p-5">
        <label className="flex-1 text-sm font-medium">
          Handles, separated by commas
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="@creator_one, @creator_two"
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
          />
        </label>
        <button type="submit" className="btn-primary" disabled={parseHandles(draft).length < 2}>
          Compare
        </button>
      </form>

      {handles.length < 2 ? null : error ? (
        <ErrorState title="Could not compare">{error.message}</ErrorState>
      ) : !data ? (
        <Spinner label="Comparing creators" />
      ) : (
        <>
          <div className="mt-8 flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-slate-800" role="note">
            <Info className="mt-0.5 h-5 w-5 shrink-0 text-misleading" aria-hidden="true" />
            {data.note}
          </div>
          {data.missing.length > 0 && (
            <p className="mt-4 text-sm text-slate-600">No checks yet for {data.missing.join(", ")}.</p>
          )}
          {data.creators.length > 0 && (
            <div className="mt-6 overflow-x-auto">
              <table className="w-full min-w-[480px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th scope="col" className="py-3 pr-4 font-medium text-slate-500">
                      &nbsp;
                    </th>
                    {data.creators.map((c) => (
                      <th key={c.handle} scope="col" className="py-3 pr-4 font-semibold">
                        <Link to={`/creators/${c.handle.slice(1)}`} className="text-brand-700 hover:underline">
                          {c.handle}
                        </Link>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map((row) => (
                    <tr key={row.label} className="border-b border-slate-100">
                      <th scope="row" className="py-2.5 pr-4 font-normal text-slate-600">
                        {row.label}
                        {row.hint && <span className="block text-xs text-slate-400">{row.hint}</span>}
                      </th>
                      {data.creators.map((c) => (
                        <td key={c.handle} className="py-2.5 pr-4 tabular-nums">
                          {row.value(c)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
