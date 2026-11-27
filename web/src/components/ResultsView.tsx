import { BadgeCheck, CircleSlash, ExternalLink, Info, Plus, SearchX } from "lucide-react";
import { Link } from "react-router";
import type { CheckView, SebiRegistration } from "../api/types";
import { VERDICTS, VERDICT_ORDER, formatDate } from "../lib/verdicts";
import { ClaimCard } from "./ClaimCard";
import { FlagCard } from "./FlagCard";
import { RunDetails } from "./RunDetails";
import { ShareBar } from "./ShareBar";
import { Term } from "./Term";

const LANGUAGE_NAMES: Record<string, string> = { en: "English", hi: "Hindi", hinglish: "Hinglish" };

function RegistrationCard({ reg }: { reg: SebiRegistration }) {
  const registered = reg.status.startsWith("registered_");
  const kind = reg.status.includes("adviser_and") ? "Investment Adviser and Research Analyst" : reg.status.includes("adviser") ? "Investment Adviser" : "Research Analyst";
  const Icon = registered ? BadgeCheck : reg.status === "not_found" ? SearchX : CircleSlash;
  const title = registered
    ? `Registered with SEBI as ${kind}`
    : reg.status === "not_found"
      ? "Not found in our copy of SEBI's register"
      : "Registration not checked";
  return (
    <section className="card p-5" aria-labelledby="reg-title">
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 h-6 w-6 shrink-0 ${registered ? "text-supported" : "text-unverifiable"}`} aria-hidden="true" />
        <div>
          <p className="eyebrow">SEBI registration</p>
          <h2 id="reg-title" className="mt-1 font-semibold">
            {title}
          </h2>
          {reg.matched_name && <p className="mt-1 text-sm text-slate-700">{reg.matched_name} · {reg.registration_numbers.join(", ")}</p>}
          <p className="mt-2 text-sm leading-relaxed text-slate-600">{reg.note}</p>
          <p className="mt-2 text-xs text-slate-500">
            {reg.registry_snapshot_date ? `Register copy dated ${formatDate(reg.registry_snapshot_date)}. ` : ""}
            <a href="https://www.sebi.gov.in/intermediaries.html" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">
              Verify on sebi.gov.in <ExternalLink className="h-3 w-3" aria-hidden="true" />
            </a>
          </p>
        </div>
      </div>
    </section>
  );
}

export function ResultsView({ view }: { view: CheckView }) {
  const { check } = view;
  const verdictFor = (id: string) => check.verdicts.find((v) => v.claim_id === id);
  const claims = [...check.claims].sort((a, b) => {
    const ra = VERDICT_ORDER.indexOf(verdictFor(a.id)?.label ?? "not_verifiable");
    const rb = VERDICT_ORDER.indexOf(verdictFor(b.id)?.label ?? "not_verifiable");
    return ra - rb;
  });
  const counts = VERDICT_ORDER.map((label) => ({ label, n: check.verdicts.filter((v) => v.label === label).length })).filter((c) => c.n);
  const official = check.red_flags.filter((f) => f.basis === "verified_rule");
  const concerns = check.red_flags.filter((f) => f.basis === "potential_concern");
  const handle = check.input.creator_handle;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Fact-check results</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">
            {check.claims.length} claim{check.claims.length === 1 ? "" : "s"} checked
            {handle && (
              <>
                {" "}
                from{" "}
                <Link to={`/creators/${encodeURIComponent(handle.replace(/^@/, ""))}`} className="text-brand-700 hover:underline">
                  {handle.startsWith("@") ? handle : `@${handle}`}
                </Link>
              </>
            )}
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            {formatDate(check.created_at)} · {LANGUAGE_NAMES[check.detected_language ?? "en"] ?? check.detected_language} · Check {check.id}
          </p>
        </div>
        <Link to="/check" className="btn-primary">
          <Plus className="h-4 w-4" aria-hidden="true" /> New check
        </Link>
      </div>

      <div className="mt-6">
        <ShareBar check={check} />
      </div>

      {/* Summary */}
      <div className="mt-8 grid gap-5 lg:grid-cols-3">
        <section className="card p-5 lg:col-span-2" aria-labelledby="summary-title">
          <h2 id="summary-title" className="eyebrow">
            At a glance
          </h2>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {VERDICT_ORDER.map((label) => {
              const v = VERDICTS[label];
              const n = counts.find((c) => c.label === label)?.n ?? 0;
              return (
                <div key={label} className={`rounded-xl p-4 ${v.bg}`}>
                  <v.icon className={`h-5 w-5 ${v.text}`} aria-hidden="true" />
                  <p className={`mt-2 text-2xl font-bold ${v.text}`}>{n}</p>
                  <p className="text-xs font-medium text-slate-700">
                    <Term term={v.label}>{v.label}</Term>
                  </p>
                </div>
              );
            })}
          </div>
          <p className="mt-4 text-sm text-slate-600">
            <strong>{official.length}</strong> official SEBI red flag{official.length === 1 ? "" : "s"} and <strong>{concerns.length}</strong> AI potential concern
            {concerns.length === 1 ? "" : "s"}.
          </p>
        </section>
        <RegistrationCard reg={check.registration} />
      </div>

      <div className="mt-6 flex gap-3 rounded-2xl border border-brand-200 bg-brand-50 p-4 text-sm leading-relaxed text-brand-900">
        <Info className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
        <ul className="space-y-1">
          {view.notices.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      </div>

      <div className="mt-10 grid gap-10 lg:grid-cols-5">
        {/* Claims */}
        <section className="lg:col-span-3" aria-labelledby="claims-title">
          <h2 id="claims-title" className="text-xl font-bold tracking-tight">
            Claims and verdicts
          </h2>
          <p className="mt-1 text-sm text-slate-600">Most serious first. Open a claim to see the evidence and reasoning.</p>
          {claims.length === 0 ? (
            <p className="card mt-5 p-6 text-slate-600">No checkable factual claims were found. Opinions and general advice are not fact-checked.</p>
          ) : (
            <div className="mt-5 space-y-5">
              {claims.map((c, i) => (
                <ClaimCard key={c.id} claim={c} verdict={verdictFor(c.id)} evidence={check.evidence.filter((e) => e.claim_id === c.id)} index={i} />
              ))}
            </div>
          )}
        </section>

        {/* Rulebook */}
        <section className="lg:col-span-2" aria-labelledby="flags-title">
          <h2 id="flags-title" className="text-xl font-bold tracking-tight">
            SEBI rulebook
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            What was said, compared with official SEBI material.{" "}
            <Link to="/rulebook" className="font-medium text-brand-700 hover:underline">
              How these checks work
            </Link>
          </p>
          {check.red_flags.length === 0 ? (
            <p className="card mt-5 p-6 text-sm text-slate-600">No red flags from our rulebook were found in this content.</p>
          ) : (
            <div className="mt-5 space-y-4">
              {[...official, ...concerns].map((f) => (
                <FlagCard key={f.id} flag={f} sources={check.regulatory_sources} />
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Transparency */}
      <section className="mt-12 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600" aria-labelledby="run-title">
        <h2 id="run-title" className="font-semibold text-ink">
          About this check
        </h2>
        <RunDetails metrics={check.metrics} />
        {check.metrics.notes.length > 0 && (
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {check.metrics.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        )}
        <p className="mt-3">
          PaperTrail cannot judge intent, prove a legal violation, or see private groups and deleted posts.{" "}
          <Link to="/glossary" className="font-medium text-brand-700 hover:underline">
            What the terms mean
          </Link>
        </p>
      </section>
    </div>
  );
}
