import { BookOpenCheck, ExternalLink, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { RulebookResponse } from "../api/types";
import { SourceRef } from "../components/FlagCard";
import { ErrorState, PageHeader, Spinner } from "../components/States";
import { formatDate } from "../lib/verdicts";

const LEVELS: Record<string, string> = {
  full_text: "Read in full",
  official_listing: "Title and date confirmed on SEBI's site",
  quoted_in_sebi_orders: "Wording as quoted in SEBI's own orders",
};

export function RulebookPage() {
  const [data, setData] = useState<RulebookResponse | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    api.getRulebook().then(setData).catch(() => setFailed(true));
  }, []);
  if (failed) return <ErrorState title="The rulebook could not be loaded">Please try again in a moment.</ErrorState>;
  if (!data) return <Spinner label="Loading the rulebook" />;

  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
      <PageHeader eyebrow="SEBI rulebook" title="What we check, and where each rule comes from">
        PaperTrail compares what finance creators say with official SEBI regulations, circulars and investor guidance. Every check below links to the SEBI document it relies on.
      </PageHeader>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-6">
          <BookOpenCheck className="h-6 w-6 text-misleading" aria-hidden="true" />
          <h2 className="mt-3 font-semibold">Official SEBI rule or guidance</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-700">
            A fixed check that cites a SEBI document we verified and link to. It describes what was said and what SEBI's material says. It is not a finding that anyone broke a rule.
          </p>
        </div>
        <div className="rounded-2xl border border-sky-200 bg-sky-50/60 p-6">
          <Sparkles className="h-6 w-6 text-sky-800" aria-hidden="true" />
          <h2 className="mt-3 font-semibold">Potential concern (AI observation)</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-700">
            Something the AI noticed that may deserve a closer look. It never names a regulation, is never described as a violation, and accusatory wording is blocked.
          </p>
        </div>
      </div>
      <p className="mt-4 text-sm text-slate-600">Only SEBI or a court can decide whether a rule was broken. SEBI registration does not mean SEBI endorses anyone's advice.</p>

      <h2 className="mt-12 text-2xl font-bold tracking-tight">The checks</h2>
      <div className="mt-6 space-y-5">
        {data.rules.map((r) => (
          <article key={r.id} className="card p-6">
            <h3 className="text-lg font-semibold">{r.title}</h3>
            <dl className="mt-4 grid gap-4 text-sm leading-relaxed md:grid-cols-3">
              <div>
                <dt className="font-semibold">What we look for</dt>
                <dd className="mt-1 text-slate-700">{r.what}</dd>
              </div>
              <div>
                <dt className="font-semibold">Why it matters</dt>
                <dd className="mt-1 text-slate-700">{r.why}</dd>
              </div>
              <div>
                <dt className="font-semibold">What you should know</dt>
                <dd className="mt-1 text-slate-700">{r.takeaway}</dd>
              </div>
            </dl>
            <div className="mt-5 border-t border-slate-100 pt-4">
              {r.provision && (
                <p className="text-sm">
                  <span className="font-semibold">Relevant provision:</span> {r.provision}
                </p>
              )}
              <ul className="mt-2 space-y-2">
                {r.sources.map((s) => {
                  const full = data.sources.find((x) => x.id === s.id);
                  return full ? <SourceRef key={s.id} source={full} /> : null;
                })}
              </ul>
            </div>
          </article>
        ))}
      </div>

      <h2 className="mt-12 text-2xl font-bold tracking-tight">Official sources</h2>
      <p className="mt-2 text-sm text-slate-600">Every source is on sebi.gov.in and was checked by hand. Sources are re-checked periodically because SEBI's rules change.</p>
      <div className="mt-5 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
            <tr>
              <th scope="col" className="px-4 py-3">Source</th>
              <th scope="col" className="px-4 py-3">Reference</th>
              <th scope="col" className="px-4 py-3">Published</th>
              <th scope="col" className="px-4 py-3">How we verified it</th>
              <th scope="col" className="px-4 py-3">Last checked</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.sources.map((s) => (
              <tr key={s.id} className="align-top">
                <td className="px-4 py-3">
                  <a href={s.url} target="_blank" rel="noreferrer noopener" className="inline-flex items-start gap-1 font-medium text-brand-700 hover:underline">
                    {s.title} <ExternalLink className="mt-1 h-3 w-3 shrink-0" aria-hidden="true" />
                  </a>
                  <p className="mt-1 text-xs leading-relaxed text-slate-500">{s.summary}</p>
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">{s.reference_number ?? "-"}</td>
                <td className="px-4 py-3 text-xs whitespace-nowrap text-slate-600">
                  {s.published_on ? formatDate(s.published_on) : "Not stated"}
                  {s.updated_on && <span className="block">updated {formatDate(s.updated_on)}</span>}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">{LEVELS[s.verification_level] ?? s.verification_level}</td>
                <td className="px-4 py-3 text-xs whitespace-nowrap text-slate-600">{formatDate(s.verified_on)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card mt-10 p-6">
        <h2 className="font-semibold">Deliberately not checked</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-slate-700">
          <li>Missing disclaimers: we have not verified an official requirement that applies to unregistered creators, so we do not flag their absence.</li>
          <li>Whether price data was from the last 30 days: we can't see the data a creator used, so the education check is worded conditionally.</li>
        </ul>
      </div>
    </div>
  );
}
