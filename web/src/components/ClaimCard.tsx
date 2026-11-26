import { ChevronDown, Clock, Info } from "lucide-react";
import { useState } from "react";
import type { Claim, Evidence, Verdict } from "../api/types";
import { CLAIM_TYPE_LABELS, VERDICTS, band, formatTimestamp } from "../lib/verdicts";
import { EvidenceItem } from "./Evidence";
import { Term } from "./Term";
import { VerdictBadge } from "./VerdictBadge";

export function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const b = band(value);
  return (
    <div className="min-w-40">
      <div className="flex items-baseline justify-between text-xs text-slate-500">
        <Term term="Confidence">Confidence</Term>
        <span className="font-semibold text-ink">{b}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label={`Confidence ${b}, ${pct} out of 100`}>
        <div className="h-full rounded-full bg-ink/70" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function ClaimCard({ claim, verdict, evidence, index }: { claim: Claim; verdict?: Verdict; evidence: Evidence[]; index: number }) {
  const [open, setOpen] = useState(index === 0);
  const ts = formatTimestamp(claim.timestamp_seconds);
  const groups = (["supports", "contradicts", "context"] as const)
    .map((stance) => ({ stance, items: evidence.filter((e) => e.stance === stance) }))
    .filter((g) => g.items.length);
  const style = verdict ? VERDICTS[verdict.label] : null;
  // Number sources in display order and replace internal evidence ids in the reasoning with
  // "source N", so explanations read naturally.
  const ordered = groups.flatMap((g) => g.items);
  const numberOf = new Map(ordered.map((e, i) => [e.id, i + 1]));
  const readable = (text: string) =>
    text.replace(/\bevd_[A-Za-z0-9_]+\b|\be\d+\b/g, (id) => (numberOf.has(id) ? `source ${numberOf.get(id)}` : id));
  return (
    <article className="card overflow-hidden">
      <div className={`h-1 ${style ? style.bg : "bg-slate-100"}`} aria-hidden="true" />
      <div className="p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className="rounded-md bg-slate-100 px-2 py-0.5 font-medium text-slate-600">{CLAIM_TYPE_LABELS[claim.claim_type] ?? claim.claim_type}</span>
          {ts && (
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" aria-hidden="true" /> at {ts}
            </span>
          )}
          {claim.tickers.map((tk) => (
            <span key={tk} className="rounded-md bg-brand-50 px-2 py-0.5 font-mono text-brand-700">
              {tk}
            </span>
          ))}
        </div>
        <h3 className="mt-3 text-lg leading-snug font-semibold">{claim.text}</h3>
        {claim.quote !== claim.text && <p className="mt-2 border-l-2 border-slate-200 pl-3 text-sm text-slate-600 italic">Said: “{claim.quote}”</p>}

        {verdict && (
          <>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
              <VerdictBadge label={verdict.label} />
              <ConfidenceMeter value={verdict.confidence} />
            </div>
            <p className="mt-4 leading-relaxed text-slate-700">{readable(verdict.explanation.summary)}</p>

            <button
              type="button"
              className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-700 hover:text-brand-900"
              aria-expanded={open}
              onClick={() => setOpen((o) => !o)}
            >
              {open ? "Hide details" : "Why this verdict?"}
              <ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} aria-hidden="true" />
            </button>

            {open && (
              <div className="mt-4 space-y-5 border-t border-slate-100 pt-5">
                {verdict.explanation.reasoning.length > 0 && (
                  <section>
                    <h4 className="text-sm font-semibold">How we got there</h4>
                    <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm leading-relaxed text-slate-700">
                      {verdict.explanation.reasoning.map((r) => (
                        <li key={r}>{readable(r)}</li>
                      ))}
                    </ol>
                  </section>
                )}
                {groups.length > 0 && (
                  <section>
                    <h4 className="text-sm font-semibold">
                      <Term term="Evidence">Evidence</Term> ({evidence.length})
                    </h4>
                    <ul className="mt-3 space-y-3">
                      {ordered.map((e) => (
                        <EvidenceItem key={e.id} evidence={e} number={numberOf.get(e.id)} />
                      ))}
                    </ul>
                  </section>
                )}
                {verdict.explanation.could_not_verify.length > 0 && (
                  <section className="rounded-xl bg-slate-50 p-4">
                    <h4 className="text-sm font-semibold">What we could not verify</h4>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-slate-700">
                      {verdict.explanation.could_not_verify.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  </section>
                )}
                {verdict.explanation.confidence_note && (
                  <p className="flex gap-2 text-xs leading-relaxed text-slate-500">
                    <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    {verdict.explanation.confidence_note}
                  </p>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </article>
  );
}
