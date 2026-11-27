import { BookOpenCheck, ExternalLink, Sparkles } from "lucide-react";
import type { RedFlag, RegulatorySource } from "../api/types";
import { formatDate } from "../lib/verdicts";
import { Term } from "./Term";

const LEVELS: Record<string, string> = {
  full_text: "Read in full",
  official_listing: "Title and date confirmed",
  quoted_in_sebi_orders: "Wording as quoted in SEBI orders",
};

export function SourceRef({ source }: { source: RegulatorySource }) {
  return (
    <li className="text-sm">
      <a href={source.url} target="_blank" rel="noreferrer noopener" className="inline-flex items-start gap-1.5 font-medium text-brand-700 hover:text-brand-900">
        {source.title}
        <ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span className="sr-only">(opens sebi.gov.in in a new tab)</span>
      </a>
      <p className="mt-0.5 text-xs text-slate-500">
        {source.reference_number ? `${source.reference_number} · ` : ""}
        {source.published_on ? `Published ${formatDate(source.published_on)}` : "Date not stated on page"}
        {source.updated_on ? ` · updated ${formatDate(source.updated_on)}` : ""}
        {source.amended_up_to ? ` · amended up to ${formatDate(source.amended_up_to)}` : ""}
        {" · "}
        {LEVELS[source.verification_level] ?? source.verification_level}
      </p>
    </li>
  );
}

export function FlagCard({ flag, sources }: { flag: RedFlag; sources: RegulatorySource[] }) {
  const official = flag.basis === "verified_rule";
  const cited = sources.filter((s) => flag.rule_source_ids.includes(s.id));
  return (
    <article className={`rounded-2xl border p-5 ${official ? "border-amber-200 bg-amber-50/60" : "border-sky-200 bg-sky-50/60"}`}>
      <p className={`inline-flex items-center gap-1.5 text-xs font-semibold tracking-wide uppercase ${official ? "text-misleading" : "text-sky-800"}`}>
        {official ? <BookOpenCheck className="h-4 w-4" aria-hidden="true" /> : <Sparkles className="h-4 w-4" aria-hidden="true" />}
        {official ? <Term term="Official SEBI rule or guidance" /> : <Term term="Potential concern">Potential concern · AI observation</Term>}
      </p>
      <h3 className="mt-2 font-semibold">{flag.what_was_detected}</h3>
      <blockquote className="mt-2 border-l-2 border-current/20 pl-3 text-sm text-slate-700 italic">“{flag.detected_text}”</blockquote>
      <dl className="mt-4 space-y-3 text-sm leading-relaxed">
        <div>
          <dt className="font-semibold">Why it matters</dt>
          <dd className="text-slate-700">{flag.why_it_matters}</dd>
        </div>
        <div>
          <dt className="font-semibold">What you should know</dt>
          <dd className="text-slate-700">{flag.investor_takeaway}</dd>
        </div>
        {flag.relevant_provision && (
          <div>
            <dt className="font-semibold">Relevant provision</dt>
            <dd className="text-slate-700">{flag.relevant_provision}</dd>
          </div>
        )}
      </dl>
      {cited.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-slate-500 uppercase">{official ? "Official sources" : "Related official material"}</p>
          <ul className="mt-2 space-y-2">
            {cited.map((s) => (
              <SourceRef key={s.id} source={s} />
            ))}
          </ul>
        </div>
      )}
      {!official && <p className="mt-4 text-xs text-slate-500">This is an AI observation, not a finding that any rule was broken.</p>}
    </article>
  );
}
