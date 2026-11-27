import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { GlossaryTerm } from "../api/types";
import { PageHeader, Spinner } from "../components/States";

export function GlossaryPage() {
  const [terms, setTerms] = useState<GlossaryTerm[] | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => {
    api.getGlossary().then(setTerms).catch(() => setTerms([]));
  }, []);
  const shown = useMemo(
    () => (terms ?? []).filter((t) => `${t.term} ${t.definition}`.toLowerCase().includes(q.toLowerCase())),
    [terms, q],
  );
  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <PageHeader eyebrow="Glossary" title="Every term, in plain language">
        These explanations also appear when you hover over or tap a dotted-underlined word.
      </PageHeader>
      <label className="relative block">
        <span className="sr-only">Search the glossary</span>
        <Search className="pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
        <input className="input pl-11" placeholder="Search terms…" value={q} onChange={(e) => setQ(e.target.value)} />
      </label>
      {terms === null ? (
        <Spinner label="Loading the glossary" />
      ) : (
        <dl className="mt-6 divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
          {shown.map((t) => (
            <div key={t.term} className="p-5">
              <dt className="font-semibold">{t.term}</dt>
              <dd className="mt-1 text-sm leading-relaxed text-slate-700">{t.definition}</dd>
            </div>
          ))}
          {shown.length === 0 && <p className="p-5 text-sm text-slate-500">No terms match “{q}”.</p>}
        </dl>
      )}
    </div>
  );
}
