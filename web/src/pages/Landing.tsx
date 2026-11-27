import {
  ArrowRight,
  BookOpenCheck,
  FileSearch,
  Languages,
  Link2,
  Lock,
  Scale,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router";
import { VerdictBadge } from "../components/VerdictBadge";
import { useI18n } from "../lib/i18n";

const FEATURES = [
  {
    icon: FileSearch,
    title: "Evidence you can check yourself",
    body: "Every verdict links to its sources: exchange data, company filings, regulators and established news. Each source is rated for reliability, recency and relevance.",
  },
  {
    icon: BookOpenCheck,
    title: "A verified SEBI rulebook",
    body: "Red flags like guaranteed returns or unregistered stock tips are matched to official SEBI regulations, circulars and investor cautions, with reference numbers and dates.",
  },
  {
    icon: Sparkles,
    title: "AI that explains itself",
    body: "See why each verdict was reached, what supports or contradicts it, what couldn't be verified, and how confident the assessment is, in plain language.",
  },
  {
    icon: Languages,
    title: "Hindi, English and Hinglish",
    body: "Built for how Indian creators actually talk. Original quotes are always shown as spoken, next to a clear English summary.",
  },
  {
    icon: Scale,
    title: "Fair to creators",
    body: "Verdicts are about claims, never people. 'Not found in SEBI's register' is never treated as proof of anything, and AI observations are always labelled as such.",
  },
  {
    icon: Lock,
    title: "Safe by design",
    body: "Web pages can't trick the AI with hidden instructions, invented claims are thrown out automatically, and no personal contact data is ever stored.",
  },
];

export function Landing() {
  const { t } = useI18n();
  const steps = [1, 2, 3, 4] as const;
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-b from-white to-surface">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24">
          <div>
            <p className="eyebrow">{t("hero.eyebrow")}</p>
            <h1 className="mt-3 text-4xl font-bold tracking-tight text-ink sm:text-5xl lg:text-6xl">{t("hero.title")}</h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-600">{t("hero.subtitle")}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/check" className="btn-primary">
                {t("hero.cta")} <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <a href="#how" className="btn-secondary">
                {t("hero.secondary")}
              </a>
            </div>
            <p className="mt-4 text-sm text-slate-500">{t("hero.note")}</p>
          </div>
          <SamplePreview />
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16 sm:px-6">
        <h2 className="text-3xl font-bold tracking-tight">{t("how.title")}</h2>
        <ol className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((n) => (
            <li key={n} className="card p-6">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-50 text-sm font-bold text-brand-700">{n}</span>
              <h3 className="mt-4 font-semibold">{t(`how.${n}.title`)}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{t(`how.${n}.body`)}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Features */}
      <section className="bg-white">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <p className="eyebrow">Why PaperTrail</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight">Built to be trusted, not just impressive</h2>
          <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title}>
                <f.icon className="h-7 w-7 text-brand-600" aria-hidden="true" />
                <h3 className="mt-3 font-semibold">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Honesty */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="card grid gap-8 p-8 lg:grid-cols-2">
          <div>
            <ShieldCheck className="h-8 w-8 text-brand-600" aria-hidden="true" />
            <h2 className="mt-3 text-2xl font-bold tracking-tight">What PaperTrail is not</h2>
            <p className="mt-3 leading-relaxed text-slate-600">
              Being clear about limits is part of being trustworthy. PaperTrail is a tool to help you ask better questions, not a replacement for your own judgement.
            </p>
          </div>
          <ul className="space-y-3 text-sm leading-relaxed text-slate-700">
            {[
              "Not financial advice. It never tells you to buy or sell anything.",
              "Not a judge of people. It assesses specific claims, never anyone's honesty or intent.",
              "Not a legal finding. Only SEBI or a court can decide whether a rule was broken.",
              "Not all-knowing. Private groups, paid courses and deleted posts are usually out of reach.",
              "Not perfect. AI can make mistakes, so every verdict shows its sources so you can check.",
            ].map((item) => (
              <li key={item} className="flex gap-3">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="mt-12 text-center">
          <Link to="/check" className="btn-primary">
            {t("hero.cta")} <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </section>
    </>
  );
}

/** A static illustration of a result card (demo data), so visitors see the output at a glance. */
function SamplePreview() {
  return (
    <div className="card relative p-6 lg:ml-8" aria-label="Example result (illustration)">
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <Link2 className="h-3.5 w-3.5" aria-hidden="true" /> Example result · demo data
        </span>
        <span>Hinglish</span>
      </div>
      <p className="mt-4 text-sm text-slate-500">They said:</p>
      <blockquote className="mt-1 border-l-4 border-brand-200 pl-3 text-lg font-medium">
        “Mere premium group mein guaranteed 5% har mahine milega, bilkul risk-free.”
      </blockquote>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <VerdictBadge label="misleading" />
        <span className="text-sm text-slate-600">High confidence in this assessment</span>
      </div>
      <p className="mt-4 text-sm leading-relaxed text-slate-700">
        Market investments carry risk, so a promise of guaranteed returns leaves out important context.
      </p>
      <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
        <p className="text-xs font-semibold tracking-wide text-misleading uppercase">Official SEBI guidance</p>
        <p className="mt-1 text-sm text-slate-700">
          SEBI's caution on social-media frauds (PR No. 22/2025) lists promises of assured or risk-free returns as a common trick.
        </p>
      </div>
    </div>
  );
}
