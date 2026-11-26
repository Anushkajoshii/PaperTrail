import { ExternalLink } from "lucide-react";
import type { Evidence } from "../api/types";
import { STANCE_LABELS, band, formatDate, hostOf } from "../lib/verdicts";
import { Term } from "./Term";

const SOURCE_TYPES: Record<string, string> = {
  regulator: "Regulator",
  exchange: "Stock exchange",
  company_filing: "Company filing",
  data_provider: "Data provider",
  reputable_news: "News outlet",
  blog: "Blog",
  social: "Social media",
  other: "Other website",
};

const BAND_STYLE = { High: "bg-emerald-50 text-emerald-800", Medium: "bg-amber-50 text-amber-800", Low: "bg-slate-100 text-slate-600" };

function QualityChip({ term, score }: { term: string; score: number }) {
  const b = band(score);
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${BAND_STYLE[b]}`}>
      <Term term={term}>{term}</Term>
      <span className="ml-1">{b}</span>
    </span>
  );
}

const STANCE_BORDER: Record<string, string> = {
  supports: "border-l-supported",
  contradicts: "border-l-contradicted",
  context: "border-l-slate-300",
};

export function EvidenceItem({ evidence, number }: { evidence: Evidence; number?: number }) {
  const demo = hostOf(evidence.url).endsWith(".test");
  return (
    <li className={`rounded-xl border border-slate-200 border-l-4 bg-white p-4 ${STANCE_BORDER[evidence.stance]}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <a href={evidence.url} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1.5 font-medium text-ink hover:text-brand-700">
          {number != null && <span className="rounded bg-slate-100 px-1.5 text-xs font-semibold text-slate-600">Source {number}</span>}
          {evidence.title}
          <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
        <span className="text-xs font-medium text-slate-500">{STANCE_LABELS[evidence.stance]}</span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {hostOf(evidence.url)} · {SOURCE_TYPES[evidence.source_type] ?? evidence.source_type} · {formatDate(evidence.published_at)}
        {demo && <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 font-medium">demo data</span>}
      </p>
      <blockquote className="mt-3 text-sm leading-relaxed text-slate-700">“{evidence.snippet}”</blockquote>
      <div className="mt-3 flex flex-wrap gap-2">
        <QualityChip term="Reliability" score={evidence.quality.reliability} />
        <QualityChip term="Recency" score={evidence.quality.recency} />
        <QualityChip term="Relevance" score={evidence.quality.relevance} />
      </div>
    </li>
  );
}
